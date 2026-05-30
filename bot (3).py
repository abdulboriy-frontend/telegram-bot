import os
import re
import asyncio
import logging
import subprocess
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import yt_dlp

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)
MAX_BYTES = 49 * 1024 * 1024  # 49MB

INSTAGRAM_RE = re.compile(r"(https?://)?(www\.)?instagram\.com/(p|reel|tv|stories)/[\w\-]+")
YOUTUBE_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[\w\-]+")
TIKTOK_RE = re.compile(r"(https?://)?(www\.|vm\.)?tiktok\.com/[\S]+")


def detect(url: str) -> str | None:
    if INSTAGRAM_RE.search(url): return "Instagram"
    if YOUTUBE_RE.search(url): return "YouTube"
    if TIKTOK_RE.search(url): return "TikTok"
    return None


def get_opts(platform: str, out_tmpl: str) -> dict:
    base = {
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30,
    }

    if platform == "YouTube":
        base["format"] = (
            "bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]"
            "/bestvideo[height<=480]+bestaudio"
            "/best[height<=480]"
            "/best[ext=mp4]"
            "/best"
        )
        base["merge_output_format"] = "mp4"
        base["postprocessors"] = [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }]
    elif platform == "Instagram":
        base["format"] = "best[ext=mp4]/best"
    elif platform == "TikTok":
        base["format"] = "best[ext=mp4]/best"
        base["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    return base


def find_downloaded_file(stem: str) -> Path | None:
    for f in DOWNLOAD_DIR.iterdir():
        if f.stem == stem and f.suffix in (".mp4", ".mkv", ".webm", ".mov"):
            return f
    return None


def download_sync(url: str, platform: str) -> tuple:
    out_tmpl = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")

    # 1-urinish: ffmpeg bilan
    opts = get_opts(platform, out_tmpl)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id", "")
            path = find_downloaded_file(video_id)
            if path and path.exists():
                return path, ""
    except Exception as e:
        logger.warning("1-urinish xato: %s", e)

    # 2-urinish: ffmpegsiz
    opts2 = {
        "outtmpl": out_tmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "best[ext=mp4][height<=480]/best[ext=mp4]/best",
    }
    try:
        with yt_dlp.YoutubeDL(opts2) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id", "")
            path = find_downloaded_file(video_id)
            if not path:
                fname = ydl.prepare_filename(info)
                path = Path(fname)
            if path and path.exists():
                return path, ""
            return None, "Fayl topilmadi"
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "login" in msg.lower() or "private" in msg.lower():
            return None, "Bu video private — yuklab bolmaydi"
        if "copyright" in msg.lower():
            return None, "Bu video mualliflik huquqi bilan himoyalangan"
        if "unavailable" in msg.lower():
            return None, "Bu video mavjud emas"
        return None, f"Yuklab bolmadi: {msg[:200]}"
    except Exception as e:
        return None, f"Xato: {str(e)[:200]}"


async def download_video(url: str, platform: str) -> tuple:
    loop = asyncio.get_event_loop()
    path, err = await loop.run_in_executor(None, download_sync, url, platform)
    if err:
        return None, err
    if path and path.stat().st_size > MAX_BYTES:
        path.unlink(missing_ok=True)
        return None, "Video 49MB dan katta — yuklab bolmaydi. Qisqaroq video yuboring."
    return path, ""


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men Video Yuklovchi Botman!\n\n"
        "Quyidagi saytlardan video havolasini yuboring:\n"
        "- Instagram (post, reel)\n"
        "- YouTube (video, Shorts)\n"
        "- TikTok\n\n"
        "Faqat havola yuboring — men yuklab beraman!"
    )


async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    platform = detect(url)

    if not platform:
        await update.message.reply_text(
            "Faqat Instagram, YouTube yoki TikTok havolasi yuboring!\n\n"
            "Misol:\n"
            "https://youtu.be/VIDEO_ID\n"
            "https://www.instagram.com/reel/ABC/\n"
            "https://www.tiktok.com/@user/video/123"
        )
        return

    status = await update.message.reply_text(f"{platform} videosi yuklanmoqda... kuting...")

    path, err = await download_video(url, platform)

    if err:
        await status.edit_text(f"Xato: {err}")
        return

    await status.edit_text("Yuborilmoqda...")

    try:
        with open(path, "rb") as f:
            await update.message.reply_video(
                video=f,
                caption=f"{platform} dan yuklandi!",
                supports_streaming=True,
                read_timeout=60,
                write_timeout=60,
            )
        await status.delete()
    except Exception as e:
        logger.error("Yuborishda xato: %s", e)
        await status.edit_text("Videoni yuborishda xato yuz berdi. Qayta urinib koring.")
    finally:
        if path and path.exists():
            path.unlink(missing_ok=True)


async def other(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Faqat Instagram, YouTube yoki TikTok havolasi yuboring!\n"
        "/start — boshlash"
    )


def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("BOT_TOKEN ornatilmagan!")
        return

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"https?://"), handle))
    app.add_handler(MessageHandler(filters.ALL, other))

    print("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

import os
import re
import asyncio
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import yt_dlp

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)
MAX_BYTES = 49 * 1024 * 1024

INSTAGRAM_RE = re.compile(r"(https?://)?(www\.)?instagram\.com/(p|reel|tv|stories)/[\w\-]+")
YOUTUBE_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[\w\-]+")
TIKTOK_RE = re.compile(r"(https?://)?(www\.|vm\.)?tiktok\.com/[\S]+")

def detect(url):
    if INSTAGRAM_RE.search(url): return "Instagram"
    if YOUTUBE_RE.search(url): return "YouTube"
    if TIKTOK_RE.search(url): return "TikTok"
    return None

def download_sync(url, platform):
    out = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")
    opts = {
        "outtmpl": out,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
    }
    if platform == "TikTok":
        opts["http_headers"] = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
        }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            vid_id = info.get("id", "")
            for f in DOWNLOAD_DIR.iterdir():
                if f.stem == vid_id:
                    return f, ""
            fname = Path(ydl.prepare_filename(info))
            if fname.exists():
                return fname, ""
            files = list(DOWNLOAD_DIR.iterdir())
            if files:
                return max(files, key=lambda f: f.stat().st_mtime), ""
            return None, "Fayl topilmadi"
    except Exception as e:
        msg = str(e)
        if "login" in msg.lower() or "private" in msg.lower():
            return None, "Bu video private"
        if "unavailable" in msg.lower():
            return None, "Bu video mavjud emas"
        return None, f"Xato: {msg[:150]}"

async def download_video(url, platform):
    loop = asyncio.get_event_loop()
    path, err = await loop.run_in_executor(None, download_sync, url, platform)
    if err:
        return None, err
    if not path or not path.exists():
        return None, "Fayl topilmadi"
    if path.stat().st_size > MAX_BYTES:
        path.unlink(missing_ok=True)
        return None, "Video 49MB dan katta"
    return path, ""

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men Video Yuklovchi Botman!\n\n"
        "YouTube, Instagram, TikTok havolalarini yuboring!\n"
        "Yuklab beraman!"
    )

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    platform = detect(url)
    if not platform:
        await update.message.reply_text("Faqat YouTube, Instagram yoki TikTok havolasi yuboring!")
        return
    status = await update.message.reply_text(f"{platform} yuklanmoqda... kuting...")
    path, err = await download_video(url, platform)
    if err:
        await status.edit_text(f"Xato: {err}")
        return
    await status.edit_text("Yuborilmoqda...")
    try:
        with open(path, "rb") as f:
            await update.message.reply_video(video=f, caption=f"{platform} dan yuklandi!", supports_streaming=True, read_timeout=120, write_timeout=120)
        await status.delete()
    except Exception as e:
        await status.edit_text(f"Yuborishda xato: {e}")
    finally:
        if path and path.exists():
            path.unlink(missing_ok=True)

async def other(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Faqat YouTube, Instagram yoki TikTok havolasi yuboring!")

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("BOT_TOKEN ornatilmagan!")
        return
    app = Application.builder().token(BOT_TOKEN).read_timeout(120).write_timeout(120).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"https?://"), handle))
    app.add_handler(MessageHandler(filters.ALL, other))
    print("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

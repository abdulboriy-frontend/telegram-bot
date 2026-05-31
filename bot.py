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

URL_RE = re.compile(r"https?://[\S]+")

def is_supported(url):
    patterns = [
        r"instagram\.com/(p|reel|tv|stories)/",
        r"(youtube\.com/(watch|shorts)|youtu\.be/)",
        r"tiktok\.com/",
        r"facebook\.com/",
        r"fb\.watch/",
    ]
    return any(re.search(p, url) for p in patterns)

def get_platform(url):
    if "instagram.com" in url: return "Instagram"
    if "youtube.com" in url or "youtu.be" in url: return "YouTube"
    if "tiktok.com" in url: return "TikTok"
    if "facebook.com" in url or "fb.watch" in url: return "Facebook"
    return "Video"

def download_sync(url):
    out = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")
    
    # YouTube uchun pytubefix ishlatamiz
    if "youtube.com" in url or "youtu.be" in url:
        try:
            from pytubefix import YouTube
            yt = YouTube(url)
            stream = (
                yt.streams
                .filter(progressive=True, file_extension="mp4")
                .order_by("resolution")
                .last()
            )
            if not stream:
                stream = yt.streams.filter(file_extension="mp4").first()
            if stream:
                path = Path(stream.download(output_path=str(DOWNLOAD_DIR)))
                if path.exists() and path.stat().st_size > 0:
                    return path, ""
        except Exception as e:
            logger.warning("pytubefix xato: %s", e)

    # Boshqa saytlar uchun yt-dlp
    format_list = [
        "best[ext=mp4][height<=480]",
        "best[ext=mp4][height<=720]",
        "best[ext=mp4]",
        "best",
    ]
    
    last_err = "Yuklab bolmadi"
    for fmt in format_list:
        try:
            opts = {
                "outtmpl": out,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "format": fmt,
                "prefer_ffmpeg": False,
                "postprocessors": [],
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
                },
            }
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                vid_id = info.get("id", "")
                for f in DOWNLOAD_DIR.iterdir():
                    if f.stem == vid_id:
                        return f, ""
                files = list(DOWNLOAD_DIR.iterdir())
                if files:
                    newest = max(files, key=lambda x: x.stat().st_mtime)
                    if newest.stat().st_size > 0:
                        return newest, ""
        except Exception as e:
            err = str(e)
            if "private" in err.lower() or "login" in err.lower():
                return None, "Bu video private — yuklab bolmaydi"
            if "unavailable" in err.lower():
                return None, "Bu video mavjud emas"
            last_err = err
            continue
    
    return None, last_err

async def download_video(url):
    loop = asyncio.get_event_loop()
    path, err = await loop.run_in_executor(None, download_sync, url)
    if err:
        return None, err
    if not path or not path.exists():
        return None, "Fayl topilmadi"
    if path.stat().st_size > MAX_BYTES:
        path.unlink(missing_ok=True)
        return None, "Video 49MB dan katta. Qisqaroq video yuboring."
    return path, ""

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men Video Yuklovchi Botman!\n\n"
        "Quyidagi saytlardan havola yuboring:\n"
        "• Instagram\n"
        "• YouTube\n"
        "• TikTok\n"
        "• Facebook\n\n"
        "Havola yuboring — yuklab beraman!"
    )

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if not URL_RE.search(text):
        await update.message.reply_text("Havola yuboring!")
        return
    
    url = URL_RE.search(text).group()
    
    if not is_supported(url):
        await update.message.reply_text(
            "Faqat Instagram, YouTube, TikTok yoki Facebook havolasi yuboring!"
        )
        return

    platform = get_platform(url)
    status = await update.message.reply_text(f"{platform} yuklanmoqda... kuting...")
    
    path, err = await download_video(url)

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
                read_timeout=120,
                write_timeout=120,
            )
        await status.delete()
    except Exception as e:
        logger.error("Yuborishda xato: %s", e)
        await status.edit_text("Yuborishda xato yuz berdi. Qayta urining.")
    finally:
        if path and path.exists():
            path.unlink(missing_ok=True)

async def other(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Havola yuboring!\n"
        "Instagram, YouTube, TikTok, Facebook"
    )

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("BOT_TOKEN ornatilmagan!")
        return
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(120)
        .write_timeout(120)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"https?://"), handle))
    app.add_handler(MessageHandler(filters.ALL, other))
    print("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

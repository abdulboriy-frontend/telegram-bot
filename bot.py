import os
import re
import asyncio
import logging
import urllib.request
import urllib.parse
import json
import tempfile
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import yt_dlp

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "83a6838fa5mshb0763b50baee654p1b6a32jsn083c8022623e")
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)
MAX_BYTES = 49 * 1024 * 1024

INSTAGRAM_RE = re.compile(r"(https?://)?(www\.)?instagram\.com/(p|reel|tv|stories)/[\w\-]+")
YOUTUBE_RE = re.compile(r"(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[\w\-]+")
TIKTOK_RE = re.compile(r"(https?://)?(www\.|vm\.)?tiktok\.com/[\S]+")
FACEBOOK_RE = re.compile(r"(https?://)?(www\.)?(facebook\.com|fb\.watch)/[\S]+")

def detect(url):
    if INSTAGRAM_RE.search(url): return "Instagram"
    if YOUTUBE_RE.search(url): return "YouTube"
    if TIKTOK_RE.search(url): return "TikTok"
    if FACEBOOK_RE.search(url): return "Facebook"
    return None

def download_file(url, filename):
    """URL dan fayl yuklab olish"""
    path = DOWNLOAD_DIR / filename
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        with open(path, "wb") as f:
            f.write(r.read())
    return path

def download_tiktok_api(url):
    """RapidAPI orqali TikTok video yuklash"""
    try:
        encoded_url = urllib.parse.quote(url, safe="")
        api_url = f"https://tiktok-scraper7.p.rapidapi.com/video/info?url={encoded_url}"
        
        headers = {
            "x-rapidapi-host": "tiktok-scraper7.p.rapidapi.com",
            "x-rapidapi-key": RAPIDAPI_KEY,
        }
        
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        
        if not data.get("data"):
            return None, "Video topilmadi"
        
        video_data = data["data"]
        
        # Watermarksiz video URL
        video_url = (
            video_data.get("play") or
            video_data.get("wmplay") or
            video_data.get("download_addr", {}).get("url_list", [None])[0]
        )
        
        if not video_url:
            return None, "Video URL topilmadi"
        
        path = download_file(video_url, "tiktok_video.mp4")
        return path, ""
        
    except Exception as e:
        logger.error("TikTok API xato: %s", e)
        return None, str(e)

def download_youtube(url):
    """pytubefix orqali YouTube video yuklash"""
    try:
        from pytubefix import YouTube
        yt = YouTube(url)
        stream = yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").last()
        if not stream:
            stream = yt.streams.filter(file_extension="mp4").first()
        if stream:
            path = Path(stream.download(output_path=str(DOWNLOAD_DIR)))
            if path.exists() and path.stat().st_size > 0:
                return path, ""
    except Exception as e:
        logger.warning("pytubefix xato: %s", e)
    return None, "YouTube yuklab bolmadi"

def download_ytdlp(url, platform):
    """yt-dlp orqali video yuklash"""
    out = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")
    formats = ["best[ext=mp4][height<=480]", "best[ext=mp4]", "best"]
    
    headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"}
    
    for fmt in formats:
        try:
            opts = {
                "outtmpl": out,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "format": fmt,
                "prefer_ffmpeg": False,
                "postprocessors": [],
                "http_headers": headers,
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
            if "private" in err.lower(): return None, "Bu video private"
            if "unavailable" in err.lower(): return None, "Bu video mavjud emas"
            continue
    return None, "Yuklab bolmadi"

def download_sync(url, platform):
    if platform == "TikTok":
        path, err = download_tiktok_api(url)
        if not err and path:
            return path, ""
        return download_ytdlp(url, platform)
    elif platform == "YouTube":
        path, err = download_youtube(url)
        if not err and path:
            return path, ""
        return download_ytdlp(url, platform)
    else:
        return download_ytdlp(url, platform)

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
        "Salom! Video Yuklovchi Bot!\n\n"
        "Quyidagilardan havola yuboring:\n"
        "• Instagram\n"
        "• YouTube\n"
        "• TikTok\n"
        "• Facebook\n\n"
        "Havola yuboring — yuklab beraman!"
    )

async def handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    platform = detect(url)
    if not platform:
        await update.message.reply_text("Faqat Instagram, YouTube, TikTok yoki Facebook havolasi yuboring!")
        return

    status = await update.message.reply_text(f"{platform} yuklanmoqda... kuting...")
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
                read_timeout=120,
                write_timeout=120,
            )
        await status.delete()
    except Exception as e:
        logger.error("Yuborishda xato: %s", e)
        await status.edit_text("Yuborishda xato. Qayta urining.")
    finally:
        if path and path.exists():
            path.unlink(missing_ok=True)

async def other(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Instagram, YouTube, TikTok yoki Facebook havolasi yuboring!")

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

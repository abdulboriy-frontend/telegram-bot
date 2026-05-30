import os
import re
import asyncio
import logging
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Config ─────────────────────────────────────────────────────────────────
BOT_TOKEN = "8004189168:AAF4PVlvLwv9VQgUL_XDtEzX2HzesIBBp-c"
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Max file size Telegram allows via bot (50 MB)
MAX_FILE_MB = 50
MAX_FILE_BYTES = MAX_FILE_MB * 1024 * 1024

# ─── URL helpers ─────────────────────────────────────────────────────────────
INSTAGRAM_RE = re.compile(
    r"(https?://)?(www\.)?instagram\.com/(p|reel|tv|stories)/[\w\-]+"
)
YOUTUBE_RE = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[\w\-]+"
)


def detect_platform(url: str) -> str | None:
    if INSTAGRAM_RE.search(url):
        return "instagram"
    if YOUTUBE_RE.search(url):
        return "youtube"
    return None


# ─── Downloader ──────────────────────────────────────────────────────────────
def get_ydl_opts(platform: str, output_path: str) -> dict:
    common = {
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    if platform == "instagram":
        return {
            **common,
            # Best video ≤ 720p to keep file size down
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
            "merge_output_format": "mp4",
        }
    else:  # youtube
        return {
            **common,
            "format": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
            "merge_output_format": "mp4",
        }


async def download_video(url: str, platform: str) -> tuple[Path | None, str]:
    """Download video. Returns (file_path, error_message)."""
    output_template = str(DOWNLOAD_DIR / "%(id)s.%(ext)s")
    opts = get_ydl_opts(platform, output_template)

    loop = asyncio.get_event_loop()

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # yt-dlp may change extension after merge
            base = Path(filename).stem
            for f in DOWNLOAD_DIR.iterdir():
                if f.stem == base and f.suffix in (".mp4", ".mkv", ".webm"):
                    return f
            return Path(filename)

    try:
        file_path = await loop.run_in_executor(None, _download)
        if not file_path.exists():
            return None, "❌ Fayl topilmadi. URL to'g'riligini tekshiring."
        if file_path.stat().st_size > MAX_FILE_BYTES:
            file_path.unlink(missing_ok=True)
            return None, f"❌ Video juda katta ({MAX_FILE_MB} MB dan oshadi). Qisqaroq video yuboring."
        return file_path, ""
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Private" in msg or "login" in msg.lower():
            return None, "🔒 Bu video private — yuklab bo'lmaydi."
        if "Unsupported URL" in msg:
            return None, "❌ Bu URL qo'llab-quvvatlanmaydi."
        return None, f"❌ Yuklab bo'lmadi:\n<code>{msg[:200]}</code>"
    except Exception as e:
        logger.exception("Unexpected error downloading %s", url)
        return None, f"❌ Kutilmagan xato: {e}"


# ─── Handlers ────────────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 <b>Salom! Men Video Yuklovchi Botman</b>\n\n"
        "📌 <b>Nima qila olaman?</b>\n"
        "• Instagram post / reel / video havolasini yuboring\n"
        "• YouTube video / shorts havolasini yuboring\n\n"
        "⚡ Men videoni yuklab, sizga yuboraman!\n\n"
        "🔗 Faqat havola yuboring — boshqa narsa shart emas."
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 <b>Yordam</b>\n\n"
        "<b>Qo'llab-quvvatlanadigan saytlar:</b>\n"
        "✅ Instagram (post, reel, IGTV)\n"
        "✅ YouTube (video, Shorts)\n\n"
        "<b>Qanday ishlatish:</b>\n"
        "1. Video havolasini nusxalang\n"
        "2. Shu botga yuboring\n"
        "3. Biroz kuting — video keladi!\n\n"
        "<b>Cheklovlar:</b>\n"
        f"• Fayl hajmi {MAX_FILE_MB} MB dan oshmasligi kerak\n"
        "• Private videolar yuklanmaydi\n"
        "• Video sifati: 720p gacha"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def handle_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    platform = detect_platform(url)

    if not platform:
        await update.message.reply_text(
            "⚠️ Faqat <b>Instagram</b> yoki <b>YouTube</b> havolalarini yuboring!\n\n"
            "Misol:\n"
            "• <code>https://www.instagram.com/reel/ABC123/</code>\n"
            "• <code>https://youtu.be/dQw4w9WgXcQ</code>",
            parse_mode="HTML",
        )
        return

    icon = "📸" if platform == "instagram" else "▶️"
    name = "Instagram" if platform == "instagram" else "YouTube"

    status_msg = await update.message.reply_text(
        f"{icon} <b>{name}</b> videosi yuklanmoqda...\n⏳ Biroz kuting...",
        parse_mode="HTML",
    )

    file_path, error = await download_video(url, platform)

    if error:
        await status_msg.edit_text(error, parse_mode="HTML")
        return

    await status_msg.edit_text("📤 Telegram'ga yuborilmoqda...")

    try:
        with open(file_path, "rb") as video_file:
            caption = f"{icon} <b>{name}</b> dan yuklandi!\n🤖 @{ctx.bot.username}"
            await update.message.reply_video(
                video=video_file,
                caption=caption,
                parse_mode="HTML",
                supports_streaming=True,
            )
        await status_msg.delete()
    except Exception as e:
        logger.error("Send video error: %s", e)
        await status_msg.edit_text(
            "❌ Videoni yuborishda xato yuz berdi. Qayta urinib ko'ring.",
            parse_mode="HTML",
        )
    finally:
        if file_path and file_path.exists():
            file_path.unlink(missing_ok=True)


async def handle_other(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔗 Faqat <b>Instagram</b> yoki <b>YouTube</b> havolasini yuboring!\n"
        "/help — ko'proq ma'lumot",
        parse_mode="HTML",
    )


# ─── Main ────────────────────────────────────────────────────────────────────
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ BOT_TOKEN o'rnatilmagan! .env faylini to'ldiring.")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"https?://"), handle_url))
    app.add_handler(MessageHandler(filters.ALL, handle_other))

    print("🚀 Bot ishga tushdi! Ctrl+C bilan to'xtatish mumkin.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

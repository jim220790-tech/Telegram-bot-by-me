import logging
import os
import re
import http.server
import socketserver
import threading
import time
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from yt_dlp import YoutubeDL

# Configuration
TOKEN = os.environ.get('TOKEN', '8870862159:AAF3WlBNfgqejm4yPDeyGnrwjdIDkFGemCM')
AUDIO_DIR = 'downloads'
MAX_FILE_SIZE_MB = 50
REQUIRED_CHANNEL = '@Soulscript0'
CHANNEL_LINK = 'https://t.me/Soulscript0'

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ensure download directory exists
os.makedirs(AUDIO_DIR, exist_ok=True)

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user has joined the required channel."""
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error checking membership for user {user_id}: {e}")
        return False

async def send_join_message(update: Update) -> None:
    """Send a message asking the user to join the channel."""
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ I've Joined", callback_data="check_joined")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚠️ You must join our channel to use this bot.\n\n"
        f"👉 Join: {CHANNEL_LINK}\n\n"
        "After joining, tap the button below to verify.",
        reply_markup=reply_markup
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    if not await check_membership(update, context):
        await send_join_message(update)
        return

    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}!\n\n"
        "I'm a music downloader bot. Just send me a link and I'll download the audio for you.\n\n"
        "Supported links:\n"
        "• TikTok (tiktok.com, vt.tiktok.com, vm.tiktok.com)\n"
        "• YouTube (youtube.com, youtu.be)\n\n"
        "Just paste a link directly!"
    )

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, platform: str) -> None:
    """Download audio from a given URL and send it to the user."""
    message = update.message if update.message else update.callback_query.message

    await message.reply_text(f"Downloading audio from {platform}...")

    # Define options for yt-dlp
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(AUDIO_DIR, '%(title)s.%(ext)s'),
        'restrictfilenames': True,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024,
    }

    info = None
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            # yt-dlp might not always return mp3 extension directly
            base, ext = os.path.splitext(file_path)
            if ext != '.mp3':
                file_path = base + '.mp3'
            
            if not os.path.exists(file_path):
                await message.reply_text("Error: Downloaded file not found. It might have exceeded the file size limit.")
                logger.error(f"Downloaded file not found at {file_path} for URL: {url}")
                return

            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                await message.reply_text(f"The audio file exceeds the {MAX_FILE_SIZE_MB}MB limit and cannot be sent.")
            else:
                await message.reply_audio(audio=open(file_path, 'rb'), title=info.get('title', 'audio'), performer=info.get('artist', 'Unknown'))
                await message.reply_text("Audio sent successfully!")

            # Clean up
            os.remove(file_path)
            logger.info(f"Successfully sent and removed file: {file_path}")

    except Exception as e:
        logger.error(f"Error downloading audio from {url}: {e}")
        await message.reply_text("An error occurred while downloading the audio. Please try again later.")
    finally:
        # Clean up any leftover files
        for f in os.listdir(AUDIO_DIR):
            try:
                os.remove(os.path.join(AUDIO_DIR, f))
            except:
                pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages - detect TikTok or YouTube links."""
    if update.message.text and not update.message.text.startswith('/'):
        # Check channel membership first
        if not await check_membership(update, context):
            await send_join_message(update)
            return

        text = update.message.text.strip()
        # Auto-detect TikTok links
        if re.match(r'^(https?://)?(www\.|vt\.|vm\.)?tiktok\.com/.+$', text):
            await download_audio(update, context, text, "TikTok")
        # Auto-detect YouTube links
        elif re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$', text):
            await download_audio(update, context, text, "YouTube")
        else:
            await update.message.reply_text(
                "Please send me a valid TikTok or YouTube link.\n\n"
                "Examples:\n"
                "• https://vt.tiktok.com/ZSCpetre9/\n"
                "• https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )

async def tiktok_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download audio from a TikTok URL."""
    if not await check_membership(update, context):
        await send_join_message(update)
        return

    if not context.args:
        await update.message.reply_text("Please provide a TikTok URL. Example: /tiktok https://vt.tiktok.com/ZSCpetre9/")
        return
    url = context.args[0]
    if not re.match(r'^(https?://)?(www\.|vt\.|vm\.)?tiktok\.com/.+$', url):
        await update.message.reply_text("Please provide a valid TikTok URL.")
        return
    await download_audio(update, context, url, "TikTok")

async def youtube_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download audio from a YouTube URL."""
    if not await check_membership(update, context):
        await send_join_message(update)
        return

    if not context.args:
        await update.message.reply_text("Please provide a YouTube URL. Example: /youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        return
    url = context.args[0]
    if not re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$', url):
        await update.message.reply_text("Please provide a valid YouTube URL.")
        return
    await download_audio(update, context, url, "YouTube")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == "check_joined":
        user_id = query.from_user.id
        try:
            member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                await query.message.edit_text("✅ Verified! You can now use the bot. Just send me a TikTok or YouTube link.")
            else:
                await query.answer("❌ You haven't joined the channel yet. Please join first.", show_alert=True)
        except Exception as e:
            logger.error(f"Error verifying membership: {e}")
            await query.answer("❌ Could not verify. Make sure you joined the channel.", show_alert=True)

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP server logs

def start_http_server():
    PORT = 10000
    with socketserver.TCPServer(("0.0.0.0", PORT), HealthCheckHandler) as httpd:
        logger.info(f"Serving HTTP health check on port {PORT}")
        httpd.serve_forever()

def self_ping():
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
    if not RENDER_EXTERNAL_URL:
        logger.warning("RENDER_EXTERNAL_URL not set. Self-ping disabled.")
        return

    ping_url = f"{RENDER_EXTERNAL_URL}/health"
    logger.info(f"Starting self-ping to {ping_url}")
    while True:
        try:
            response = requests.get(ping_url, timeout=5)
            logger.info(f"Self-ping: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Self-ping failed: {e}")
        time.sleep(10 * 60)  # Ping every 10 minutes

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("tiktok", tiktok_command))
    application.add_handler(CommandHandler("youtube", youtube_command))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start HTTP server in a separate thread
    http_server_thread = threading.Thread(target=start_http_server, daemon=True)
    http_server_thread.start()

    # Start self-ping in a separate thread
    self_ping_thread = threading.Thread(target=self_ping, daemon=True)
    self_ping_thread.start()

    # Run the bot
    logger.info("Bot started.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

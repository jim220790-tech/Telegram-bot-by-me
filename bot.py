import logging
import os
import re
import asyncio
import http.server
import socketserver
import threading
import time
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from yt_dlp import YoutubeDL

# Configuration
TOKEN = os.environ.get('TOKEN', '8870862159:AAF3WlBNfgqejm4yPDeyGnrwjdIDkFGemCM')
AUDIO_DIR = 'downloads'
MAX_FILE_SIZE_MB = 50

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ensure download directory exists
os.makedirs(AUDIO_DIR, exist_ok=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}!\n\n"\
        "I'm a music bot. You can send me a song name to search on YouTube, "\
        "or use the following commands:\n\n"\
        "/search <query> - Search for music on YouTube\n"\
        "/youtube <url> - Download audio from a YouTube video\n"\
        "/tiktok <url> - Download audio from a TikTok video"
    )

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for music on YouTube and return results with inline buttons."""
    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text("Please provide a search query. Example: /search Never Gonna Give You Up")
        return

    await update.message.reply_text(f"Searching YouTube for '{query}'...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'default_search': 'ytsearch5',
        'quiet': True,
        'extract_flat': True, # Only extract basic info, not the full video
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                results = info['entries']
                if not results:
                    await update.message.reply_text("No results found.")
                    return

                keyboard = []
                for entry in results:
                    if entry and 'url' in entry and 'title' in entry:
                        video_url = entry['url']
                        title = entry['title']
                        keyboard.append([InlineKeyboardButton(title, callback_data=f"download_yt:{video_url}")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("Please select a song to download:", reply_markup=reply_markup)
            else:
                await update.message.reply_text("Could not find any videos for your query.")
    except Exception as e:
        logger.error(f"Error during YouTube search for '{query}': {e}")
        await update.message.reply_text("An error occurred during the search. Please try again later.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages - detect TikTok links or search YouTube."""
    if update.message.text and not update.message.text.startswith('/'):
        text = update.message.text.strip()
        # Auto-detect TikTok links
        if re.match(r'^(https?://)?(www\.|vt\.|vm\.)?tiktok\.com/.+$', text):
            context.args = [text]
            await tiktok_command(update, context)
        # Auto-detect YouTube links
        elif re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$', text):
            context.args = [text]
            await youtube_command(update, context)
        else:
            context.args = text.split()
            await search(update, context)

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str, platform: str) -> None:
    """Download audio from a given URL and send it to the user."""
    message = update.message if update.message else update.callback_query.message
    chat_id = message.chat_id

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
        'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024, # Convert MB to bytes
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            # yt-dlp might not always return mp3 extension directly, so we need to adjust
            base, ext = os.path.splitext(file_path)
            if ext != '.mp3':
                file_path = base + '.mp3'
            
            if not os.path.exists(file_path):
                await message.reply_text("Error: Downloaded file not found. It might have exceeded the file size limit or an issue occurred during conversion.")
                logger.error(f"Downloaded file not found at {file_path} for URL: {url}")
                return

            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                await message.reply_text(f"The audio file exceeds the {MAX_FILE_SIZE_MB}MB limit and cannot be sent.")
                logger.warning(f"File {file_path} exceeded size limit ({file_size} bytes) for URL: {url}")
            else:
                await message.reply_audio(audio=open(file_path, 'rb'), title=info.get('title', 'audio'), performer=info.get('artist', 'Unknown'))
                await message.reply_text("Audio sent successfully!")

            # Clean up the downloaded file
            os.remove(file_path)
            logger.info(f"Successfully sent and removed file: {file_path}")

    except Exception as e:
        logger.error(f"Error downloading audio from {url}: {e}")
        await message.reply_text("An error occurred while downloading the audio. It might be too large or unavailable. Please try again later.")
    finally:
        # Ensure any partially downloaded files are cleaned up
        for f in os.listdir(AUDIO_DIR):
            if f.startswith(info.get('_filename', '')) and not f.endswith('.mp3'): # Clean up temporary files
                os.remove(os.path.join(AUDIO_DIR, f))

async def youtube_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download audio from a YouTube URL."""
    if not context.args:
        await update.message.reply_text("Please provide a YouTube URL. Example: /youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        return
    url = context.args[0]
    if not re.match(r'^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.+$', url):
        await update.message.reply_text("Please provide a valid YouTube URL.")
        return
    await download_audio(update, context, url, "YouTube")

async def tiktok_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download audio from a TikTok URL."""
    if not context.args:
        await update.message.reply_text("Please provide a TikTok URL. Example: /tiktok https://vt.tiktok.com/ZSCpetre9/")
        return
    url = context.args[0]
    if not re.match(r'^(https?://)?(www\.|vt\.|vm\.)?tiktok\.com/.+$', url):
        await update.message.reply_text("Please provide a valid TikTok URL.")
        return
    await download_audio(update, context, url, "TikTok")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith('download_yt:'):
        url = data.split(':', 1)[1]
        await download_audio(update, context, url, "YouTube")

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Bot is running')
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')

def start_http_server():
    PORT = 10000
    Handler = HealthCheckHandler
    with socketserver.TCPServer(("0.0.0.0", PORT), Handler) as httpd:
        logger.info(f"Serving HTTP health check on port {PORT}")
        httpd.serve_forever()

def self_ping():
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
    if not RENDER_EXTERNAL_URL:
        logger.warning("RENDER_EXTERNAL_URL environment variable not set. Self-ping will not work.")
        return

    ping_url = f"{RENDER_EXTERNAL_URL}/health"
    logger.info(f"Starting self-ping to {ping_url}")
    while True:
        try:
            response = requests.get(ping_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Self-ping successful: {response.status_code}")
            else:
                logger.warning(f"Self-ping failed with status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Self-ping request failed: {e}")
        time.sleep(10 * 60) # Ping every 10 minutes

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("youtube", youtube_command))
    application.add_handler(CommandHandler("tiktok", tiktok_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button))

    # Start HTTP server in a separate thread
    http_server_thread = threading.Thread(target=start_http_server, daemon=True)
    http_server_thread.start()

    # Start self-ping in a separate thread
    self_ping_thread = threading.Thread(target=self_ping, daemon=True)
    self_ping_thread.start()

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot started. Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    from telegram.ext import CallbackQueryHandler # Import here to avoid circular dependency if main is imported elsewhere
    main()

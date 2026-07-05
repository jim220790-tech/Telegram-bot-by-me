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
DOWNLOAD_DIR = 'downloads'
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
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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
    message = update.message if update.message else update.callback_query.message
    await message.reply_text(
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
        f"Hi {user.mention_html()}! 🎵\n\n"
        "I'm a music & video downloader bot.\n\n"
        "🔹 <b>TikTok Download:</b>\n"
        "Paste a TikTok link → choose Video or Audio\n\n"
        "🔹 <b>Song Search:</b>\n"
        "Type any song name → I'll find it for you\n\n"
        "Just send me a TikTok link or a song name!"
    )

async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """Search for a song using Deezer API and show results."""
    message = update.message if update.message else update.callback_query.message
    await message.reply_text(f"🔍 Searching for '{query}'...")

    try:
        # Use Deezer public API (no auth required)
        response = requests.get(
            f"https://api.deezer.com/search",
            params={'q': query, 'limit': 5},
            timeout=10
        )
        data = response.json()

        if 'data' not in data or not data['data']:
            await message.reply_text("❌ No results found. Try a different search term.")
            return

        keyboard = []
        for track in data['data']:
            title = track.get('title', 'Unknown')
            artist = track.get('artist', {}).get('name', 'Unknown')
            track_id = track.get('id')
            display = f"🎵 {title} - {artist}"
            if len(display) > 50:
                display = display[:47] + "..."
            callback_data = f"deezer:{track_id}"
            keyboard.append([InlineKeyboardButton(display, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text("🎶 Select a song to download:", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error searching for '{query}': {e}")
        await message.reply_text("❌ An error occurred during search. Please try again later.")

async def download_deezer_track(update: Update, context: ContextTypes.DEFAULT_TYPE, track_id: str) -> None:
    """Download a track preview from Deezer."""
    query = update.callback_query
    message = query.message

    # Delete the song list message
    try:
        await message.delete()
    except:
        pass

    chat_id = query.message.chat_id

    try:
        # Get track info from Deezer
        response = requests.get(f"https://api.deezer.com/track/{track_id}", timeout=10)
        track = response.json()

        title = track.get('title', 'Unknown')
        artist = track.get('artist', {}).get('name', 'Unknown')
        preview_url = track.get('preview')

        if not preview_url:
            await context.bot.send_message(chat_id, "❌ No preview available for this track.")
            return

        await context.bot.send_message(chat_id, f"🎵 Downloading: {title} - {artist}...")

        # Download the preview MP3
        file_path = os.path.join(DOWNLOAD_DIR, f"{title}_{artist}.mp3".replace('/', '_').replace(' ', '_'))
        audio_response = requests.get(preview_url, timeout=30)

        if audio_response.status_code == 200:
            with open(file_path, 'wb') as f:
                f.write(audio_response.content)

            await context.bot.send_audio(
                chat_id=chat_id,
                audio=open(file_path, 'rb'),
                title=title,
                performer=artist
            )

            os.remove(file_path)
        else:
            await context.bot.send_message(chat_id, "❌ Could not download the track.")

    except Exception as e:
        logger.error(f"Error downloading Deezer track {track_id}: {e}")
        await context.bot.send_message(chat_id, "❌ An error occurred while downloading. Please try again later.")
    finally:
        cleanup_downloads()

async def download_tiktok_audio(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    """Download audio from a TikTok URL."""
    message = update.message if update.message else update.callback_query.message
    await message.reply_text("🎵 Downloading TikTok audio...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'restrictfilenames': True,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            base, ext = os.path.splitext(file_path)
            if ext != '.mp3':
                file_path = base + '.mp3'

            if not os.path.exists(file_path):
                await message.reply_text("❌ Error: Could not download audio.")
                return

            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                await message.reply_text(f"❌ File exceeds {MAX_FILE_SIZE_MB}MB limit.")
            else:
                await message.reply_audio(
                    audio=open(file_path, 'rb'),
                    title=info.get('title', 'TikTok Audio'),
                    performer=info.get('artist', info.get('uploader', 'Unknown'))
                )

            os.remove(file_path)

    except Exception as e:
        logger.error(f"Error downloading TikTok audio from {url}: {e}")
        await message.reply_text("❌ An error occurred while downloading. Please try again later.")
    finally:
        cleanup_downloads()

async def download_tiktok_video(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    """Download video from a TikTok URL."""
    message = update.message if update.message else update.callback_query.message
    await message.reply_text("🎬 Downloading TikTok video...")

    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'restrictfilenames': True,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': MAX_FILE_SIZE_MB * 1024 * 1024,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            if not os.path.exists(file_path):
                await message.reply_text("❌ Error: Could not download video.")
                return

            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                await message.reply_text(f"❌ Video exceeds {MAX_FILE_SIZE_MB}MB limit.")
            else:
                await message.reply_video(
                    video=open(file_path, 'rb'),
                    caption=info.get('title', 'TikTok Video'),
                    supports_streaming=True
                )

            os.remove(file_path)

    except Exception as e:
        logger.error(f"Error downloading TikTok video from {url}: {e}")
        await message.reply_text("❌ An error occurred while downloading. Please try again later.")
    finally:
        cleanup_downloads()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages."""
    if update.message.text and not update.message.text.startswith('/'):
        if not await check_membership(update, context):
            await send_join_message(update)
            return

        text = update.message.text.strip()
        # Auto-detect TikTok links
        if re.match(r'^(https?://)?(www\.|vt\.|vm\.)?tiktok\.com/.+$', text):
            # Show options: video or audio
            # Store URL in bot_data to avoid callback_data length limit
            url_key = f"tt_{update.effective_user.id}_{int(time.time())}"
            context.bot_data[url_key] = text
            keyboard = [
                [InlineKeyboardButton("🎬 Video", callback_data=f"ttvideo:{url_key}")],
                [InlineKeyboardButton("🎵 Audio Only", callback_data=f"ttaudio:{url_key}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Choose download format:", reply_markup=reply_markup)
        else:
            # Treat as song search
            await search_song(update, context, text)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /search command."""
    if not await check_membership(update, context):
        await send_join_message(update)
        return

    query = ' '.join(context.args)
    if not query:
        await update.message.reply_text("Please provide a song name. Example: /search Blue")
        return
    await search_song(update, context, query)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "check_joined":
        user_id = query.from_user.id
        try:
            member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                await query.message.edit_text("✅ Verified! You can now use the bot.\n\nSend me a TikTok link or a song name to search.")
            else:
                await query.answer("❌ You haven't joined the channel yet.", show_alert=True)
        except Exception as e:
            logger.error(f"Error verifying membership: {e}")
            await query.answer("❌ Could not verify. Make sure you joined the channel.", show_alert=True)

    elif data.startswith("ttvideo:"):
        url_key = data[8:]
        url = context.bot_data.get(url_key)
        if url:
            await download_tiktok_video(update, context, url)
        else:
            await query.message.reply_text("❌ Link expired. Please send the TikTok link again.")

    elif data.startswith("ttaudio:"):
        url_key = data[8:]
        url = context.bot_data.get(url_key)
        if url:
            await download_tiktok_audio(update, context, url)
        else:
            await query.message.reply_text("❌ Link expired. Please send the TikTok link again.")

    elif data.startswith("deezer:"):
        track_id = data[7:]
        await download_deezer_track(update, context, track_id)

def cleanup_downloads():
    """Clean up any leftover files in download directory."""
    for f in os.listdir(DOWNLOAD_DIR):
        try:
            os.remove(os.path.join(DOWNLOAD_DIR, f))
        except:
            pass

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')

    def log_message(self, format, *args):
        pass

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
        time.sleep(10 * 60)

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_command))
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

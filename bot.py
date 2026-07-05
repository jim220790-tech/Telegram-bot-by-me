import logging
import os
import re
import json
import http.server
import socketserver
import threading
import time
import requests
from datetime import time as dtime, timezone, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from yt_dlp import YoutubeDL

# Configuration
TOKEN = os.environ.get('TOKEN', '8870862159:AAF3WlBNfgqejm4yPDeyGnrwjdIDkFGemCM')
DOWNLOAD_DIR = 'downloads'
MAX_FILE_SIZE_MB = 50
REQUIRED_CHANNEL = '@Soulscript16'
CHANNEL_LINK = 'https://t.me/Soulscript16'
OWNER_ID = 8731823643  # Owner's Telegram user ID

# Myanmar timezone (GMT+6:30)
MMR_TZ = timezone(timedelta(hours=6, minutes=30))

# File to store users and quote
USERS_FILE = 'users.json'
QUOTE_FILE = 'quote.json'

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- User tracking ---
def load_users() -> set:
    """Load user IDs from file."""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_users(users: set):
    """Save user IDs to file."""
    with open(USERS_FILE, 'w') as f:
        json.dump(list(users), f)

def add_user(user_id: int):
    """Add a user to the tracked users."""
    users = load_users()
    users.add(user_id)
    save_users(users)

# --- Quote management ---
def get_quote() -> str:
    """Get the current quote."""
    if os.path.exists(QUOTE_FILE):
        try:
            with open(QUOTE_FILE, 'r') as f:
                data = json.load(f)
                return data.get('quote', '')
        except:
            return ''
    return ''

def set_quote(quote: str):
    """Set the current quote."""
    with open(QUOTE_FILE, 'w') as f:
        json.dump({'quote': quote}, f)

# --- Broadcast function ---
async def broadcast_quote(context: ContextTypes.DEFAULT_TYPE):
    """Send the current quote to all users."""
    quote = get_quote()
    if not quote:
        logger.info("No quote set, skipping broadcast.")
        return

    users = load_users()
    success = 0
    failed = 0
    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"✨ Daily Quote ✨\n\n{quote}")
            success += 1
        except Exception as e:
            logger.error(f"Failed to send quote to {user_id}: {e}")
            failed += 1

    logger.info(f"Broadcast complete: {success} sent, {failed} failed")

    # Notify owner
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"📊 Broadcast Report:\n✅ Sent: {success}\n❌ Failed: {failed}"
        )
    except:
        pass

# --- Membership check ---
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

# --- Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the command /start is issued."""
    if not await check_membership(update, context):
        await send_join_message(update)
        return

    # Track user
    add_user(update.effective_user.id)

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

async def setquote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner command to set the daily quote."""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can use this command.")
        return

    quote_text = ' '.join(context.args)
    if not quote_text:
        await update.message.reply_text("Usage: /setquote <your quote text>")
        return

    set_quote(quote_text)

    keyboard = [
        [InlineKeyboardButton("📤 Send to All Users Now", callback_data="broadcast_now")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"✅ Quote set!\n\n\"{quote_text}\"\n\n"
        "This will be sent to all users at 7:30 PM daily.\n"
        "Or tap the button below to send it now:",
        reply_markup=reply_markup
    )

async def viewquote_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner command to view the current quote."""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can use this command.")
        return

    quote = get_quote()
    if quote:
        keyboard = [
            [InlineKeyboardButton("📤 Send to All Users Now", callback_data="broadcast_now")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"📝 Current quote:\n\n\"{quote}\"\n\n"
            f"👥 Total users: {len(load_users())}",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text("No quote set. Use /setquote <text> to set one.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner command to see bot stats."""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Only the owner can use this command.")
        return

    users = load_users()
    quote = get_quote()
    await update.message.reply_text(
        f"📊 Bot Stats:\n\n"
        f"👥 Total users: {len(users)}\n"
        f"📝 Current quote: {quote if quote else 'Not set'}"
    )

# --- Song search ---
async def search_song(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    """Search for a song using Deezer API and show results."""
    message = update.message if update.message else update.callback_query.message
    await message.reply_text(f"🔍 Searching for '{query}'...")

    try:
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
        response = requests.get(f"https://api.deezer.com/track/{track_id}", timeout=10)
        track = response.json()

        title = track.get('title', 'Unknown')
        artist = track.get('artist', {}).get('name', 'Unknown')
        preview_url = track.get('preview')

        if not preview_url:
            await context.bot.send_message(chat_id, "❌ No preview available for this track.")
            return

        await context.bot.send_message(chat_id, f"🎵 Downloading: {title} - {artist}...")

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

# --- TikTok downloads ---
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

# --- Message handler ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages."""
    if update.message.text and not update.message.text.startswith('/'):
        if not await check_membership(update, context):
            await send_join_message(update)
            return

        # Track user
        add_user(update.effective_user.id)

        text = update.message.text.strip()
        # Auto-detect TikTok links
        if re.match(r'^(https?://)?(www\.|vt\.|vm\.)?tiktok\.com/.+$', text):
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

# --- Button handler ---
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
                add_user(user_id)
                await query.message.edit_text("✅ Verified! You can now use the bot.\n\nSend me a TikTok link or a song name to search.")
            else:
                await query.answer("❌ You haven't joined the channel yet.", show_alert=True)
        except Exception as e:
            logger.error(f"Error verifying membership: {e}")
            await query.answer("❌ Could not verify. Make sure you joined the channel.", show_alert=True)

    elif data == "broadcast_now":
        # Only owner can broadcast
        if query.from_user.id != OWNER_ID:
            await query.answer("❌ Only the owner can do this.", show_alert=True)
            return

        await query.message.edit_text("📤 Broadcasting quote to all users...")
        await broadcast_quote(context)

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

# --- Utilities ---
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

# --- Scheduled job ---
async def daily_quote_job(context: ContextTypes.DEFAULT_TYPE):
    """Job that runs daily at 7:30 PM Myanmar time to send quote."""
    logger.info("Running daily quote broadcast...")
    await broadcast_quote(context)

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("setquote", setquote_command))
    application.add_handler(CommandHandler("viewquote", viewquote_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Schedule daily quote at 7:30 PM Myanmar time (GMT+6:30)
    job_queue = application.job_queue
    target_time = dtime(hour=19, minute=30, second=0, tzinfo=MMR_TZ)
    job_queue.run_daily(daily_quote_job, time=target_time)
    logger.info(f"Daily quote scheduled at 7:30 PM Myanmar time")

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

import os
import uuid
import requests
import asyncio
import threading
import logging
import time
import socket
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, NetworkError, BadRequest, Forbidden

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fixed token value
TOKEN = "0022294985:AAEbYrY6lFeEvy_f3m4eIP7xzi7JNYiK"
app = Flask(__name__)

# Ensure temp folder exists
TEMP_FOLDER = os.path.join(os.getcwd(), "temp_folder")
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

@app.route('/')
def index():
    return 'Bot Is Alive'

@app.route('/health', methods=['GET'])
def health_check():
    # Check if port is bound
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('0.0.0.0', 5000))
        sock.close()
        return jsonify(status='OK' if result == 0 else 'DOWN'), 200
    except:
        return jsonify(status='ERROR'), 500

class MediaNotFoundError(Exception):
    """Custom exception for media not found"""
    pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        keyboard = [[InlineKeyboardButton("Join channel", url="https://t.me/Opleech_WD")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_photo(
            photo="https://i.ibb.co/txvvB9m/image.jpg",
            caption="Greetings! Send me any public Instagram link and I'll download the media for you 😊",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Start command error: {e}")
        await update.message.reply_text("🚨 Sorry, I encountered an error. Please try again later.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for Telegram bot"""
    error = context.error
    logger.error(f"Global error: {error}", exc_info=True)
    
    if update and isinstance(update, Update) and update.message:
        if isinstance(error, MediaNotFoundError):
            await update.message.reply_text("❌ No media found at this URL. Please try another Instagram link.")
        elif isinstance(error, (Forbidden, BadRequest)):
            await update.message.reply_text("🔒 Bot authentication failed. Please contact support.")
        else:
            await update.message.reply_text("⚠️ An unexpected error occurred. Please try again later.")

def fetch_instagram_media(url: str) -> dict:
    """Fetch Instagram media data from API with proper error handling"""
    api_url = "https://social-media-api-chi.vercel.app/api/instagram"
    params = {"url": url}
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle API error responses
        if data.get("status") == "error" or "error" in data:
            error_msg = data.get("message", data.get("error", "Unknown API error"))
            logger.error(f"API returned error: {error_msg}")
            raise MediaNotFoundError(f"API error: {error_msg}")
        
        # Validate successful response
        if data.get("status") == "success" and data.get("downloads"):
            return data
        
        # Handle empty downloads case
        if not data.get("downloads"):
            raise MediaNotFoundError("API returned no media items")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        raise MediaNotFoundError("Service unavailable. Please try again later.")
    except ValueError as e:
        logger.error(f"Invalid API response: {e}")
        logger.debug(f"API response: {response.text[:500]}")
        raise MediaNotFoundError("Invalid response from service.")
    
    raise MediaNotFoundError("Failed to fetch media from API")

def download_media(url: str, file_path: str) -> None:
    """Download media from URL to file path"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/"
    }
    
    try:
        response = requests.get(url, stream=True, headers=headers, timeout=30)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if chunk: f.write(chunk)
        
        if os.path.getsize(file_path) == 0:
            raise ValueError("Downloaded file is empty")
            
    except Exception as e:
        logger.error(f"Media download failed: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise MediaNotFoundError("Failed to download media")

async def handle_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    if "instagram.com" not in user_text:
        await update.message.reply_text("⚠️ Please send a valid Instagram link")
        return
    
    logger.info(f"Processing request from {update.effective_user.id} for URL: {user_text}")
    processing_msg = await update.message.reply_text("⏳ Processing your Instagram link...")
    temp_files = []
    
    try:
        # Fetch media data from API
        api_data = fetch_instagram_media(user_text)
        success_count = 0
        
        for media in api_data["downloads"]:
            try:
                # Create temp file path
                ext = ".mp4" if media["type"] == "video" else ".jpg"
                temp_file = os.path.join(TEMP_FOLDER, f"{uuid.uuid4().hex}{ext}")
                temp_files.append(temp_file)
                
                # Download media
                await asyncio.to_thread(download_media, media["url"], temp_file)
                
                # Prepare response
                caption = "Here's your Instagram video 🎬" if media["type"] == "video" else "Here's your Instagram photo 📸"
                keyboard = [[InlineKeyboardButton("Join channel", url="https://t.me/Opleech_WD")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Send media to user
                with open(temp_file, "rb") as media_file:
                    if media["type"] == "video":
                        await update.message.reply_video(
                            media_file,
                            caption=caption,
                            reply_markup=reply_markup,
                            supports_streaming=True
                        )
                    else:
                        await update.message.reply_photo(
                            media_file,
                            caption=caption,
                            reply_markup=reply_markup
                        )
                success_count += 1
            except Exception as e:
                logger.error(f"Media processing error: {e}")
        
        # Handle partial success
        if success_count == 0:
            raise MediaNotFoundError("Failed to process media. Please try again later.")
        elif success_count < len(api_data["downloads"]):
            await update.message.reply_text(f"⚠️ Processed {success_count}/{len(api_data['downloads'])} items")
                
    except MediaNotFoundError as e:
        logger.warning(f"Media not found: {e}")
        await update.message.reply_text(f"❌ {e}")
    except Exception as e:
        logger.error(f"Handle Instagram error: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Processing error. Please try again.")
    finally:
        # Cleanup processing message
        try:
            await context.bot.delete_message(processing_msg.chat_id, processing_msg.message_id)
        except:
            pass
        
        # Cleanup temporary files
        for file in temp_files:
            try:
                if os.path.exists(file): os.remove(file)
            except:
                pass

def run_flask():
    """Run Flask with production server"""
    from waitress import serve
    logger.info("Starting Flask server on port 5000")
    serve(app, host='0.0.0.0', port=5000)

def run_bot():
    """Run the Telegram bot"""
    try:
        logger.info(f"Starting bot with token: {TOKEN[:5]}...{TOKEN[-3:]}")
        app_telegram = ApplicationBuilder().token(TOKEN).build()
        
        # Register handlers
        app_telegram.add_handler(CommandHandler("start", start))
        app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_instagram))
        app_telegram.add_error_handler(error_handler)
        
        logger.info("Starting bot polling")
        app_telegram.run_polling()
        
    except TelegramError as e:
        logger.critical(f"Telegram error: {e}")
        os._exit(1)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        os._exit(1)

def wait_for_port(port=5000, timeout=15):
    """Wait until a port is available"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex(('0.0.0.0', port)) == 0:
                    logger.info(f"Port {port} is bound")
                    return True
        except:
            pass
        time.sleep(0.5)
    return False

if __name__ == '__main__':
    # Start Flask in background
    threading.Thread(target=run_flask, daemon=True).start()
    
    # Wait for port to bind
    logger.info("Waiting for port 5000")
    if wait_for_port():
        logger.info("Flask ready. Starting bot")
    else:
        logger.error("Flask didn't start in time")
    
    # Start bot
    run_bot()

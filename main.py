import logging
import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import asyncio
import yt_dlp

# --- Configuration ---
BOT_TOKEN = "7598946589:AAHNOuwJps7wSn26HiNlUSqggBY_28ChnxU" # Replace with your actual bot token
DOWNLOAD_DIR = "downloads"  # Directory to save downloaded files

# Create the downloads directory if it doesn't exist
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Helper function for downloading media ---
async def download_media(url: str, chat_id: int) -> tuple[str | None, str | None]:
    """Downloads media from a given URL using yt-dlp."""
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
        'noplaylist': True,  # Prevent downloading entire playlists
        'quiet': True,
        'no_warnings': True,
        'restrictfilenames': True, # Keep filenames clean
        'merge_output_format': 'mp4',
        'progress_hooks': [], # Add progress hooks if you want to show download progress
        'postprocessors': [{
            'key': 'FFmpegMetadata',
            'add_metadata': False,
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            # Get the actual downloaded file path
            # yt-dlp returns the info dictionary after download.
            # 'filepath' key is usually where it saves the file.
            filepath = ydl.prepare_filename(info_dict)
            return filepath, info_dict.get('title', 'Unknown Title')
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download failed for URL {url}: {e}")
        return None, None
    except Exception as e:
        logger.error(f"An unexpected error occurred during download for URL {url}: {e}")
        return None, None

# --- Telegram Bot Handlers ---

async def start(update: Update, context) -> None:
    """Sends a message when the command /start is issued."""
    await update.message.reply_text(
        'Hello! Send me a link to a YouTube video, Instagram reel/post, or other supported media, and I will try to send you the file.'
    )

async def help_command(update: Update, context) -> None:
    """Sends a message when the command /help is issued."""
    await update.message.reply_text(
        'Just send me a public link to a video or image from websites like YouTube, Instagram, etc., and I will try to download and send it to you. '
        'Please ensure the link is publicly accessible.'
    )

async def handle_message(update: Update, context) -> None:
    """Handles incoming messages and attempts to download media from URLs."""
    url = update.message.text
    chat_id = update.message.chat_id

    # Simple regex to check for common URL patterns
    if not re.match(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', url):
        await update.message.reply_text("That doesn't look like a valid URL. Please send a direct link to the media.")
        return

    message = await update.message.reply_text("Got your link! Attempting to download, please wait...")

    file_path, title = await download_media(url, chat_id)

    if file_path and os.path.exists(file_path):
        try:
            # Check file size before sending
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if file_size_mb > 50: # Telegram's direct file upload limit is 50MB for bots
                await message.edit_text(
                    f"File '{title}' downloaded successfully, but it's too large ({file_size_mb:.2f} MB) to send directly via Telegram bot. "
                    "You might need to use a cloud storage solution or a different method for large files."
                )
                os.remove(file_path) # Clean up large file
                return

            with open(file_path, 'rb') as f:
                if file_path.endswith(('.mp4', '.mov', '.avi', '.mkv')):
                    await context.bot.send_video(
                        chat_id=chat_id,
                        video=f,
                        caption=f"Here's your video: '{title}'",
                        supports_streaming=True # For larger videos, allows streaming
                    )
                elif file_path.endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=f,
                        caption=f"Here's your image: '{title}'"
                    )
                elif file_path.endswith(('.mp3', '.wav', '.ogg')):
                    await context.bot.send_audio(
                        chat_id=chat_id,
                        audio=f,
                        caption=f"Here's your audio: '{title}'"
                    )
                else:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        caption=f"Here's your file: '{title}' (unrecognized format, sent as document)"
                    )
            await message.delete() # Delete the "downloading" message
            os.remove(file_path) # Clean up the downloaded file
            logger.info(f"Successfully sent and deleted file: {file_path}")

        except Exception as e:
            logger.error(f"Error sending file to Telegram: {e}")
            await message.edit_text(f"An error occurred while sending the file: {e}")
            if os.path.exists(file_path):
                os.remove(file_path) # Clean up on send failure
    else:
        await message.edit_text(
            "Sorry, I couldn't download the media from that link. "
            "It might be a private post, an unsupported website, or there was an issue with the download."
        )


async def error_handler(update: Update, context) -> None:
    """Log the error and send a telegram message to notify the user."""
    logger.warning(f'Update "{update}" caused error "{context.error}"')
    if update.message:
        await update.message.reply_text(
            "Oops! Something went wrong. Please try again or check the link."
        )

# --- Main function to run the bot ---
def main() -> None:
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler
    application.add_error_handler(error_handler)

    # Start the Bot
    logger.info("Bot started polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

import os
import logging
from dotenv import load_dotenv

import google.generativeai as genai

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("7347273926:AAH2M1LDzSQoibf1VH0BMQrkFSfcX6qedlo")
GEMINI_API_KEY = os.getenv("AIzaSyCT_hRShR7x-luU4bMCNCTj9vunETcOqGk")
GEMINI_MODEL_NAME = "gemini-1.5-flash" # Or "gemini-2.0-flash" if available and preferred, check Google AI Studio documentation for latest model names

# Initialize Gemini
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file. Please set it up.")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL_NAME)

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hello {user.mention_html()}! I'm your Gemini-powered chatbot. Ask me anything!"
    )
    logger.info(f"User {user.full_name} started the bot.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message when the /help command is issued."""
    help_text = """
    *Welcome to the Gemini AI Chatbot!*

    I can answer your questions and generate creative text using Google's Gemini 1.5 Flash model.

    *Commands:*
    /start - Start interacting with the bot.
    /help - Show this help message.
    /clear - Clear the current conversation history (for multi-turn conversations).

    *How to use:*
    Just type your question or prompt, and I'll do my best to respond!
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")
    logger.info(f"User {update.effective_user.full_name} requested help.")

async def clear_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears the conversation history for a user."""
    # This example doesn't store per-user history, but if you were building
    # a more complex multi-turn bot, you would reset the history here.
    await update.message.reply_text("Conversation history cleared!")
    logger.info(f"User {update.effective_user.full_name} cleared conversation.")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming text messages and sends them to Gemini for a response."""
    user_message = update.message.text
    user = update.effective_user

    logger.info(f"User {user.full_name} ({user.id}) sent message: {user_message}")

    try:
        # Show typing status
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Send message to Gemini 2.0 Flash
        # For multi-turn conversations, you would maintain a chat session.
        # This example treats each message as a new prompt for simplicity,
        # but you can implement conversation history using `model.start_chat()`.
        response = model.generate_content(user_message)

        # Get the text response
        gemini_response_text = response.text

        # Send the Gemini response back to Telegram
        await update.message.reply_text(gemini_response_text)
        logger.info(f"Sent response to user {user.full_name}: {gemini_response_text[:100]}...") # Log first 100 chars
    except Exception as e:
        logger.error(f"Error processing message from {user.full_name}: {e}")
        await update.message.reply_text("Oops! Something went wrong while processing your request. Please try again later.")

def main() -> None:
    """Starts the bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in .env file. Please set it up.")

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_conversation))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))

    logger.info("Bot is polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

# main.py

import logging
from telegram import Update, ForceReply, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# IMPORTANT: Replace 'YOUR_BOT_TOKEN' with your actual bot token provided by BotFather.
# The user provided token is 7598946589:AAHNOuwJps7wSn26HiNlUSqggBY_28ChnxU
BOT_TOKEN = "7598946589:AAHNOuwJps7wSn26HiNlUSqggBY_28ChnxU"

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I'm your group management bot. "
        "Use /help to see what I can do.",
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message with available commands when the command /help is issued."""
    help_text = """
Hello! I'm a simple group management bot. Here's what I can do:

* /start - Greet me!
* /help - Show this help message.
* /kick <reply to a message> - Kick the replied user from the group.
    (Note: I need to be an admin in the group with 'Ban users' permission for this to work.)

More features will be added soon!
    """
    await update.message.reply_text(help_text)

async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kicks a user from the group. Requires bot to be an admin with ban rights."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type == 'group' and not chat.type == 'supergroup':
        await message.reply_text("This command can only be used in a group.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message of the user you want to kick.")
        return

    user_to_kick = message.reply_to_message.from_user

    # Check if the bot has admin rights to kick users
    bot_member = await chat.get_member(context.bot.id)
    if not bot_member.status == ChatMember.ADMINISTRATOR or not bot_member.can_restrict_members:
        await message.reply_text(
            "I need to be an admin in this group with 'Ban users' permission to kick members."
        )
        return

    try:
        await chat.ban_member(user_to_kick.id)
        await message.reply_text(f"Successfully kicked {user_to_kick.full_name}.")
        logger.info(f"Kicked user {user_to_kick.id} from chat {chat.id}")
    except Exception as e:
        await message.reply_text(f"Failed to kick {user_to_kick.full_name}. Error: {e}")
        logger.error(f"Error kicking user {user_to_kick.id} from chat {chat.id}: {e}")

async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets new members when they join the group."""
    for member in update.message.new_chat_members:
        if not member.is_bot:
            await update.message.reply_text(f"Welcome, {member.full_name}! 👋")
            logger.info(f"Welcomed new member {member.id} to chat {update.effective_chat.id}")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echoes the user message. This is just for demonstration."""
    # This handler is intentionally kept simple for a group management bot.
    # You might want to remove or modify it based on your bot's purpose.
    # await update.message.reply_text(update.message.text)
    pass # Do nothing for now, as it's a group management bot.

def main() -> None:
    """Start the bot."""
    # Create the Application and pass your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # On different commands - add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("kick", kick_user))

    # On new members joining - add handler
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))

    # On non-command messages - echo the message (optional, usually not needed for management bots)
    # application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot started! Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

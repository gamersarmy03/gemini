# main.py

import logging
from telegram import Update, ForceReply, ChatMember, ChatMemberAdministrator, ChatMemberOwner
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ChatMemberHandler
import datetime
import re
import json

# Firebase Imports (handled by Canvas environment)
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from firebase_admin.auth import get_auth, signInAnonymously, signInWithCustomToken, on_auth_state_changed
except ImportError:
    # This block will execute if firebase_admin is not installed.
    # It's here for local testing guidance, but in Canvas, it should always be available.
    print("firebase_admin library not found. Please install it: pip install firebase-admin")
    firebase_admin = None
    firestore = None
    credentials = None

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# IMPORTANT: Replace 'YOUR_BOT_TOKEN' with your actual bot token provided by BotFather.
# The user provided token is 7598946589:AAHNOuwJps7wSn26HiNlUSqggBY_28ChnxU
BOT_TOKEN = "7598946589:AAHNOuwJps7wSn26HiNlUSqggBY_28ChnxU"

# Global Firestore instances
db = None
auth = None
app_id = None # Will be set from __app_id

# --- Utility Functions ---

async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Checks if a user is an administrator in the current chat."""
    chat = update.effective_chat
    if not chat.type in ['group', 'supergroup']:
        return False

    try:
        chat_member = await chat.get_member(user_id)
        return chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception as e:
        logger.error(f"Error checking admin status for user {user_id} in chat {chat.id}: {e}")
        return False

async def get_bot_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    """Gets the bot's permissions in the current chat."""
    chat = update.effective_chat
    if not chat.type in ['group', 'supergroup']:
        return {}

    try:
        bot_member = await chat.get_member(context.bot.id)
        if isinstance(bot_member, ChatMemberAdministrator) or isinstance(bot_member, ChatMemberOwner):
            return {
                'is_admin': True,
                'can_restrict_members': bot_member.can_restrict_members,
                'can_delete_messages': bot_member.can_delete_messages,
                'can_pin_messages': bot_member.can_pin_messages,
                'can_promote_members': bot_member.can_promote_members, # Not used yet but good to have
            }
        return {'is_admin': False}
    except Exception as e:
        logger.error(f"Error getting bot permissions in chat {chat.id}: {e}")
        return {'is_admin': False}

def parse_duration(duration_str: str) -> datetime.timedelta | None:
    """Parses a duration string (e.g., '1h', '30m', '1d') into a timedelta object."""
    match = re.match(r'^(\d+)([smhd])$', duration_str)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)

    if unit == 's':
        return datetime.timedelta(seconds=value)
    elif unit == 'm':
        return datetime.timedelta(minutes=value)
    elif unit == 'h':
        return datetime.timedelta(hours=value)
    elif unit == 'd':
        return datetime.timedelta(days=value)
    return None

# --- Firestore Operations ---

async def get_group_settings(chat_id: int) -> dict:
    """Retrieves group settings (welcome, rules) from Firestore."""
    if not db or not app_id: return {}
    doc_ref = db.collection('artifacts').document(app_id).collection('public').document('data').collection('group_settings').document(str(chat_id))
    try:
        doc = await doc_ref.get()
        return doc.to_dict() if doc.exists else {}
    except Exception as e:
        logger.error(f"Error getting group settings for {chat_id}: {e}")
        return {}

async def set_group_setting(chat_id: int, key: str, value: str | None) -> None:
    """Sets a specific group setting in Firestore."""
    if not db or not app_id: return
    doc_ref = db.collection('artifacts').document(app_id).collection('public').document('data').collection('group_settings').document(str(chat_id))
    try:
        if value is None:
            # If value is None, remove the field
            update_data = {key: firestore.DELETE_FIELD}
            await doc_ref.update(update_data)
        else:
            await doc_ref.set({key: value}, merge=True)
    except Exception as e:
        logger.error(f"Error setting group setting {key} for {chat_id}: {e}")

async def get_user_warnings(chat_id: int, user_id: int) -> list:
    """Retrieves a user's warnings from Firestore."""
    if not db or not app_id: return []
    doc_ref = db.collection('artifacts').document(app_id).collection('public').document('data').collection('group_warnings').document(str(chat_id)).collection('users').document(str(user_id))
    try:
        doc = await doc_ref.get()
        data = doc.to_dict()
        return data.get('warnings', []) if data else []
    except Exception as e:
        logger.error(f"Error getting warnings for user {user_id} in chat {chat_id}: {e}")
        return []

async def update_user_warnings(chat_id: int, user_id: int, warnings: list) -> None:
    """Updates a user's warnings in Firestore."""
    if not db or not app_id: return
    doc_ref = db.collection('artifacts').document(app_id).collection('public').document('data').collection('group_warnings').document(str(chat_id)).collection('users').document(str(user_id))
    try:
        await doc_ref.set({'warnings': warnings}, merge=True)
    except Exception as e:
        logger.error(f"Error updating warnings for user {user_id} in chat {chat_id}: {e}")

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.mention_html()}! I'm your advanced group management bot. "
        "Use /help to see what I can do.",
        reply_markup=ForceReply(selective=True),
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message with available commands when the command /help is issued."""
    help_text = """
Hello! I'm an advanced group management bot. Here's what I can do:

*General Commands:*
* /start - Greet me!
* /help - Show this help message.
* /about - Learn more about me.
* /id [reply to a message] - Get user/chat ID.
* /echo <text> - I will echo your text.

*Moderation Commands (Admin Only):*
* /warn <reply to a message> - Warn the replied user.
* /unwarn <reply to a message> - Remove a warn from the replied user.
* /warnings <reply to a message> - Check a user's warnings.
* /mute <reply to a message> [duration e.g., 1h, 30m, 1d] - Mute a user.
* /unmute <reply to a message> - Unmute a user.
* /kick <reply to a message> - Kick the replied user.
* /ban <reply to a message> - Ban the replied user permanently.
* /unban <user_id> - Unban a user by their ID.
* /del [reply to a message] - Delete the replied message.
* /pin <reply to a message> - Pin the replied message.
* /unpin - Unpin the current pinned message.

*Group Management Commands (Admin Only):*
* /setwelcome <text> - Set a custom welcome message for new members.
* /delwelcome - Delete the custom welcome message.
* /rules <text> - Set group rules.
* /rules - Get current group rules.
* /info <reply to a message> - Get user info.
* /chatinfo - Get current chat info.
* /report <reply to a message> - Report a message to admins.

Note: For moderation commands to work, I need to be an admin in the group with necessary permissions!
    """
    await update.message.reply_text(help_text)

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides information about the bot."""
    about_text = """
I am an advanced Telegram group management bot, built to help you moderate and manage your groups effectively.
My features include moderation tools (warn, mute, ban), group settings (welcome, rules), and utility commands.

I am constantly being improved with new functionalities!
Developed by Gemini Bot.
    """
    await update.message.reply_text(about_text)

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gets the ID of the user, replied user, or chat."""
    message = update.effective_message
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    text = f"Your User ID: `{user_id}`\n"
    if message.reply_to_message:
        replied_user = message.reply_to_message.from_user
        text += f"Replied User ID: `{replied_user.id}` (`{replied_user.full_name}`)\n"
    text += f"Chat ID: `{chat_id}`"
    await message.reply_text(text, parse_mode='MarkdownV2')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echoes the user's message."""
    if not context.args:
        await update.message.reply_text("Please provide text to echo. E.g., `/echo Hello World!`")
        return
    await update.message.reply_text(" ".join(context.args))

async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Kicks a user from the group. Requires bot to be an admin with ban rights."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message of the user you want to kick.")
        return

    user_to_kick = message.reply_to_message.from_user
    if user_to_kick.id == context.bot.id:
        await message.reply_text("I cannot kick myself!")
        return
    if await is_user_admin(update, context, user_to_kick.id):
        await message.reply_text("I cannot kick another admin.")
        return

    bot_perms = await get_bot_permissions(update, context)
    if not bot_perms.get('can_restrict_members'):
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

async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Warns a user and stores the warning."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message of the user you want to warn.")
        return

    user_to_warn = message.reply_to_message.from_user
    if user_to_warn.id == context.bot.id:
        await message.reply_text("I cannot warn myself!")
        return
    if await is_user_admin(update, context, user_to_warn.id):
        await message.reply_text("I cannot warn another admin.")
        return

    reason = " ".join(context.args) if context.args else "No reason specified."
    
    warnings = await get_user_warnings(chat.id, user_to_warn.id)
    warnings.append({
        'timestamp': datetime.datetime.now().isoformat(),
        'admin_id': update.effective_user.id,
        'reason': reason
    })
    await update_user_warnings(chat.id, user_to_warn.id, warnings)

    await message.reply_text(f"{user_to_warn.full_name} has been warned. Total warnings: {len(warnings)}.\nReason: {reason}")
    logger.info(f"Warned user {user_to_warn.id} in chat {chat.id}. Reason: {reason}")

async def unwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Removes a warning from a user."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message of the user you want to unwarn.")
        return

    user_to_unwarn = message.reply_to_message.from_user
    warnings = await get_user_warnings(chat.id, user_to_unwarn.id)

    if not warnings:
        await message.reply_text(f"{user_to_unwarn.full_name} has no warnings.")
        return

    # Remove the most recent warning
    warnings.pop()
    await update_user_warnings(chat.id, user_to_unwarn.id, warnings)

    await message.reply_text(f"One warning removed for {user_to_unwarn.full_name}. Total warnings: {len(warnings)}.")
    logger.info(f"Unwarned user {user_to_unwarn.id} in chat {chat.id}.")

async def check_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Checks and displays a user's warnings."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message of the user whose warnings you want to check.")
        return

    user_to_check = message.reply_to_message.from_user
    warnings = await get_user_warnings(chat.id, user_to_check.id)

    if not warnings:
        await message.reply_text(f"{user_to_check.full_name} has no warnings.")
        return

    response_text = f"Warnings for {user_to_check.full_name} ({len(warnings)} total):\n"
    for i, warning in enumerate(warnings):
        response_text += (
            f"{i+1}. Reason: {warning.get('reason', 'N/A')}\n"
            f"   Admin: {warning.get('admin_id', 'N/A')}\n"
            f"   Time: {warning.get('timestamp', 'N/A')}\n"
        )
    await message.reply_text(response_text)
    logger.info(f"Checked warnings for user {user_to_check.id} in chat {chat.id}.")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mutes a user for a specified duration or indefinitely."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message of the user you want to mute.")
        return

    user_to_mute = message.reply_to_message.from_user
    if user_to_mute.id == context.bot.id:
        await message.reply_text("I cannot mute myself!")
        return
    if await is_user_admin(update, context, user_to_mute.id):
        await message.reply_text("I cannot mute another admin.")
        return

    bot_perms = await get_bot_permissions(update, context)
    if not bot_perms.get('can_restrict_members'):
        await message.reply_text(
            "I need to be an admin in this group with 'Ban users' permission to mute members."
        )
        return

    duration = None
    if context.args:
        duration_str = context.args[0]
        duration = parse_duration(duration_str)
        if not duration:
            await message.reply_text("Invalid duration format. Use e.g., `1h`, `30m`, `1d`.")
            return

    try:
        # Permissions to send messages, add polls, send media, etc.
        permissions = {
            'can_send_messages': False,
            'can_send_audios': False,
            'can_send_documents': False,
            'can_send_photos': False,
            'can_send_videos': False,
            'can_send_video_notes': False,
            'can_send_voice_notes': False,
            'can_send_polls': False,
            'can_send_other_messages': False, # This usually covers stickers, gifs, etc.
            'can_add_web_page_previews': False,
            'can_change_info': False,
            'can_invite_users': False,
            'can_pin_messages': False,
        }

        if duration:
            until_date = datetime.datetime.now() + duration
            await chat.restrict_member(user_to_mute.id, permissions, until_date=until_date)
            await message.reply_text(f"Successfully muted {user_to_mute.full_name} for {duration_str}.")
            logger.info(f"Muted user {user_to_mute.id} in chat {chat.id} for {duration_str}")
        else:
            await chat.restrict_member(user_to_mute.id, permissions)
            await message.reply_text(f"Successfully muted {user_to_mute.full_name} indefinitely.")
            logger.info(f"Muted user {user_to_mute.id} in chat {chat.id} indefinitely.")

    except Exception as e:
        await message.reply_text(f"Failed to mute {user_to_mute.full_name}. Error: {e}")
        logger.error(f"Error muting user {user_to_mute.id} in chat {chat.id}: {e}")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unmutes a user."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message of the user you want to unmute.")
        return

    user_to_unmute = message.reply_to_message.from_user
    if user_to_unmute.id == context.bot.id:
        await message.reply_text("I cannot unmute myself!")
        return

    bot_perms = await get_bot_permissions(update, context)
    if not bot_perms.get('can_restrict_members'):
        await message.reply_text(
            "I need to be an admin in this group with 'Ban users' permission to unmute members."
        )
        return

    try:
        # Re-enable all permissions for sending messages, etc.
        permissions = {
            'can_send_messages': True,
            'can_send_audios': True,
            'can_send_documents': True,
            'can_send_photos': True,
            'can_send_videos': True,
            'can_send_video_notes': True,
            'can_send_voice_notes': True,
            'can_send_polls': True,
            'can_send_other_messages': True,
            'can_add_web_page_previews': True,
            'can_change_info': True,
            'can_invite_users': True,
            'can_pin_messages': True,
        }
        await chat.restrict_member(user_to_unmute.id, permissions)
        await message.reply_text(f"Successfully unmuted {user_to_unmute.full_name}.")
        logger.info(f"Unmuted user {user_to_unmute.id} in chat {chat.id}")
    except Exception as e:
        await message.reply_text(f"Failed to unmute {user_to_unmute.full_name}. Error: {e}")
        logger.error(f"Error unmuting user {user_to_unmute.id} in chat {chat.id}: {e}")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bans a user from the group permanently."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message of the user you want to ban.")
        return

    user_to_ban = message.reply_to_message.from_user
    if user_to_ban.id == context.bot.id:
        await message.reply_text("I cannot ban myself!")
        return
    if await is_user_admin(update, context, user_to_ban.id):
        await message.reply_text("I cannot ban another admin.")
        return

    bot_perms = await get_bot_permissions(update, context)
    if not bot_perms.get('can_restrict_members'):
        await message.reply_text(
            "I need to be an admin in this group with 'Ban users' permission to ban members."
        )
        return

    try:
        await chat.ban_member(user_to_ban.id)
        await message.reply_text(f"Successfully banned {user_to_ban.full_name}.")
        logger.info(f"Banned user {user_to_ban.id} from chat {chat.id}")
    except Exception as e:
        await message.reply_text(f"Failed to ban {user_to_ban.full_name}. Error: {e}")
        logger.error(f"Error banning user {user_to_ban.id} from chat {chat.id}: {e}")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unbans a user by their ID."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not context.args:
        await message.reply_text("Please provide the user ID to unban. E.g., `/unban 123456789`")
        return

    try:
        user_id_to_unban = int(context.args[0])
    except ValueError:
        await message.reply_text("Invalid user ID provided. Please provide a numeric ID.")
        return

    bot_perms = await get_bot_permissions(update, context)
    if not bot_perms.get('can_restrict_members'):
        await message.reply_text(
            "I need to be an admin in this group with 'Ban users' permission to unban members."
        )
        return

    try:
        # Use only_if_banned=True to prevent errors if user is not banned
        await chat.unban_member(user_id_to_unban, only_if_banned=True)
        await message.reply_text(f"Successfully unbanned user with ID `{user_id_to_unban}`.")
        logger.info(f"Unbanned user {user_id_to_unban} from chat {chat.id}")
    except Exception as e:
        await message.reply_text(f"Failed to unban user with ID `{user_id_to_unban}`. Error: {e}")
        logger.error(f"Error unbanning user {user_id_to_unban} from chat {chat.id}: {e}")

async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes the replied-to message."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message you want to delete.")
        return

    bot_perms = await get_bot_permissions(update, context)
    if not bot_perms.get('can_delete_messages'):
        await message.reply_text(
            "I need to be an admin in this group with 'Delete messages' permission to delete messages."
        )
        return

    try:
        await message.reply_to_message.delete()
        await message.delete() # Delete the command message itself
        logger.info(f"Deleted message {message.reply_to_message.message_id} in chat {chat.id}")
    except Exception as e:
        await message.reply_text(f"Failed to delete message. Error: {e}")
        logger.error(f"Error deleting message in chat {chat.id}: {e}")

async def pin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pins the replied-to message."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message you want to pin.")
        return

    bot_perms = await get_bot_permissions(update, context)
    if not bot_perms.get('can_pin_messages'):
        await message.reply_text(
            "I need to be an admin in this group with 'Pin messages' permission to pin messages."
        )
        return

    try:
        await message.reply_to_message.pin(disable_notification=False)
        await message.reply_text("Message pinned successfully!")
        logger.info(f"Pinned message {message.reply_to_message.message_id} in chat {chat.id}")
    except Exception as e:
        await message.reply_text(f"Failed to pin message. Error: {e}")
        logger.error(f"Error pinning message in chat {chat.id}: {e}")

async def unpin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unpins the current pinned message."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    bot_perms = await get_bot_permissions(update, context)
    if not bot_perms.get('can_pin_messages'):
        await message.reply_text(
            "I need to be an admin in this group with 'Pin messages' permission to unpin messages."
        )
        return

    try:
        await chat.unpin_all_messages() # Unpins all, or use chat.unpin_message() for specific
        await message.reply_text("All messages unpinned successfully!")
        logger.info(f"Unpinned messages in chat {chat.id}")
    except Exception as e:
        await message.reply_text(f"Failed to unpin messages. Error: {e}")
        logger.error(f"Error unpinning messages in chat {chat.id}: {e}")

async def set_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets a custom welcome message for the group."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not context.args:
        await message.reply_text("Please provide the welcome message text. E.g., `/setwelcome Welcome {username}!`")
        await message.reply_text(
            "You can use `{username}` to insert the new member's name and `{chatname}` for the group name."
        )
        return

    welcome_text = " ".join(context.args)
    await set_group_setting(chat.id, 'welcome_message', welcome_text)
    await message.reply_text("Welcome message set successfully!")
    logger.info(f"Set welcome message for chat {chat.id}")

async def delete_welcome_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Deletes the custom welcome message."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    await set_group_setting(chat.id, 'welcome_message', None) # Set to None to delete
    await message.reply_text("Welcome message deleted successfully!")
    logger.info(f"Deleted welcome message for chat {chat.id}")

async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greets new members using a custom welcome message if set."""
    chat = update.effective_chat
    settings = await get_group_settings(chat.id)
    welcome_message_template = settings.get('welcome_message')

    for member in update.message.new_chat_members:
        if not member.is_bot:
            if welcome_message_template:
                # Replace placeholders
                welcome_text = welcome_message_template.replace("{username}", member.full_name).replace("{chatname}", chat.title)
                await update.message.reply_text(welcome_text)
            else:
                await update.message.reply_text(f"Welcome, {member.full_name}! 👋")
            logger.info(f"Welcomed new member {member.id} to chat {chat.id}")

async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sets the group rules."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not await is_user_admin(update, context, update.effective_user.id):
        await message.reply_text("You must be an admin to use this command.")
        return

    if not context.args:
        await message.reply_text("Please provide the rules text. E.g., `/rules Be respectful!`")
        return

    rules_text = " ".join(context.args)
    await set_group_setting(chat.id, 'rules_message', rules_text)
    await message.reply_text("Group rules set successfully!")
    logger.info(f"Set rules for chat {chat.id}")

async def get_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the current group rules."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    settings = await get_group_settings(chat.id)
    rules_message = settings.get('rules_message')

    if rules_message:
        await message.reply_text(f"Group Rules:\n\n{rules_message}")
    else:
        await message.reply_text("No group rules have been set yet. Admins can set them using `/rules <text>`.")
    logger.info(f"Displayed rules for chat {chat.id}")

async def get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gets detailed information about a user."""
    message = update.effective_message
    
    if not message.reply_to_message:
        await message.reply_text("Please reply to the message of the user whose info you want to get.")
        return

    user_info = message.reply_to_message.from_user
    chat_member = None
    if update.effective_chat.type in ['group', 'supergroup']:
        try:
            chat_member = await update.effective_chat.get_member(user_info.id)
        except Exception:
            pass # User might have left

    info_text = (
        f"**User Info:**\n"
        f"ID: `{user_info.id}`\n"
        f"First Name: `{user_info.first_name}`\n"
    )
    if user_info.last_name:
        info_text += f"Last Name: `{user_info.last_name}`\n"
    if user_info.username:
        info_text += f"Username: `@{user_info.username}`\n"
    info_text += f"Is Bot: `{user_info.is_bot}`\n"
    if chat_member:
        info_text += f"Status in chat: `{chat_member.status.capitalize()}`\n"
        if isinstance(chat_member, ChatMemberAdministrator) or isinstance(chat_member, ChatMemberOwner):
            info_text += f"Can restrict members: `{chat_member.can_restrict_members}`\n"
            info_text += f"Can delete messages: `{chat_member.can_delete_messages}`\n"
            info_text += f"Can invite users: `{chat_member.can_invite_users}`\n"
            info_text += f"Can pin messages: `{chat_member.can_pin_messages}`\n"

    await message.reply_text(info_text, parse_mode='MarkdownV2')
    logger.info(f"Displayed info for user {user_info.id} in chat {update.effective_chat.id}")

async def get_chat_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gets detailed information about the current chat."""
    chat = update.effective_chat
    message = update.effective_message

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group or supergroup.")
        return

    info_text = (
        f"**Chat Info:**\n"
        f"ID: `{chat.id}`\n"
        f"Type: `{chat.type}`\n"
        f"Title: `{chat.title}`\n"
    )
    if chat.username:
        info_text += f"Username: `@{chat.username}`\n"
    if chat.description:
        info_text += f"Description: `{chat.description}`\n"
    
    # Try to get member count if available (can be None for some chat types or privacy settings)
    try:
        member_count = await chat.get_member_count()
        info_text += f"Member Count: `{member_count}`\n"
    except Exception:
        pass # Ignore if cannot get member count

    await message.reply_text(info_text, parse_mode='MarkdownV2')
    logger.info(f"Displayed chat info for chat {chat.id}")

async def report_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reports a message to group administrators."""
    message = update.effective_message
    chat = update.effective_chat

    if not chat.type in ['group', 'supergroup']:
        await message.reply_text("This command can only be used in a group.")
        return

    if not message.reply_to_message:
        await message.reply_text("Please reply to the message you want to report.")
        return
    
    reporter = update.effective_user
    reported_message = message.reply_to_message
    reported_user = reported_message.from_user

    # Get chat administrators
    admins = await chat.get_administrators()
    admin_ids = [admin.user.id for admin in admins]
    admin_mentions = []
    for admin in admins:
        if not admin.user.is_bot: # Don't mention other bots
            admin_mentions.append(admin.user.mention_html())

    report_text = (
        f"🚨 **New Report in {chat.title}** 🚨\n\n"
        f"**Reported by:** {reporter.full_name} (`{reporter.id}`)\n"
        f"**Reported user:** {reported_user.full_name} (`{reported_user.id}`)\n"
        f"**Message:** [Link to message]({reported_message.link})\n"
        f"**Reason:** {' '.join(context.args) if context.args else 'No reason provided.'}\n\n"
        f"Admins: {' '.join(admin_mentions) if admin_mentions else 'No human admins to notify.'}"
    )

    # Send report to admins who are not the reporter and not the bot itself
    for admin_id in admin_ids:
        if admin_id != reporter.id and admin_id != context.bot.id:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=report_text,
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.warning(f"Could not send report to admin {admin_id}: {e}")
    
    await message.reply_text("Message reported to administrators.")
    logger.info(f"Message {reported_message.message_id} reported by {reporter.id} in chat {chat.id}")


# --- Main Function ---

def main() -> None:
    """Start the bot."""
    global db, auth, app_id

    # Initialize Firebase if not already initialized
    # These global variables are provided by the Canvas environment.
    # We must ensure they are accessed safely.
    firebase_config = json.loads(typeof __firebase_config !== 'undefined' ? __firebase_config : '{}')
    app_id = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id'

    if not firebase_admin._apps:
        try:
            # The 'options' dictionary is part of the firebase_admin.credentials.Certificate class
            # but here we initialize with the firebaseConfig directly, which firebase_admin.initializeApp expects.
            # No need for a separate credentials object if firebaseConfig directly contains project_id etc.
            firebase_admin.initializeApp(firebase_config)
            db = firestore.client()
            auth = get_auth()
            logger.info("Firebase initialized.")

            # Authenticate anonymously or with custom token
            # This is crucial for Firestore security rules to allow access
            async def auth_listener(user_record):
                if user_record:
                    logger.info(f"Authenticated as user: {user_record.uid}")
                else:
                    logger.info("Authentication state changed: user signed out or not authenticated.")

            # Await the initial authentication for the bot instance
            async def authenticate_bot():
                try:
                    if typeof __initial_auth_token !== 'undefined' and __initial_auth_token:
                        await signInWithCustomToken(auth, __initial_auth_token)
                        logger.info("Signed in with custom token.")
                    else:
                        await signInAnonymously(auth)
                        logger.info("Signed in anonymously.")
                except Exception as e:
                    logger.error(f"Firebase authentication failed: {e}")
                    # Handle authentication failure, maybe exit or retry
            
            # Run this async function to ensure authentication completes before bot starts polling
            import asyncio
            asyncio.run(authenticate_bot())

        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            # If Firebase fails to initialize, the bot might not work correctly.
            # You might want to exit here or run with limited functionality.

    # Create the Application and pass your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # General Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("id", get_id))
    application.add_handler(CommandHandler("echo", echo))

    # Moderation Commands
    application.add_handler(CommandHandler("kick", kick_user))
    application.add_handler(CommandHandler("warn", warn_user))
    application.add_handler(CommandHandler("unwarn", unwarn_user))
    application.add_handler(CommandHandler("warnings", check_warnings))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler("unmute", unmute_user))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("del", delete_message))
    application.add_handler(CommandHandler("pin", pin_message))
    application.add_handler(CommandHandler("unpin", unpin_message))

    # Group Management Commands
    application.add_handler(CommandHandler("setwelcome", set_welcome_message))
    application.add_handler(CommandHandler("delwelcome", delete_welcome_message))
    application.add_handler(CommandHandler("rules", set_rules))
    application.add_handler(CommandHandler("getrules", get_rules)) # Added explicit command for clarity
    application.add_handler(CommandHandler("info", get_user_info))
    application.add_handler(CommandHandler("chatinfo", get_chat_info))
    application.add_handler(CommandHandler("report", report_message))


    # On new members joining - add handler
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))

    # Run the bot until the user presses Ctrl-C
    logger.info("Bot started! Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

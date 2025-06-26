# main.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
    CallbackQueryHandler
)
import requests
import urllib.parse
from io import BytesIO
import asyncio # For the progress animation
import json # For saving/loading settings in user_data

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "7582238839:AAHcJW1kOcEcJ_RRk5ovZVmvebxE4za9x7I"
POLLINATIONS_IMAGE_API = "https://image.pollinations.ai/prompt/"
MAX_RECENT_PROMPTS = 5 # Maximum number of recent prompts to store
DEFAULT_IMAGE_TIMEOUT = 60 # Default timeout for image generation requests in seconds

# Define states for our conversation flow
GET_PROMPT, ASK_NEGATIVE_PROMPT, ASK_CUSTOM_TIMEOUT, RECEIVE_CUSTOM_TIMEOUT, CHOOSE_NUM_IMAGES, CHOOSE_QUALITY, CHOOSE_RATIO, CHOOSE_STYLE, ASK_OUTPUT_TYPE, GET_FEEDBACK_TEXT = range(10)

# Image Quality/Resolution options (width, height)
QUALITIES = {
    "Standard": (768, 768),
    "High": (1024, 1024),
    "Ultra": (1280, 1280),
}

# Ratios and their corresponding dimensions (for scaling the base quality dimensions)
RATIOS = {
    "1:1 (Square)": (1, 1),
    "4:5 (Portrait)": (4, 5),
    "9:16 (Tall Portrait)": (9, 16),
    "16:9 (Landscape)": (16, 9),
    "9:21 (Ultra Tall)": (9, 21),
    "21:9 (Ultra Wide)": (21, 9),
}

# Image styles to offer
STYLES = [
    "auto", "realistic", "digital art", "painting", "anime",
    "3d render", "minimalist", "sketch", "B&W"
]

# Number of image options to present to the user
NUM_IMAGE_OPTIONS = [1, 2, 3, 4, 5, 6, 7, 8]

# --- Helper Functions ---
def get_progress_bar(current, total, bar_length=20):
    """Generates a text-based progress bar."""
    progress = (current / total)
    arrow = '=' * int(round(progress * bar_length) - 1) + '>'
    spaces = ' ' * (bar_length - len(arrow))
    return f"[{arrow}{spaces}] {int(progress * 100)}%"

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a 'hello' message and instructions when the command /start is issued."""
    if update.message:
        logger.info(f"Received /start command from {update.effective_user.id}")
        await update.message.reply_text(
            'Hello! I can generate images based on your text prompts.\n'
            'Send me a detailed description (prompt) to start. '
            'Use /help for more information on how to use me.'
        )
    else:
        logger.warning("Received a /start update without a message object.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a help message explaining bot features."""
    if update.message:
        logger.info(f"Received /help command from {update.effective_user.id}")
        help_text = (
            "🤖 **Image Generation Bot Help** 🤖\n\n"
            "To generate an image:\n"
            "1. Just **send me a text message with your image description (prompt)**. "
            "   Example: `A futuristic city at sunset, highly detailed`\n"
            "2. I'll guide you through choosing **negative prompt**, **number of images**, "
            "   **quality**, **aspect ratio**, and **style**.\n\n"
            "**Key Features:**\n"
            "🎨 **Negative Prompt**: Exclude unwanted elements.\n"
            "⏱️ **Custom Timeout**: Set a maximum generation time.\n"
            "🖼️ **Image Quality**: Choose from Standard, High, Ultra resolution.\n"
            "📏 **Aspect Ratios**: Define image shape (1:1, 16:9, etc.).\n"
            "🖌️ **Styles**: Apply artistic styles like 'realistic' or 'anime'.\n"
            "🔢 **Multiple Images**: Generate 1 to 8 variations.\n"
            "🔄 **Regenerate**: Create new images with the same settings.\n"
            "✨ **Recent Prompts**: Quickly reuse your last few prompts.\n"
            "💾 **Save/Load Settings**: Save your preferred generation parameters as default.\n"
            "🔗 **Image URLs**: Get direct links to images instead of receiving them.\n"
            "📊 **Progress Bar**: See live progress during generation.\n\n"
            "**Commands:**\n"
            "• `/start`: Greet the bot.\n"
            "• `/help`: Show this help message.\n"
            "• `/describe_image`: Reply to an image with this command to get a description (experimental).\n"
            "• `/feedback`: Send feedback to the bot's developer.\n"
            "• `/clear_data`: Clear your recent prompts and saved settings.\n"
            "• `/cancel`: Stop the current image generation process.\n\n"
            "Enjoy creating! 🚀"
        )
        await update.message.reply_markdown(help_text)
    else:
        logger.warning("Received a /help update without a message object.")

async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provides information about the bot."""
    if update.message:
        logger.info(f"Received /about command from {update.effective_user.id}")
        about_text = (
            "**About This Bot**\n\n"
            "This bot allows you to generate images from text prompts using the Pollinations AI API.\n"
            "It's designed to be a fun and interactive way to explore AI-generated art.\n\n"
            "Please remember that images generated by Pollinations AI may include a watermark. "
            "For support or feedback, use the `/feedback` command."
        )
        await update.message.reply_markdown(about_text)

async def clear_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clears user's recent prompts and saved settings."""
    if update.message:
        user_id = update.effective_user.id
        if 'recent_prompts' in context.user_data:
            context.user_data.pop('recent_prompts')
        if 'saved_settings' in context.user_data:
            context.user_data.pop('saved_settings')
        logger.info(f"User {user_id} cleared their recent prompts and saved settings.")
        await update.message.reply_text("Your recent prompts and saved settings have been cleared.")
    else:
        logger.warning("Received a /clear_data update without a message object.")

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the feedback conversation."""
    if update.message:
        logger.info(f"User {update.effective_user.id} initiated feedback.")
        await update.message.reply_text(
            "Please send me your feedback message. Use /cancel to stop."
        )
        return GET_FEEDBACK_TEXT
    return ConversationHandler.END

async def receive_feedback_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the feedback text and logs it."""
    if update.message and update.message.text:
        feedback_text = update.message.text
        user_id = update.effective_user.id
        logger.info(f"Feedback from {user_id}: {feedback_text}")
        await update.message.reply_text(
            "Thank you for your feedback! It has been received."
        )
    else:
        await update.message.reply_text("Please send valid text feedback.")
    return ConversationHandler.END # End the feedback conversation

async def describe_image_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Placeholder for image description feature."""
    if update.message:
        if update.message.reply_to_message and update.message.reply_to_message.photo:
            logger.info(f"User {update.effective_user.id} requested image description.")
            await update.message.reply_text(
                "This feature is under development! To describe images, I would need to integrate with a powerful Vision AI model (like Google's Gemini Vision API)."
                "\n\nCurrently, I only generate images from text. Stay tuned for updates!"
            )
        else:
            await update.message.reply_text(
                "Please reply to an image with the /describe_image command to use this feature."
            )
    else:
        logger.warning("Received /describe_image update without a message object.")


async def receive_initial_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for conversation: receives the user's initial message as a prompt,
    stores it, and then asks if they want to add a negative prompt, or offers recent prompts.
    Also adds "Use Saved Settings" button.
    """
    if not update.message or not update.message.text:
        await update.message.reply_text("Please send me a text message to start image generation.")
        return ConversationHandler.END
    
    user_prompt = update.message.text.strip()
    context.user_data['prompt'] = user_prompt
    logger.info(f"User {update.effective_user.id} initiated image generation with prompt: '{user_prompt}'")

    # Add current prompt to recent prompts history
    if 'recent_prompts' not in context.user_data:
        context.user_data['recent_prompts'] = []
    
    if user_prompt not in context.user_data['recent_prompts']:
        context.user_data['recent_prompts'].insert(0, user_prompt)
        context.user_data['recent_prompts'] = context.user_data['recent_prompts'][:MAX_RECENT_PROMPTS]

    keyboard = [
        [
            InlineKeyboardButton("Yes, add a negative prompt", callback_data="add_negative_prompt"),
            InlineKeyboardButton("No, skip negative prompt", callback_data="skip_negative_prompt")
        ]
    ]

    # Add "Use Saved Settings" button if settings exist
    if 'saved_settings' in context.user_data and context.user_data['saved_settings']:
        keyboard.append([InlineKeyboardButton("Use Saved Settings", callback_data="use_saved_settings")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Your prompt: '{user_prompt}'\nDo you want to add a negative prompt (things you DON'T want in the image)?",
        reply_markup=reply_markup
    )
    return ASK_NEGATIVE_PROMPT

async def handle_negative_prompt_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice regarding a negative prompt or using saved settings."""
    query = update.callback_query
    await query.answer()

    if query.data == "add_negative_prompt":
        await query.edit_message_text("Please send me the negative prompt (e.g., 'ugly, blurry, deformed').")
        context.user_data['awaiting_negative_prompt'] = True
        return ASK_NEGATIVE_PROMPT
    elif query.data == "skip_negative_prompt":
        context.user_data['negative_prompt'] = ""
        await query.edit_message_text("Negative prompt skipped.")
        return await ask_custom_timeout(update, context) # Proceed to ask for custom timeout
    elif query.data == "use_saved_settings":
        return await load_saved_settings(update, context)
    
    return ASK_NEGATIVE_PROMPT

async def receive_negative_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the user's negative prompt."""
    if not update.message or not update.message.text:
        await update.message.reply_text("Please send a valid negative prompt or use /cancel.")
        return ASK_NEGATIVE_PROMPT

    negative_prompt = update.message.text.strip()
    context.user_data['negative_prompt'] = negative_prompt
    context.user_data.pop('awaiting_negative_prompt', None)
    logger.info(f"User {update.effective_user.id} entered negative prompt: '{negative_prompt}'")

    return await ask_custom_timeout(update, context)

async def ask_custom_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user if they want to set a custom timeout."""
    keyboard = [
        [
            InlineKeyboardButton("Yes, set custom timeout", callback_data="set_custom_timeout"),
            InlineKeyboardButton(f"No, use default ({DEFAULT_IMAGE_TIMEOUT}s)", callback_data="use_default_timeout")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Use the original message or query message for sending the next prompt
    message_to_edit = update.callback_query.message if update.callback_query else update.message
    await message_to_edit.reply_text(
        "Do you want to set a custom timeout for image generation?",
        reply_markup=reply_markup
    )
    return ASK_CUSTOM_TIMEOUT

async def handle_custom_timeout_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice for custom timeout."""
    query = update.callback_query
    await query.answer()

    if query.data == "set_custom_timeout":
        await query.edit_message_text("Please send the timeout value in seconds (e.g., '90' for 90 seconds). Max 180 seconds.")
        return RECEIVE_CUSTOM_TIMEOUT
    elif query.data == "use_default_timeout":
        context.user_data['generation_timeout'] = DEFAULT_IMAGE_TIMEOUT
        await query.edit_message_text(f"Using default timeout of {DEFAULT_IMAGE_TIMEOUT} seconds.")
        return await ask_num_images(update, context) # Proceed to ask for num images
    
    return ASK_CUSTOM_TIMEOUT

async def receive_custom_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives the user's custom timeout value."""
    if not update.message or not update.message.text:
        await update.message.reply_text("Please send a valid number for timeout or use /cancel.")
        return RECEIVE_CUSTOM_TIMEOUT
    
    try:
        timeout_value = int(update.message.text.strip())
        if not (10 <= timeout_value <= 180): # Enforce reasonable bounds
            await update.message.reply_text("Please enter a timeout between 10 and 180 seconds.")
            return RECEIVE_CUSTOM_TIMEOUT
        
        context.user_data['generation_timeout'] = timeout_value
        logger.info(f"User {update.effective_user.id} set custom timeout: {timeout_value}s")
        await update.message.reply_text(f"Custom timeout set to {timeout_value} seconds.")
        return await ask_num_images(update, context)
    except ValueError:
        await update.message.reply_text("Invalid input. Please enter a number for timeout.")
        return RECEIVE_CUSTOM_TIMEOUT

async def ask_num_images(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user for the number of images to generate."""
    keyboard = []
    row = []
    for num in NUM_IMAGE_OPTIONS:
        row.append(InlineKeyboardButton(str(num), callback_data=f"num_{num}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_to_edit = update.callback_query.message if update.callback_query else update.message
    await message_to_edit.reply_text(
        f"How many images would you like to generate?",
        reply_markup=reply_markup
    )
    return CHOOSE_NUM_IMAGES


async def choose_num_images(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles the user's selection for the number of images and then
    asks for the image quality.
    """
    query = update.callback_query
    await query.answer()

    chosen_num_images = int(query.data.replace("num_", ""))
    context.user_data['num_images'] = chosen_num_images
    logger.info(f"User {update.effective_user.id} selected {chosen_num_images} images.")

    keyboard = []
    for quality_name in QUALITIES.keys():
        keyboard.append([InlineKeyboardButton(quality_name, callback_data=f"quality_{quality_name}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"You chose {chosen_num_images} images. Now, please choose the image quality:",
        reply_markup=reply_markup
    )
    return CHOOSE_QUALITY

async def choose_quality(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles the user's quality selection and then asks for the image ratio.
    """
    query = update.callback_query
    await query.answer()

    chosen_quality_name = query.data.replace("quality_", "")
    context.user_data['quality'] = chosen_quality_name
    logger.info(f"User {update.effective_user.id} selected quality: {chosen_quality_name}")

    keyboard = []
    for ratio_name in RATIOS.keys():
        keyboard.append([InlineKeyboardButton(ratio_name, callback_data=f"ratio_{ratio_name}")])
    keyboard.append([InlineKeyboardButton("Random Ratio", callback_data="ratio_random")]) # Random option
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"You chose '{chosen_quality_name}' quality. Now, please choose an aspect ratio:",
        reply_markup=reply_markup
    )
    return CHOOSE_RATIO

async def choose_ratio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles the user's ratio selection and then asks for the image style.
    """
    query = update.callback_query
    await query.answer()

    chosen_ratio_name = query.data.replace("ratio_", "")
    if chosen_ratio_name == "random":
        import random
        chosen_ratio_name = random.choice(list(RATIOS.keys()))
        await query.edit_message_text(f"Random ratio selected: '{chosen_ratio_name}'.")
        await asyncio.sleep(0.5) # Small delay for user to see the random choice

    context.user_data['ratio'] = chosen_ratio_name
    logger.info(f"User {update.effective_user.id} selected ratio: {chosen_ratio_name}")

    keyboard = []
    for i in range(0, len(STYLES), 3):
        row = []
        for style in STYLES[i:i+3]:
            row.append(InlineKeyboardButton(style.title(), callback_data=f"style_{style}"))
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("Random Style", callback_data="style_random")]) # Random option
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"You chose '{chosen_ratio_name}'. Now, please select an image style:",
        reply_markup=reply_markup
    )
    return CHOOSE_STYLE

async def choose_style_and_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles the user's style selection, then initiates image generation,
    provides progress updates, sends images as a media group, and offers
    "Regenerate" or "Start New" options.
    """
    query = update.callback_query
    await query.answer()

    chosen_style = query.data.replace("style_", "")
    if chosen_style == "random":
        import random
        chosen_style = random.choice(STYLES)
        await query.edit_message_text(f"Random style selected: '{chosen_style}'.")
        await asyncio.sleep(0.5) # Small delay for user to see the random choice

    context.user_data['style'] = chosen_style
    logger.info(f"User {update.effective_user.id} selected style: {chosen_style}")

    # Retrieve all necessary data from context.user_data
    prompt = context.user_data.get('prompt')
    negative_prompt = context.user_data.get('negative_prompt', "")
    ratio_name = context.user_data.get('ratio')
    quality_name = context.user_data.get('quality')
    num_images = context.user_data.get('num_images')
    generation_timeout = context.user_data.get('generation_timeout', DEFAULT_IMAGE_TIMEOUT) # Use default if not set

    base_width, base_height = QUALITIES.get(quality_name, (1024, 1024))
    ratio_w, ratio_h = RATIOS.get(ratio_name, (1, 1))

    # Calculate actual width and height based on quality and aspect ratio
    if ratio_w >= ratio_h:
        width = base_width
        height = int(base_width * (ratio_h / ratio_w))
    else:
        height = base_height
        width = int(base_height * (ratio_w / ratio_h))

    logger.info(f"Generating with dimensions: {width}x{height}, timeout: {generation_timeout}s")

    # Ask user for output type (images or URLs)
    keyboard = [
        [
            InlineKeyboardButton("Send Images", callback_data="output_images"),
            InlineKeyboardButton("Send Image URLs", callback_data="output_urls")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "How would you like to receive the generated images?",
        reply_markup=reply_markup
    )
    return ASK_OUTPUT_TYPE

async def handle_output_type_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's choice for output type (images or URLs) and starts generation."""
    query = update.callback_query
    await query.answer()

    output_type = query.data.replace("output_", "")
    context.user_data['output_type'] = output_type
    logger.info(f"User {update.effective_user.id} chose output type: {output_type}")

    # Retrieve all necessary data from context.user_data for generation
    prompt = context.user_data.get('prompt')
    negative_prompt = context.user_data.get('negative_prompt', "")
    ratio_name = context.user_data.get('ratio')
    quality_name = context.user_data.get('quality')
    num_images = context.user_data.get('num_images')
    generation_timeout = context.user_data.get('generation_timeout', DEFAULT_IMAGE_TIMEOUT)

    base_width, base_height = QUALITIES.get(quality_name, (1024, 1024))
    ratio_w, ratio_h = RATIOS.get(ratio_name, (1, 1))

    if ratio_w >= ratio_h:
        width = base_width
        height = int(base_width * (ratio_h / ratio_w))
    else:
        height = base_height
        width = int(base_height * (ratio_w / ratio_h))

    # Inform the user that generation is starting and provide initial progress
    generation_message_text = f"Starting image generation. Generating 0 of {num_images} images... {get_progress_bar(0, num_images)}"
    generation_message = await query.edit_message_text(generation_message_text)
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action='upload_photo')

    media_group = [] # For InputMediaPhoto objects
    image_urls_list = [] # For direct URLs

    for i in range(num_images):
        current_image_num = i + 1
        
        # Update the progress message in the chat with animation and progress bar
        try:
            current_frame_index = i % 3 # For . .. ... animation
            animated_text = f"Generating image {current_image_num} of {num_images}{'. ' * current_frame_index} {get_progress_bar(current_image_num, num_images)}"
            await context.bot.edit_message_text(
                chat_id=generation_message.chat_id,
                message_id=generation_message.message_id,
                text=animated_text
            )
            await asyncio.sleep(0.5)
        except Exception as edit_error:
            logger.warning(f"Could not edit message for progress update: {edit_error}")

        full_prompt = f"{prompt}, {context.user_data['style']} style"
        if negative_prompt:
            full_prompt += f", no {negative_prompt}"
        
        variant_prompt = f"{full_prompt} (variation {current_image_num})"
        
        try:
            encoded_prompt = urllib.parse.quote(variant_prompt)
            image_generation_url = f"{POLLINATIONS_IMAGE_API}{encoded_prompt}?width={width}&height={height}"
            logger.info(f"Attempting to fetch image {current_image_num}/{num_images} from URL: {image_generation_url}")

            response = requests.get(image_generation_url, stream=True, timeout=generation_timeout)
            response.raise_for_status()

            if output_type == "images":
                image_bytes = BytesIO(response.content)
                media_group.append(InputMediaPhoto(media=image_bytes))
            else: # output_type == "urls"
                image_urls_list.append(image_generation_url)
            
            logger.info(f"Successfully prepared image {current_image_num} for prompt: '{variant_prompt}'")

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching image {current_image_num} for {update.effective_user.id}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Image {current_image_num} generation timed out. Pollinations AI might be experiencing high load. Trying next image..."
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching image {current_image_num} from Pollinations AI for {update.effective_user.id}: {e}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"Sorry, I couldn't generate image {current_image_num} for you due to a network or API issue. Trying next image..."
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred for image {current_image_num} for {update.effective_user.id}: {e}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=f"An unexpected error occurred while trying to generate image {current_image_num}. Trying next image..."
            )
    
    # Attempt to delete the final progress message
    try:
        await context.bot.delete_message(chat_id=generation_message.chat_id, message_id=generation_message.message_id)
    except Exception as delete_error:
        logger.warning(f"Could not delete generation message: {delete_error}")

    if output_type == "images" and media_group:
        try:
            await context.bot.send_media_group(chat_id=query.message.chat_id, media=media_group)
            logger.info(f"Successfully sent all {len(media_group)} images to {update.effective_user.id}")
        except Exception as e:
            logger.error(f"Error sending media group to {update.effective_user.id}: {e}")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Finished generating images, but had trouble sending them as a group. You might see some individually."
            )
    elif output_type == "urls" and image_urls_list:
        urls_text = "\n".join(image_urls_list)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=f"Here are the image URLs:\n{urls_text}",
            disable_web_page_preview=False # Allow preview for URLs
        )
        logger.info(f"Successfully sent {len(image_urls_list)} image URLs to {update.effective_user.id}")
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="No images could be generated successfully with your request. Please try again."
        )

    # Add post-generation buttons
    final_keyboard = [
        [
            InlineKeyboardButton("Regenerate (Same Settings)", callback_data="regenerate"),
            InlineKeyboardButton("Start New Generation", callback_data="start_new")
        ],
        [
            InlineKeyboardButton("Save Current Settings", callback_data="save_current_settings"),
            InlineKeyboardButton("Upscale/Enhance (Experimental)", callback_data="upscale_image")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(final_keyboard)

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="All done! Please note that images generated by Pollinations AI may include a watermark that cannot be removed by the bot.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END


async def handle_post_generation_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles callback queries from the 'Regenerate', 'Start New', 'Save Settings', and 'Upscale' buttons.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "regenerate":
        try:
            await query.edit_message_text("Regenerating images with the same settings...")
        except Exception as e:
            logger.warning(f"Could not edit message after regenerate click: {e}")
            await context.bot.send_message(query.message.chat_id, "Regenerating images with the same settings...")

        # Re-trigger the generation process using the stored user_data
        # We simulate the last step of the conversation to re-enter the generation function
        dummy_query = Update(update_id=update.update_id)
        dummy_query.callback_query = query
        dummy_query.callback_query.data = f"output_{context.user_data['output_type']}" # Simulate choosing output type again

        return await handle_output_type_choice(dummy_query, context)

    elif query.data == "start_new":
        # Clear user data (except recent prompts) to reset the conversation state
        prompt_history = context.user_data.get('recent_prompts', [])
        saved_settings = context.user_data.get('saved_settings', {}) # Preserve saved settings too
        context.user_data.clear()
        context.user_data['recent_prompts'] = prompt_history
        context.user_data['saved_settings'] = saved_settings
        
        try:
            keyboard = []
            if context.user_data['recent_prompts']:
                keyboard.append([InlineKeyboardButton("Choose from Recent Prompts", callback_data="choose_recent_prompt")])
            
            keyboard.append([InlineKeyboardButton("Enter New Prompt", callback_data="enter_new_prompt")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "Starting a new image generation. Would you like to use a recent prompt or enter a new one?",
                reply_markup=reply_markup
            )
            context.user_data['awaiting_prompt_choice'] = True
            return GET_PROMPT
        except Exception as e:
            logger.warning(f"Could not edit message after start_new click: {e}")
            await context.bot.send_message(query.message.chat_id, "Starting a new image generation. Please send your new prompt.")
            return GET_PROMPT

    elif query.data == "save_current_settings":
        # Save current generation parameters to 'saved_settings'
        settings_to_save = {
            'prompt': context.user_data.get('prompt'),
            'negative_prompt': context.user_data.get('negative_prompt', ""),
            'num_images': context.user_data.get('num_images'),
            'quality': context.user_data.get('quality'),
            'ratio': context.user_data.get('ratio'),
            'style': context.user_data.get('style'),
            'generation_timeout': context.user_data.get('generation_timeout', DEFAULT_IMAGE_TIMEOUT),
            'output_type': context.user_data.get('output_type', "images")
        }
        context.user_data['saved_settings'] = settings_to_save
        logger.info(f"User {update.effective_user.id} saved settings: {settings_to_save}")
        await query.edit_message_text("Your current generation settings have been saved for future use!")
        return ConversationHandler.END # End this action, user can start new or regenerate

    elif query.data == "upscale_image":
        await query.edit_message_text(
            "The 'Upscale/Enhance' feature is experimental and not yet fully integrated.\n\n"
            "To upscale images, I would need to connect with a dedicated image upscaling service. "
            "Stay tuned for future updates!"
        )
        return ConversationHandler.END

async def load_saved_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Loads saved settings and proceeds to generation."""
    query = update.callback_query
    await query.answer()

    saved_settings = context.user_data.get('saved_settings')
    if not saved_settings:
        await query.edit_message_text("No saved settings found. Please enter a new prompt.")
        return GET_PROMPT # Fallback to new prompt

    # Apply saved settings to current user_data for generation
    context.user_data.update(saved_settings)
    logger.info(f"User {update.effective_user.id} loaded saved settings: {saved_settings}")
    
    await query.edit_message_text("Using your saved settings for generation. Proceeding to image creation!")
    # Directly jump to the generation phase. We need to simulate the last callback needed.
    dummy_query = Update(update_id=update.update_id)
    dummy_query.callback_query = query
    # This ensures choose_style_and_generate receives the correct 'style' callback data
    dummy_query.callback_query.data = f"style_{saved_settings['style']}"
    
    # We now call handle_output_type_choice because that's the point before generation starts.
    # We need to simulate the output type being chosen from saved settings.
    dummy_query_for_output_type = Update(update_id=update.update_id)
    dummy_query_for_output_type.callback_query = query
    dummy_query_for_output_type.callback_query.data = f"output_{saved_settings.get('output_type', 'images')}"

    return await handle_output_type_choice(dummy_query_for_output_type, context)


async def handle_start_new_prompt_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the choice to use a recent prompt or enter a new one."""
    query = update.callback_query
    await query.answer()
    
    context.user_data.pop('awaiting_prompt_choice', None) # Clear flag

    if query.data == "choose_recent_prompt":
        recent_prompts = context.user_data.get('recent_prompts', [])
        if not recent_prompts:
            await query.edit_message_text("No recent prompts available. Please send a new prompt.")
            return GET_PROMPT
        
        keyboard = [[InlineKeyboardButton(p, callback_data=f"use_recent_{idx}")] for idx, p in enumerate(recent_prompts)]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Select a recent prompt:", reply_markup=reply_markup)
        return GET_PROMPT

    elif query.data == "enter_new_prompt":
        await query.edit_message_text("Please send your new image description (prompt).")
        return GET_PROMPT
    
    elif query.data.startswith("use_recent_"):
        idx = int(query.data.replace("use_recent_", ""))
        recent_prompts = context.user_data.get('recent_prompts', [])
        if 0 <= idx < len(recent_prompts):
            selected_prompt = recent_prompts[idx]
            context.user_data['prompt'] = selected_prompt
            await query.edit_message_text(f"Using recent prompt: '{selected_prompt}'")
            # Now proceed to ask for negative prompt, simulating initial flow
            return await ask_negative_prompt_for_recent(update, context)
        else:
            await query.edit_message_text("Invalid recent prompt selection. Please send a new prompt.")
            return GET_PROMPT

async def ask_negative_prompt_for_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Helper to ask for negative prompt when using a recent prompt."""
    keyboard = [
        [
            InlineKeyboardButton("Yes, add a negative prompt", callback_data="add_negative_prompt"),
            InlineKeyboardButton("No, skip negative prompt", callback_data="skip_negative_prompt")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(
        f"For prompt: '{context.user_data.get('prompt')}'\nDo you want to add a negative prompt?",
        reply_markup=reply_markup
    )
    return ASK_NEGATIVE_PROMPT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    if update.message:
        user_id = update.effective_user.id
        logger.info(f"User {user_id} cancelled the conversation.")
        await update.message.reply_text(
            'Image generation cancelled. Send me a prompt to start again.'
        )
    # Clear most user data, but preserve recent prompts and saved settings
    prompt_history = context.user_data.get('recent_prompts', [])
    saved_settings = context.user_data.get('saved_settings', {})
    context.user_data.clear()
    context.user_data['recent_prompts'] = prompt_history
    context.user_data['saved_settings'] = saved_settings
    return ConversationHandler.END


# --- Main Bot Function ---

def main() -> None:
    """Starts the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Conversation Handler defines the multi-step flow for image generation
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_initial_prompt),
            CallbackQueryHandler(handle_start_new_prompt_choice, pattern=r'^(choose_recent_prompt|enter_new_prompt|use_recent_.*)$')
        ],
        states={
            GET_PROMPT: [ # Covers initial prompt, and subsequent prompt entry after 'start new'
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_initial_prompt),
                CallbackQueryHandler(handle_start_new_prompt_choice, pattern=r'^(choose_recent_prompt|enter_new_prompt|use_recent_.*)$')
            ],
            ASK_NEGATIVE_PROMPT: [
                CallbackQueryHandler(handle_negative_prompt_choice, pattern=r'^(add_negative_prompt|skip_negative_prompt|use_saved_settings)$'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_negative_prompt)
            ],
            ASK_CUSTOM_TIMEOUT: [CallbackQueryHandler(handle_custom_timeout_choice, pattern=r'^(set_custom_timeout|use_default_timeout)$')],
            RECEIVE_CUSTOM_TIMEOUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_timeout)],
            CHOOSE_NUM_IMAGES: [CallbackQueryHandler(choose_num_images, pattern=r'^num_')],
            CHOOSE_QUALITY: [CallbackQueryHandler(choose_quality, pattern=r'^quality_')],
            CHOOSE_RATIO: [CallbackQueryHandler(choose_ratio, pattern=r'^ratio_|^ratio_random$')],
            CHOOSE_STYLE: [CallbackQueryHandler(choose_style_and_generate, pattern=r'^style_|^style_random$')],
            ASK_OUTPUT_TYPE: [CallbackQueryHandler(handle_output_type_choice, pattern=r'^(output_images|output_urls)$')],
            GET_FEEDBACK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_feedback_text)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("clear_data", clear_data_command))
    application.add_handler(CommandHandler("feedback", feedback_command)) # Entry point for feedback
    application.add_handler(CommandHandler("describe_image", describe_image_command)) # Placeholder for describe image

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_post_generation_buttons, pattern=r'^(regenerate|start_new|save_current_settings|upscale_image)$'))

    logger.info("Bot started. Press Ctrl-C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

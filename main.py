import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os

# --- Configuration ---
# Your Telegram Bot Token
BOT_TOKEN = '7598946589:AAHNOuwJps7wSn26HiNlUSqggBY_28ChnxU'
bot = telebot.TeleBot(BOT_TOKEN)

# --- Data Management ---
# This is where your bot's content (groups, channels, bots) is stored.
# For simplicity, a small sample dataset is embedded.
# For a larger, production-ready bot, consider moving this to a 'data.json' file
# and loading it using the 'load_data' function below.
sample_data = {
    "group": {
        "Technology": [
            {"name": "Tech Enthusiasts 🧑‍💻", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"}, # Replace with actual invite links
            {"name": "Python Devs Community 🐍", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"},
            {"name": "AI & Machine Learning Hub 🧠", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"},
            {"name": "Web Development Discussions 🌐", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"},
            {"name": "Cybersecurity Talks 🔒", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"}
        ],
        "Gaming": [
            {"name": "PC Gamers Hangout 🎮", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"},
            {"name": "Mobile Gaming Arena 📱", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"},
            {"name": "Retro Gaming Fanatics 👾", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"},
            {"name": "Esports Community 🏆", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"}
        ],
        "Books": [
            {"name": "Book Lovers Club 📚", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"},
            {"name": "Fiction Readers 📖", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"}
        ],
        "Fitness": [
            {"name": "Fitness & Workout 💪", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"},
            {"name": "Yoga & Meditation 🙏", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"}
        ],
        "Movies & TV": [ # Added a new niche for demonstration
            {"name": "Movie Discussions 🎬", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"},
            {"name": "Series Binge Watchers 🍿", "link": "https://t.me/+AbcdefGHIJ_KLMNOP_QRSTUV"}
        ]
        # Add more group niches and their respective groups/links here!
        # Remember to replace placeholder links with actual invite links.
    },
    "channel": {
        "News": [
            {"name": "Daily Global News 📰", "link": "https://t.me/example_news_channel1"}, # Replace with actual channel links
            {"name": "Tech News Updates ⚡", "link": "https://t.me/example_technews_channel2"},
            {"name": "Financial Insights 💰", "link": "https://t.me/example_finance_channel3"}
        ],
        "Movies": [
            {"name": "Latest Movie Releases 🎬", "link": "https://t.me/example_movies_channel1"},
            {"name": "Netflix & Chill Picks 🍿", "link": "https://t.me/example_netflix_channel2"}
        ],
        "Education": [
            {"name": "Learning Resources Hub 🎓", "link": "https://t.me/example_edu_channel1"},
            {"name": "Programming Tutorials 🖥️", "link": "https://t.me/example_programming_channel2"}
        ]
        # Add more channel niches and their respective channels/links here!
    },
    "bot": {
        "Utility": [
            {"name": "File Converter Bot ⚙️", "link": "https://t.me/example_file_converter_bot"}, # Replace with actual bot links
            {"name": "Translator Bot 🗣️", "link": "https://t.me/example_translator_bot"},
            {"name": "GIF Searcher Bot ✨", "link": "https://t.me/example_gif_bot"}
        ],
        "Games": [
            {"name": "Quiz Master Bot ❓", "link": "https://t.me/example_quiz_bot"},
            {"name": "Mafia Game Bot 🎩", "link": "https://t.me/example_mafia_bot"}
        ]
        # Add more bot niches and their respective bots/links here!
    }
}

# Function to load data from a JSON file (recommended for larger datasets)
def load_data(filename='data.json'):
    """
    Loads bot data from a JSON file. If the file doesn't exist,
    it returns the sample_data embedded in the script.
    """
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {filename}. Using sample data.")
            return sample_data
    print(f"'{filename}' not found. Using embedded sample data.")
    return sample_data

# Use the embedded sample data for now.
# If you create a 'data.json' file, uncomment the line below and comment out the current DATA line.
# DATA = load_data('data.json')
DATA = sample_data

# --- Telegram Bot Handlers ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """
    Handles the /start command. Greets the user and presents the main options
    (Groups, Channels, Bots) using an inline keyboard.
    """
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("🔎 Groups", callback_data="type_group"),
        InlineKeyboardButton("📺 Channels", callback_data="type_channel"),
        InlineKeyboardButton("🤖 Bots", callback_data="type_bot")
    )
    bot.send_message(
        message.chat.id,
        "👋 Welcome! I can help you discover amazing Telegram communities and tools. "
        "What are you looking for today?",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_type_selection(call):
    """
    Handles the selection of a content type (Group, Channel, or Bot).
    Displays a list of niches relevant to the selected type.
    """
    bot.answer_callback_query(call.id) # Acknowledge the button press

    selected_type = call.data.split('_')[1] # Extracts 'group', 'channel', or 'bot'

    niches_for_type = DATA.get(selected_type, {})
    if not niches_for_type:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"Oops! No niches found for {selected_type.capitalize()}s yet. Please try another option or check back later."
        )
        return

    markup = InlineKeyboardMarkup()
    markup.row_width = 2 # Display two niche buttons per row

    # Sort niches alphabetically for better user experience
    sorted_niches = sorted(niches_for_type.keys())

    # Create an inline button for each niche
    for niche in sorted_niches:
        # Encode niche name for callback_data to handle spaces/special characters
        # Example: "Technology" becomes "technology", "Movies & TV" becomes "movies_and_tv"
        callback_data_niche = f"niche_{selected_type}_{niche.replace(' ', '_').replace('&', 'and').lower()}"
        markup.add(InlineKeyboardButton(niche, callback_data=callback_data_niche))

    # Add a 'Back to Main Menu' button
    markup.add(InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Great choice! Now, select a **niche** for {selected_type.capitalize()}s:",
        reply_markup=markup,
        parse_mode='Markdown' # Allows for bold text using **
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('niche_'))
def handle_niche_selection(call):
    """
    Handles the selection of a specific niche.
    Displays active groups, channels, or bots within that niche, along with their links.
    """
    bot.answer_callback_query(call.id) # Acknowledge the button press

    parts = call.data.split('_')
    selected_type = parts[1] # 'group', 'channel', or 'bot'

    # Reconstruct the original niche name from callback data (undoing the encoding)
    # Example: "movies_and_tv" becomes "Movies & TV"
    original_niche_name = " ".join(parts[2:]).replace('_', ' ').replace('and', '&').title()

    listings = DATA.get(selected_type, {}).get(original_niche_name, [])

    if not listings:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"No active listings found for the '{original_niche_name}' {selected_type} niche yet. Please try another niche or check back later."
        )
        return

    markup = InlineKeyboardMarkup()
    markup.row_width = 1 # One listing button per row for clarity

    # Add each listing as an inline button with a direct URL
    for item in listings:
        button_text = f"{item['name']}"
        markup.add(InlineKeyboardButton(button_text, url=item['link']))

    # Add a 'Back' button to return to niche selection for the current type
    markup.add(InlineKeyboardButton(f"⬅️ Back to {selected_type.capitalize()} Niches", callback_data=f"type_{selected_type}"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Here are some active **{selected_type}s** in the '{original_niche_name}' niche:",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main')
def back_to_main_menu(call):
    """
    Handles the 'Back to Main Menu' button, returning the user to the initial
    choice of Groups, Channels, or Bots.
    """
    bot.answer_callback_query(call.id)
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton("🔎 Groups", callback_data="type_group"),
        InlineKeyboardButton("📺 Channels", callback_data="type_channel"),
        InlineKeyboardButton("🤖 Bots", callback_data="type_bot")
    )
    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text="What are you looking for today?",
        reply_markup=markup
    )

# --- Start the bot ---
if __name__ == '__main__':
    print("Bot is starting...")
    # 'none_stop=True' keeps the bot running even if there are errors in processing updates
    bot.polling(none_stop=True)
    print("Bot is running!")

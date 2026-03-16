import json
import logging
import os

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    MessageHandler,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters
)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOARD_CHANNEL = int(os.getenv("BOARD_CHANNEL"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

logging.basicConfig(level=logging.INFO)

# ---------------- JSON FUNCTIONS ----------------

def load_channels():
    with open("channels.json") as f:
        return json.load(f)["channels"]


def save_channels(channels):
    with open("channels.json", "w") as f:
        json.dump({"channels": channels}, f, indent=2)


def load_posts():
    with open("posts.json") as f:
        return json.load(f)


def save_posts(data):
    with open("posts.json", "w") as f:
        json.dump(data, f, indent=2)


# ---------------- ADMIN PANEL ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Channel", callback_data="add_channel")],
        [InlineKeyboardButton("➖ Remove Channel", callback_data="remove_channel")],
        [InlineKeyboardButton("📋 List Channels", callback_data="list_channels")]
    ]

    await update.message.reply_text(
        "⚙️ Admin Panel",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- ADD CHANNEL ----------------

async def add_channel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    context.user_data["mode"] = "add"

    await query.message.reply_text(
        "Send channel ID to add\nExample:\n-100xxxxxxxxxx"
    )


# ---------------- REMOVE CHANNEL ----------------

async def remove_channel_button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    channels = load_channels()

    if not channels:
        await query.message.reply_text("❌ No channels added")
        return

    keyboard = []

    for ch in channels:

        try:
            chat = await context.bot.get_chat(ch)
            name = chat.title
        except:
            name = str(ch)

        keyboard.append(
            [InlineKeyboardButton(name, callback_data=f"removech_{ch}")]
        )

    await query.message.reply_text(
        "Select channel to remove",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def remove_channel_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    channel_id = int(query.data.split("_")[1])

    channels = load_channels()

    if channel_id in channels:

        channels.remove(channel_id)
        save_channels(channels)

        await query.edit_message_text("❌ Channel removed successfully")

    else:

        await query.edit_message_text("Channel not found")


# ---------------- LIST CHANNELS ----------------

async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    channels = load_channels()

    if not channels:
        text = "❌ No channels added"
    else:

        text = "📋 Current Channels:\n\n"

        for ch in channels:

            try:
                chat = await context.bot.get_chat(ch)
                text += f"{chat.title} ({ch})\n"
            except:
                text += f"{ch}\n"

    await query.message.reply_text(text)


# ---------------- RECEIVE CHANNEL ID ----------------

async def receive_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        return

    if "mode" not in context.user_data:
        return

    try:
        channel_id = int(update.message.text)
    except:
        await update.message.reply_text("Invalid ID")
        return

    channels = load_channels()

    if context.user_data["mode"] == "add":

        if channel_id not in channels:

            channels.append(channel_id)
            save_channels(channels)

            await update.message.reply_text("✅ Channel added")

        else:

            await update.message.reply_text("Channel already exists")

    context.user_data.clear()


# ---------------- RECEIVE BOARD POST ----------------

async def receive_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.channel_post:
        return

    if update.channel_post.chat.id != BOARD_CHANNEL:
        return

    msg = update.channel_post

    channels = load_channels()
    posts = load_posts()

    sent_messages = []

    for channel in channels:

        try:

            sent = await context.bot.copy_message(
                chat_id=channel,
                from_chat_id=BOARD_CHANNEL,
                message_id=msg.message_id
            )

            sent_messages.append([channel, sent.message_id])

        except Exception as e:
            print(e)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Delete Post", callback_data=f"delete_{msg.message_id}")]
    ])

    await context.bot.send_message(
        chat_id=BOARD_CHANNEL,
        text="⚙️ Post Control Panel",
        reply_markup=keyboard
    )

    posts[str(msg.message_id)] = sent_messages
    save_posts(posts)


# ---------------- DELETE POST ----------------

async def delete_post(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("Not admin", show_alert=True)
        return

    msg_id = query.data.split("_")[1]

    posts = load_posts()

    if msg_id not in posts:
        await query.edit_message_text("Post not found")
        return

    for channel, message in posts[msg_id]:

        try:
            await context.bot.delete_message(
                chat_id=channel,
                message_id=message
            )
        except:
            pass

    await query.edit_message_text("✅ Post deleted everywhere")


# ---------------- MAIN ----------------

def main():

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(filters.TEXT & filters.User(ADMIN_ID), receive_channel_id)
    )

    app.add_handler(
        MessageHandler(filters.ALL & filters.Chat(BOARD_CHANNEL), receive_channel)
    )

    app.add_handler(
        CallbackQueryHandler(add_channel_button, pattern="add_channel")
    )

    app.add_handler(
        CallbackQueryHandler(remove_channel_button, pattern="remove_channel")
    )

    app.add_handler(
        CallbackQueryHandler(remove_channel_confirm, pattern="removech_")
    )

    app.add_handler(
        CallbackQueryHandler(list_channels, pattern="list_channels")
    )

    app.add_handler(
        CallbackQueryHandler(delete_post, pattern="delete_")
    )

    print("🚀 Bot Running...")

    app.run_polling()


if __name__ == "__main__":
    main()

import os
import time
import requests
import asyncio
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

AVAILABLE = ["متوفر", "available", "in stock"]
UNAVAILABLE = ["غير متوفر", "unavailable", "out of stock", "نفدت", "مباع"]

user_state = {}
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = "awaiting_url"
    await update.message.reply_text(
        """👋 أهلاً بك في بوت مراقبة المنتجات!

🔗 أرسل رابط المنتج الآن،
وسأتحقق من توفره وسعره، ثم أتابعه لك باستمرار.
"""
    )

def check_product(url):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text().lower()

        available = any(word in text for word in AVAILABLE)
        unavailable = any(word in text for word in UNAVAILABLE)
        price = ""

        for tag in soup.find_all(["span", "div"]):
            if any(p in tag.text.lower() for p in ["sar", "usd", "$", "ريال"]):
                price = tag.text.strip()
                break

        if available:
            return "متوفر", price
        elif unavailable:
            return "غير متوفر", price
        else:
            return "غير واضح", price
    except:
        return "خطأ", ""

async def ask_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⏱️ كل 5 دقائق", callback_data="5")],
        [InlineKeyboardButton("⏱️ كل 15 دقيقة", callback_data="15")],
        [InlineKeyboardButton("⏱️ كل 30 دقيقة", callback_data="30")],
        [InlineKeyboardButton("⏱️ كل ساعة", callback_data="60")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("كل كم دقيقة تبي أشيك؟", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = update.message.text.strip()

    if user_state.get(user_id) == "awaiting_url":
        if msg.startswith("http"):
            status, price = check_product(msg)
            user_data[user_id] = {
                "url": msg,
                "interval": 0,
                "last_status": status,
                "last_price": price
            }
            user_state[user_id] = "awaiting_interval"

            if status == "متوفر":
                await update.message.reply_text(
                    f"✅ *المنتج متوفر!*\n💰 السعر: {price or 'غير معروف'}",
                    parse_mode="Markdown"
                )
            elif status == "غير متوفر":
                await update.message.reply_text("❌ المنتج غير متوفر حالياً.")
            else:
                await update.message.reply_text("⚠️ ما قدرت أتحقق من حالة المنتج.")

            await ask_interval(update, context)
        else:
            await update.message.reply_text("📎 أرسل رابط صحيح يبدأ بـ http")
    else:
        await update.message.reply_text("💡 ابدأ بـ /start")

async def handle_interval_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    interval = int(query.data)

    if user_id in user_data:
        user_data[user_id]["interval"] = interval
        user_state[user_id] = "monitoring"

        await query.edit_message_text(f"✅ تمام! راح أشيك كل {interval} دقيقة 👀")
    else:
        await query.edit_message_text("⚠️ حصل خطأ، ابدأ من جديد بـ /start")

async def monitor_products(app):
    while True:
        for user_id, data in user_data.items():
            if user_state.get(user_id) == "monitoring":
                status, price = check_product(data["url"])
                notify = False
                msg = ""

                if status != data["last_status"]:
                    notify = True
                    msg += f"🔔 *تحديث حالة المنتج!*\nمن: {data['last_status']} ➡️ إلى: {status}"
                    data["last_status"] = status

                if price and price != data["last_price"]:
                    notify = True
                    msg += f"\n💰 *تغير السعر!*\nمن: {data['last_price'] or 'غير معروف'} ➡️ إلى: {price}"
                    data["last_price"] = price

                if notify:
                    try:
                        await app.bot.send_message(chat_id=user_id, text=msg, parse_mode="Markdown")
                    except:
                        pass

        await asyncio.sleep(60)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(handle_interval_selection))

async def main():
    asyncio.create_task(monitor_products(app))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())

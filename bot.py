
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
user_data = {}  # user_id: {url, interval, last_status, last_price}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state[user_id] = "awaiting_url"
    await update.message.reply_text("""أهلاً أهلاً بك في بوت مراقبة المنتجات!

رابط أرسل رابط المنتج الآن.""")

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
        [InlineKeyboardButton("مدة كل 5 دقائق", callback_data="5")],
        [InlineKeyboardButton("مدة كل 15 دقيقة", callback_data="15")],
        [InlineKeyboardButton("مدة كل 30 دقيقة", callback_data="30")],
        [InlineKeyboardButton("مدة كل ساعة", callback_data="60")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("كم مرة تبيني أشيك على توفر المنتج؟", reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text.strip()

    if user_state.get(user_id) == "awaiting_url":
        if message.startswith("http"):
            status, price = check_product(message)
            user_data[user_id] = {
                "url": message,
                "interval": 0,
                "last_status": status,
                "last_price": price
            }
            user_state[user_id] = "awaiting_interval"

            await update.message.reply_text("تم استلام الرابط بنجاح.\nسيتم التحقق من توفر المنتج الآن...")
            await asyncio.sleep(1)

            if status == "متوفر":
                await update.message.reply_text(f"""✅ *المنتج متوفر!*

💵 *السعر:* {price or 'غير معروف'}
🌐 [رابط المنتج]({message})""", parse_mode="Markdown")

💵 *السعر:* {price or 'غير معروف'}
🌐 [رابط المنتج]({message})", parse_mode="Markdown")
            elif status == "غير متوفر":
                await update.message.reply_text(f"""❌ *المنتج غير متوفر حالياً!*
🌐 [رابط المنتج]({message})""", parse_mode="Markdown")
🌐 [رابط المنتج]({message})", parse_mode="Markdown")
            else:
                await update.message.reply_text("تنبيه لم أتمكن من تحديد حالة المنتج بدقة.")

            await ask_interval(update, context)
        else:
            await update.message.reply_text("📎 أرسل رابط صحيح يبدأ بـ http")
    else:
        await update.message.reply_text("معلومة ابدأ باستخدام الأمر /start")

async def handle_interval_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    interval = int(query.data)

    if user_id in user_data:
        user_data[user_id]["interval"] = interval
        user_state[user_id] = "monitoring"

        await query.edit_message_text(f"""✅ تم تحديد المدة: كل {interval} دقيقة
🔁 سأقوم بمتابعة المنتج بشكل مستمر.""")
    else:
        await query.edit_message_text("تنبيه حدث خطأ، يرجى البدء من جديد بـ /start")

# المراقبة المستمرة
async def monitor_products(app):
    while True:
        now = time.time()
        for user_id, data in user_data.items():
            if user_state.get(user_id) == "monitoring":
                status, price = check_product(data["url"])
                notify = False
                msg = ""

                if status != data["last_status"]:
                    notify = True
                    msg += f"""🔄 *تحديث في حالة المنتج!*
من: {data['last_status']}
إلى: {status}"""
                    data["last_status"] = status

                if price and price != data["last_price"]:
                    notify = True
                    msg += f"""💰 *السعر تغيّر!*
من: {data['last_price'] or 'غير معروف'}
إلى: {price}"""
                    data["last_price"] = price

                if notify:
                    try:
                        await app.bot.send_message(chat_id=user_id, text=msg + f"""\n🌐 [رابط المنتج]({data['url']})""", parse_mode="Markdown")
                    except:
                        pass

        await asyncio.sleep(60)

# التشغيل
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(handle_interval_selection))

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(monitor_products(app))
    app.run_polling()

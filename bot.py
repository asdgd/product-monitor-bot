
import os
import requests
from bs4 import BeautifulSoup
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

AVAILABLE = ["متوفر", "available", "in stock"]
UNAVAILABLE = ["غير متوفر", "unavailable", "out of stock", "نفدت", "مباع"]

awaiting_links = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    awaiting_links[user_id] = True
    await update.message.reply_text("أهلًا بك! أرسل لي رابط المنتج اللي تبي أشيك عليه.")

def check_product(url):
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text().lower()

        available = any(word in text for word in AVAILABLE)
        unavailable = any(word in text for word in UNAVAILABLE)
        price = ""

        for tag in soup.find_all(["span", "div"]):
            if any(p in tag.text.lower() for p in ['sar', 'usd', '$', 'ريال']):
                price = tag.text.strip()
                break

        if available:
            return "متوفر", price
        elif unavailable:
            return "غير متوفر", price
        else:
            return "غير واضح", price
    except Exception:
        return "خطأ أثناء التحقق", ""

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.message.text.strip()

    if awaiting_links.get(user_id):
        if message.startswith("http"):
            status, price = check_product(message)
            if status == "متوفر":
                await update.message.reply_text(f"""✅ المنتج متوفر!
السعر: {price or "غير معروف"}""")
            elif status == "غير متوفر":
                await update.message.reply_text(f"❌ المنتج غير متوفر حالياً.
راح أبحث لك عن بدائل...")
            elif status == "غير واضح":
                await update.message.reply_text("ما قدرت أحدد إذا المنتج متوفر أو لا.")
            else:
                await update.message.reply_text("حصل خطأ أثناء محاولة قراءة الرابط.")
            awaiting_links[user_id] = False
        else:
            await update.message.reply_text("أرسل رابط صالح يبدأ بـ http")
    else:
        await update.message.reply_text("اكتب /start علشان أبدأ معك من جديد.")

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    app.run_polling()

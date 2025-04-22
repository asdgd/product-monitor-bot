
import os
import time
import sqlite3
import requests
import openai
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "PUT_YOUR_OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

conn = sqlite3.connect("products.db", check_same_thread=False)
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id TEXT, url TEXT, interval INTEGER, last_price TEXT, last_checked REAL)")
conn.commit()

AVAILABLE = ["متوفر", "available", "in stock"]
UNAVAILABLE = ["غير متوفر", "unavailable", "out of stock", "نفدت", "مباع"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    welcome_msg = f"""أهلاً وسهلاً {name}!

أنا مساعدك الذكي في متابعة المنتجات من أي متجر.

**وش أقدر أسوي لك؟**
- أتابع أي رابط منتج وترى إذا كان متوفر أو لا
- أنبهك لو السعر تغيّر
- أجاوب على أسئلتك باستخدام الذكاء الاصطناعي

**طريقة الاستخدام:**
أرسل:
/add [الرابط] [الدقائق]
مثال:
/add https://example.com 10

وجرب تكلمني بأي رسالة عادية، وشوف كيف أجاوبك!

بالتوفيق يالغالي!
"""
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("الصيغة الصحيحة: /add [الرابط] [الدقائق]")
        return
    url = context.args[0]
    try:
        interval = int(context.args[1])
    except:
        await update.message.reply_text("يرجى تحديد عدد الدقائق بشكل صحيح.")
        return
    user_id = str(update.effective_user.id)
    c.execute("INSERT INTO watchlist (user_id, url, interval, last_price, last_checked) VALUES (?, ?, ?, ?, ?)",
              (user_id, url, interval, '', 0))
    conn.commit()
    await update.message.reply_text(f"تمت إضافة المنتج للمراقبة كل {interval} دقيقة.")

def check_product(url):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text().lower()

        availability = None
        for word in AVAILABLE:
            if word in text:
                availability = True
        for word in UNAVAILABLE:
            if word in text:
                availability = False

        price = ''
        for tag in soup.find_all(['span', 'div']):
            if tag and any(s in tag.text.lower() for s in ['sar', '$', 'ريال', 'usd']):
                price = tag.text.strip()
                break
        return availability, price
    except:
        return None, None

async def ai_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = update.message.text
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        reply = response.choices[0].message.content.strip()
    except Exception:
        reply = "حدث خطأ أثناء الاتصال بالذكاء الاصطناعي."
    await update.message.reply_text(reply)

async def monitor(app):
    while True:
        rows = c.execute("SELECT rowid, user_id, url, interval, last_price, last_checked FROM watchlist").fetchall()
        now = time.time()
        for row in rows:
            rowid, user_id, url, interval, last_price, last_checked = row
            if now - last_checked >= interval * 60:
                available, price = check_product(url)
                msg = ""
                if available is True:
                    msg += f"✅ المنتج متوفر الآن!\n{url}"
                elif available is False:
                    msg += f"❌ المنتج غير متوفر حالياً.\n{url}"
                if price and price != last_price:
                    msg += f"\n💰 السعر تغير:\nمن: {last_price or 'غير معروف'}\nإلى: {price}"
                c.execute("UPDATE watchlist SET last_checked = ?, last_price = ? WHERE rowid = ?", (now, price, rowid))
                conn.commit()
                if msg:
                    try:
                        await app.bot.send_message(chat_id=int(user_id), text=msg)
                    except:
                        pass
        await asyncio.sleep(30)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_reply))

loop = asyncio.get_event_loop()
loop.create_task(monitor(app))
app.run_polling()

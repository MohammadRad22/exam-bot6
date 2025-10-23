import asyncio
import random
import csv
import os
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ==============================
# 🔹 تنظیمات اصلی
# ==============================
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8475437543:AAG75xruJgLyAJnyD7WGsZlpsZu3dWs_ejE")  # استفاده از متغیر محیطی
ADMIN_ID = 677533280  # آیدی عددی ادمین
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://exam-bot6-1.onrender.com")  # بدون اسلش انتهایی
RESULTS_FILE = "results.csv"
EXAM_DURATION = 15 * 60  # ۱۵ دقیقه

# ==============================
# 🔹 Flask برای دریافت Webhook
# ==============================
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Bot is running!"

@flask_app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    await app.process_update(update)  # استفاده مستقیم از await
    return "OK", 200

# ==============================
# 🔹 داده‌ها
# ==============================
if not os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Student ID", "User ID", "Score", "Percent"])

QUESTIONS = [
    {"q": "پایتخت ایران کجاست؟", "options": ["مشهد", "تهران", "اصفهان", "تبریز"], "answer": 1},
    {"q": "عدد پی تقریباً چند است؟", "options": ["2.14", "3.14", "4.13", "2.71"], "answer": 1},
    {"q": "در کدام فصل بارش برف بیشتر است؟", "options": ["تابستان", "پاییز", "زمستان", "بهار"], "answer": 2},
    {"q": "نویسنده شاهنامه کیست؟", "options": ["سعدی", "مولوی", "فردوسی", "حافظ"], "answer": 2},
    {"q": "نخستین سیاره منظومه شمسی؟", "options": ["زهره", "عطارد", "مریخ", "زحل"], "answer": 1},
    {"q": "کدام عنصر نماد شیمیایی O دارد؟", "options": ["نیتروژن", "اکسیژن", "آهن", "کربن"], "answer": 1},
    {"q": "واحد سنجش توان چیست؟", "options": ["وات", "ژول", "ولت", "آمپر"], "answer": 0},
    {"q": "سریع‌ترین حیوان روی زمین؟", "options": ["یوزپلنگ", "اسب", "شیر", "ببر"], "answer": 0},
]

user_data = {}

# ==============================
# 🔹 /start
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data and user_data[user_id].get("completed"):
        await update.message.reply_text("⚠️ شما قبلاً در این آزمون شرکت کرده‌اید.")
        return
    user_data[user_id] = {"stage": "name"}
    await update.message.reply_text("👋 لطفاً نام و نام خانوادگی خود را وارد کنید:")

# ==============================
# 🔹 دریافت نام و شماره دانشجویی
# ==============================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_data:
        await update.message.reply_text("برای شروع آزمون دستور /start را بزنید.")
        return

    stage = user_data[user_id].get("stage")

    if stage == "name":
        user_data[user_id]["name"] = text
        user_data[user_id]["stage"] = "student_id"
        await update.message.reply_text("📘 شماره دانشجویی خود را وارد کنید:")
    elif stage == "student_id":
        user_data[user_id]["student_id"] = text
        user_data[user_id]["stage"] = "ready"
        await show_rules(update, context)

# ==============================
# 🔹 مقررات آزمون
# ==============================
async def show_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules = (
        "📜 **مقررات آزمون:**\n\n"
        "1️⃣ آزمون دارای *نمره منفی* است.\n"
        "2️⃣ مدت زمان پاسخ‌گویی *۱۵ دقیقه* است.\n"
        "3️⃣ با زدن دکمه زیر آزمون آغاز می‌شود.\n\n"
        "آیا آماده‌اید؟ 🚀"
    )
    button = InlineKeyboardMarkup([[InlineKeyboardButton("✅ شروع آزمون", callback_data="start_exam")]])
    await update.message.reply_text(rules, parse_mode="Markdown", reply_markup=button)

# ==============================
# 🔹 دکمه‌ها
# ==============================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = user_data.get(user_id, {})
    await query.answer()

    if query.data == "start_exam":
        await query.edit_message_text("🟢 آزمون آغاز شد! موفق باشید 🌟")
        await asyncio.sleep(0.5)
        await start_exam(context, user_id)
        return

    if "questions" not in data or data.get("completed"):
        return

    q = data["questions"][data["index"]]
    answer = query.data

    if answer == "skip":
        pass
    elif answer == "end_exam":
        await query.edit_message_text("📤 آزمون پایان یافت.")
        await finish_exam(context, user_id)
        return
    else:
        answer = int(answer)
        if answer == q["answer"]:
            data["score"] += 1
        else:
            data["score"] -= 0.5

    data["index"] += 1

    if data["index"] >= len(data["questions"]):
        await finish_exam(context, user_id)
    else:
        await send_next_question(context, user_id)

# ==============================
# 🔹 شروع آزمون
# ==============================
async def start_exam(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    data = user_data[user_id]
    data["questions"] = random.sample(QUESTIONS, len(QUESTIONS))
    data["index"] = 0
    data["score"] = 0
    data["completed"] = False
    asyncio.create_task(exam_timer(context, user_id))
    await send_next_question(context, user_id)

# ==============================
# 🔹 تایمر
# ==============================
async def exam_timer(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    await asyncio.sleep(EXAM_DURATION)
    data = user_data.get(user_id)
    if data and not data.get("completed"):
        await context.bot.send_message(chat_id=user_id, text="⏰ زمان آزمون به پایان رسید!")
        await finish_exam(context, user_id)

# ==============================
# 🔹 ارسال سوال بعدی
# ==============================
async def send_next_question(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    data = user_data[user_id]
    q = data["questions"][data["index"]]
    buttons = [[InlineKeyboardButton(opt, callback_data=str(i))] for i, opt in enumerate(q["options"])]
    if data["index"] == len(data["questions"]) - 1:
        buttons.append([InlineKeyboardButton("📤 پایان آزمون", callback_data="end_exam")])
    else:
        buttons.append([InlineKeyboardButton("⏭ رد کردن", callback_data="skip")])
    await context.bot.send_message(
        chat_id=user_id,
        text=f"❓ سؤال {data['index'] + 1} از {len(data['questions'])}\n\n{q['q']}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ==============================
# 🔹 پایان آزمون
# ==============================
async def finish_exam(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    data = user_data[user_id]
    if data.get("completed"):
        return
    data["completed"] = True

    total = len(data["questions"])
    percent = max((data["score"] / total) * 100, 0)
    name = data["name"]
    student_id = data["student_id"]

    with open(RESULTS_FILE, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([name, student_id, user_id, data["score"], f"{percent:.1f}%"])

    # پیام برای کاربر
    await context.bot.send_message(
        chat_id=user_id,
        text=f"✅ آزمون پایان یافت!\n📊 نمره: {data['score']} از {total}\nدرصد: {percent:.1f}%"
    )

    # پیام برای ادمین
    msg = (
        f"📋 نتیجه آزمون جدید:\n\n"
        f"👤 نام: {name}\n"
        f"🎓 شماره دانشجویی: {student_id}\n"
        f"🆔 کاربر: {user_id}\n"
        f"📊 نمره: {data['score']} از {total}\n"
        f"درصد: {percent:.1f}%"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg)
    except Exception as e:
        print("خطا در ارسال نتیجه به ادمین:", e)

# ==============================
# 🔹 پیکربندی و اجرا
# ==============================
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(button_handler))

async def set_webhook():
    try:
        await app.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")
        print("✅ Webhook set successfully!")
    except Exception as e:
        print(f"❌ Error setting webhook: {e}")

async def main():
    # مقداردهی اولیه اپلیکیشن
    await app.initialize()
    # تنظیم Webhook
    await set_webhook()
    # اجرای سرور Flask
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    asyncio.run(main())

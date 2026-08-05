import asyncio
import aiosqlite
import random
import string
import threading

from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.filters import CommandStart

from config import BOT_TOKEN, ADMIN_ID

# ========== راه‌اندازی ربات ==========
bot = Bot(BOT_TOKEN)
dp = Dispatcher()
DB = "database.db"

# ========== وب‌سرور برای Render ==========
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "ربات زنده است! 🤖"

def run_webserver():
    web_app.run(host='0.0.0.0', port=8080)

# ========== کیبوردها ==========
user_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📂 دریافت فایل")],
        [KeyboardButton(text="👤 حساب کاربری"), KeyboardButton(text="⭐ VIP")],
        [KeyboardButton(text="📞 پشتیبانی"), KeyboardButton(text="✏️ درخواست فونت")],
        [KeyboardButton(text="ℹ️ درباره ما")]
    ],
    resize_keyboard=True
)

verify_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 ارسال شماره", request_contact=True)]
    ],
    resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📤 آپلود فایل")],
        [KeyboardButton(text="👥 کاربران")]
    ],
    resize_keyboard=True
)

# ========== دیتابیس ==========
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                phone TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                file_id TEXT
            )
        """)
        await db.commit()

def create_code():
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(8))

# ========== دستورات ربات ==========
@dp.message(CommandStart())
async def start(message: Message):
    args = message.text.split()

    # دریافت فایل با لینک اختصاصی
    if len(args) > 1:
        code = args[1]
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("SELECT file_id FROM files WHERE code=?", (code,))
            file = await cur.fetchone()

        if file:
            await message.answer_document(file[0])
        else:
            await message.answer("❌ فایل پیدا نشد")
        return

    # بررسی احراز هویت
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
        user = await cur.fetchone()

    if not user:
        await message.answer(
            "🔐 برای استفاده از ربات ابتدا شماره خود را ارسال کنید:",
            reply_markup=verify_keyboard
        )
        return

    # پنل مدیریت یا کاربر عادی
    if message.from_user.id == ADMIN_ID:
        await message.answer("👨‍💻 پنل مدیریت", reply_markup=admin_keyboard)
    else:
        await message.answer("🌟 خوش آمدید", reply_markup=user_keyboard)

# ========== احراز هویت شماره ==========
@dp.message(F.contact)
async def verify_phone(message: Message):
    if message.contact.user_id != message.from_user.id:
        await message.answer("❌ لطفاً شماره خودتان را ارسال کنید")
        return

    phone = message.contact.phone_number.replace(" ", "")

    if phone.startswith("0098"):
        phone = "+" + phone[2:]
    elif phone.startswith("98"):
        phone = "+" + phone

    if not phone.startswith("+98"):
        await message.answer("❌ فقط شماره ایران مجاز است")
        return

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (user_id, phone) VALUES (?,?)",
            (message.from_user.id, phone)
        )
        await db.commit()

    await message.answer(
        "✅ احراز هویت با موفقیت انجام شد",
        reply_markup=user_keyboard
    )

# ========== آپلود فایل ادمین ==========
@dp.message(F.document)
async def upload_file(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    code = create_code()
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO files (code, file_id) VALUES (?,?)",
            (code, message.document.file_id)
        )
        await db.commit()

    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={code}"

    await message.answer(
        f"✅ فایل ذخیره شد\n\n🔗 لینک اختصاصی:\n{link}"
    )

# ========== لیست کاربران ==========
@dp.message(F.text == "👥 کاربران")
async def users_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT user_id, phone FROM users")
        users = await cur.fetchall()

    if not users:
        await message.answer("❌ هنوز کاربری ثبت نشده است")
        return

    text = f"👥 تعداد کاربران: {len(users)}\n\n"
    for index, user in enumerate(users, start=1):
        text += f"{index}) 🆔 {user[0]}\n📱 {user[1]}\n\n"

    await message.answer(text)

# ========== حساب کاربری ==========
@dp.message(F.text == "👤 حساب کاربری")
async def account(message: Message):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
        user = await cur.fetchone()

    await message.answer(
        f"👤 حساب کاربری\n\n"
        f"🆔 آیدی: {message.from_user.id}\n"
        f"📱 شماره: {user[0] if user else 'ثبت نشده'}\n"
        f"👤 نام: {message.from_user.full_name}"
    )

# ========== VIP ==========
@dp.message(F.text == "⭐ VIP")
async def vip(message: Message):
    await message.answer(
        "👑 **عضویت ویژه VIP**\n\n"
        "مزایای عضویت VIP:\n"
        "✅ دانلود نامحدود فایل‌ها\n"
        "✅ دسترسی به فونت‌های اختصاصی\n"
        "✅ پشتیبانی ویژه\n"
        "✅ تخفیف ۳۰٪ برای همه محصولات\n\n"
        "💰 هزینه عضویت: ۵۰,۰۰۰ تومان (مادام‌العمر)\n\n"
        "برای ثبت‌نام، با پشتیبانی تماس بگیرید:\n"
        "📞 @Font1403_Support"
    )

# ========== درخواست فونت ==========
@dp.message(F.text == "✏️ درخواست فونت")
async def request_font(message: Message):
    await message.answer(
        "✏️ **درخواست فونت جدید**\n\n"
        "اگر فونتی مد نظرت هست که در مجموعه ما نیست، می‌تونی درخواست بدی.\n\n"
        "📝 لطفاً مشخصات فونت مورد نظرت رو به صورت زیر برای ما ارسال کن:\n"
        "```\n"
        "نام فونت: \n"
        "سبک: (ساده/کامل/تزئینی/خط)\n"
        "کاربرد: (طراحی/چاپ/وب/موبایل)\n"
        "توضیحات بیشتر: \n"
        "```\n\n"
        "📎 درخواست خود را به آیدی زیر ارسال کن:\n"
        "@Font1403_Request"
    )

# ========== پشتیبانی ==========
@dp.message(F.text == "📞 پشتیبانی")
async def support(message: Message):
    await message.answer(
        "📞 پشتیبانی\n\n"
        "برای ارتباط با پشتیبانی:\n\n"
        "https://t.me/XBCHATBot?start=sec-bgcabcgba"
    )


# ========== درباره ما ==========
@dp.message(F.text == "ℹ️ درباره ما")
async def about(message: Message):
    await message.answer(
        "ℹ️ درباره ما\n\n"
        "به ربات رسمی مجموعه Font1403 خوش آمدید 🌟\n\n"
        "در این ربات می‌توانید به‌صورت سریع و آسان فایل‌های مورد نیاز خود را دریافت کنید.\n\n"
        "📂 ارائه مجموعه‌ای از فونت‌ها، فایل‌های طراحی و منابع گرافیکی\n"
        "⚡ دریافت سریع و آسان فایل‌ها با لینک اختصاصی\n"
        "🔒 حفظ امنیت و مدیریت بهتر فایل‌ها\n\n"
        "برای مشاهده جدیدترین فایل‌ها و مطالب آموزشی، به کانال ما بپیوندید:\n\n"
        "📢 کانال رسمی:\n"
        "https://t.me/Font1403\n\n"
        "با حمایت شما، هر روز تلاش می‌کنیم منابع بهتر و کاربردی‌تری ارائه کنیم ❤️"
    )

# ========== دریافت فایل ==========
@dp.message(F.text == "📂 دریافت فایل")
async def get_file(message: Message):
    await message.answer("🔗 لینک اختصاصی فایل را ارسال کنید.")

# ========== اجرای ربات ==========
async def main():
    await init_db()
    print("✅ Bot Started")

    # اجرای وب‌سرور در پس‌زمینه
    threading.Thread(target=run_webserver, daemon=True).start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

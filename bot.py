import asyncio
import aiosqlite
import random
import string
import threading
from datetime import datetime, timedelta

from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
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
    return "ربات Font1403 زنده است! 🤖"

def run_webserver():
    web_app.run(host='0.0.0.0', port=8080)

# ========== دیتابیس ==========
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id INTEGER PRIMARY KEY,
                phone TEXT,
                is_vip INTEGER DEFAULT 0,
                vip_expiry TEXT,
                discount_code TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS files(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                file_id TEXT,
                is_free INTEGER DEFAULT 1,
                is_vip INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes(
                code TEXT PRIMARY KEY,
                discount_percent INTEGER,
                expires_at TEXT,
                used_by TEXT
            )
        """)
        await db.commit()

# ========== کیبورد اصلی کاربر ==========
user_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📂 فایل ویژه"), KeyboardButton(text="📁 فایل رایگان")],
        [KeyboardButton(text="💎 خرید اشتراک VIP"), KeyboardButton(text="✏️ درخواست فونت")],
        [KeyboardButton(text="🎫 کد تخفیف"), KeyboardButton(text="💰 کمک مالی")],
        [KeyboardButton(text="ℹ️ درباره ما"), KeyboardButton(text="📞 پشتیبانی")]
    ],
    resize_keyboard=True
)

# ========== کیبورد احراز هویت ==========
verify_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 ارسال شماره", request_contact=True)]
    ],
    resize_keyboard=True
)

# ========== کیبورد ادمین ==========
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📤 آپلود فایل ویژه")],
        [KeyboardButton(text="📤 آپلود فایل رایگان")],
        [KeyboardButton(text="👥 کاربران")],
        [KeyboardButton(text="🎫 ساخت کد تخفیف")],
        [KeyboardButton(text="📊 آمار")]
    ],
    resize_keyboard=True
)

# ========== توابع کمکی ==========
def create_code():
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(8))

def is_vip_expired(expiry_date):
    if not expiry_date:
        return True
    expiry = datetime.fromisoformat(expiry_date)
    return datetime.now() > expiry

# ========== احراز هویت ==========
async def check_auth(message: Message):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,))
        user = await cur.fetchone()
    return user is not None

@dp.message(CommandStart())
async def start(message: Message):
    args = message.text.split()

    # دریافت فایل با لینک اختصاصی
    if len(args) > 1:
        code = args[1]
        async with aiosqlite.connect(DB) as db:
            cur = await db.execute("SELECT file_id, is_free, is_vip FROM files WHERE code=?", (code,))
            file = await cur.fetchone()

        if not file:
            await message.answer("❌ فایل پیدا نشد")
            return

        # بررسی دسترسی VIP
        if file[2] == 1:  # فایل VIP
            async with aiosqlite.connect(DB) as db:
                cur = await db.execute("SELECT is_vip, vip_expiry FROM users WHERE user_id=?", (message.from_user.id,))
                user = await cur.fetchone()
            
            if not user or user[0] == 0 or is_vip_expired(user[1]):
                await message.answer("🔒 این فایل مخصوص کاربران VIP است.\nبرای دسترسی، اشتراک VIP تهیه کنید.")
                return

        await message.answer_document(file[1])
        return

    # احراز هویت
    if not await check_auth(message):
        await message.answer(
            "🔐 لطفاً برای استفاده از ربات، شماره خود را ارسال کنید:",
            reply_markup=verify_keyboard
        )
        return

    # پنل ادمین یا کاربر
    if message.from_user.id == ADMIN_ID:
        await message.answer("👨‍💻 پنل مدیریت", reply_markup=admin_keyboard)
    else:
        await message.answer("🌟 به ربات Font1403 خوش آمدید!", reply_markup=user_keyboard)

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
        "✅ احراز هویت با موفقیت انجام شد!",
        reply_markup=user_keyboard
    )

# ========== فایل ویژه (VIP) ==========
@dp.message(F.text == "📂 فایل ویژه")
async def vip_files(message: Message):
    if not await check_auth(message):
        await message.answer("🔐 ابتدا شماره خود را ارسال کنید.", reply_markup=verify_keyboard)
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT is_vip, vip_expiry FROM users WHERE user_id=?", (message.from_user.id,))
        user = await cur.fetchone()

    if not user or user[0] == 0 or is_vip_expired(user[1]):
        await message.answer(
            "🔒 **فایل‌های ویژه**\n\n"
            "این بخش مخصوص کاربران VIP است.\n"
            "برای دسترسی، اشتراک VIP تهیه کنید.\n\n"
            "💎 از دکمه `خرید اشتراک VIP` استفاده کنید."
        )
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT code, file_id FROM files WHERE is_vip=1")
        files = await cur.fetchall()

    if not files:
        await message.answer("📂 فایل ویژه‌ای موجود نیست.")
        return

    for file in files:
        link = f"https://t.me/{(await bot.get_me()).username}?start={file[0]}"
        await message.answer(f"🔗 لینک فایل ویژه:\n{link}")

# ========== فایل رایگان ==========
@dp.message(F.text == "📁 فایل رایگان")
async def free_files(message: Message):
    if not await check_auth(message):
        await message.answer("🔐 ابتدا شماره خود را ارسال کنید.", reply_markup=verify_keyboard)
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT code, file_id FROM files WHERE is_free=1 AND is_vip=0")
        files = await cur.fetchall()

    if not files:
        await message.answer("📂 فایل رایگانی موجود نیست.")
        return

    for file in files:
        link = f"https://t.me/{(await bot.get_me()).username}?start={file[0]}"
        await message.answer(f"🔗 لینک فایل رایگان:\n{link}")

# ========== خرید اشتراک VIP ==========
@dp.message(F.text == "💎 خرید اشتراک VIP")
async def buy_vip(message: Message):
    if not await check_auth(message):
        await message.answer("🔐 ابتدا شماره خود را ارسال کنید.", reply_markup=verify_keyboard)
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗓️ ۱ ماهه - ۲۰,۰۰۰ تومان", callback_data="vip_1month")],
            [InlineKeyboardButton(text="🗓️ ۳ ماهه - ۵۰,۰۰۰ تومان", callback_data="vip_3month")],
            [InlineKeyboardButton(text="🗓️ ۱ ساله - ۱۵۰,۰۰۰ تومان", callback_data="vip_1year")]
        ]
    )

    await message.answer(
        "💎 **خرید اشتراک VIP**\n\n"
        "مزایای VIP:\n"
        "✅ دانلود فایل‌های ویژه\n"
        "✅ دسترسی به فونت‌های اختصاصی\n"
        "✅ پشتیبانی اولویت‌دار\n"
        "✅ تخفیف ۲۰٪ در خرید‌ها\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=keyboard
    )

# ========== پرداخت VIP ==========
@dp.callback_query(lambda c: c.data.startswith("vip_"))
async def process_vip_payment(callback_query):
    await callback_query.answer()
    
    duration = callback_query.data.split("_")[1]
    prices = {"1month": 20000, "3month": 50000, "1year": 150000}
    price = prices.get(duration, 20000)

    await callback_query.message.edit_text(
        f"💳 **مراحل پرداخت**\n\n"
        f"مبلغ: {price:,} تومان\n\n"
        "برای پرداخت، مبلغ را به کارت زیر واریز کنید:\n"
        "💳 **۶۰۳۷-۹۹۹۸-۷۶۵۴-۳۲۱۰**\n"
        "به نام: **مجموعه Font1403**\n\n"
        "📤 پس از واریز، تصویر فیش را ارسال کنید.\n"
        "آیدی پشتیبانی: @Font1403_Support"
    )

# ========== درخواست فونت ==========
@dp.message(F.text == "✏️ درخواست فونت")
async def request_font(message: Message):
    await message.answer(
        "✏️ **درخواست فونت جدید**\n\n"
        "برای درخواست فونت، اطلاعات زیر رو ارسال کن:\n\n"
        "📝 **نام فونت:** \n"
        "🎨 **سبک:** (ساده/کامل/تزئینی/خط)\n"
        "📱 **کاربرد:** (طراحی/چاپ/وب/موبایل)\n"
        "📝 **توضیحات بیشتر:** \n\n"
        "📤 درخواست خود را به آیدی زیر ارسال کن:\n"
        "@Font1403_Request"
    )

# ========== کد تخفیف ==========
@dp.message(F.text == "🎫 کد تخفیف")
async def discount_code(message: Message):
    if not await check_auth(message):
        await message.answer("🔐 ابتدا شماره خود را ارسال کنید.", reply_markup=verify_keyboard)
        return

    await message.answer(
        "🎫 **کد تخفیف**\n\n"
        "اگر کد تخفیف داری، اینجا وارد کن:\n"
        "کد را به صورت `/discount کد` ارسال کن.\n\n"
        "مثال: `/discount FONT1403`"
    )

@dp.message(F.text.startswith("/discount"))
async def apply_discount(message: Message):
    if not await check_auth(message):
        await message.answer("🔐 ابتدا شماره خود را ارسال کنید.", reply_markup=verify_keyboard)
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❌ فرمت صحیح: `/discount کد`")
        return

    code = parts[1]
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT discount_percent, expires_at, used_by FROM discount_codes WHERE code=?",
            (code,)
        )
        discount = await cur.fetchone()

    if not discount:
        await message.answer("❌ کد تخفیف نامعتبر است.")
        return

    if discount[2]:
        await message.answer("❌ این کد قبلاً استفاده شده است.")
        return

    if discount[1] and datetime.now() > datetime.fromisoformat(discount[1]):
        await message.answer("❌ کد تخفیف منقضی شده است.")
        return

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE discount_codes SET used_by=? WHERE code=?",
            (message.from_user.id, code)
        )
        await db.commit()

    await message.answer(
        f"✅ کد تخفیف با موفقیت اعمال شد!\n"
        f"🎉 {discount[0]}٪ تخفیف دریافت کردی."
    )

# ========== کمک مالی ==========
@dp.message(F.text == "💰 کمک مالی")
async function donation(message: Message):
    await message.answer(
        "💰 **حمایت مالی از مجموعه Font1403**\n\n"
        "با کمک مالی شما، ما می‌تونیم فونت‌های بهتری تولید کنیم.\n\n"
        "💳 **شماره کارت:**\n"
        "`۶۰۳۷-۹۹۹۸-۷۶۵۴-۳۲۱۰`\n"
        "به نام: **مجموعه Font1403**\n\n"
        "🙏 حتی مبلغ کم هم برای ما ارزشمنده!\n"
        "از حمایت شما سپاسگزاریم ❤️"
    )

# ========== درباره ما ==========
@dp.message(F.text == "ℹ️ درباره ما")
async def about(message: Message):
    await message.answer(
        "ℹ️ **درباره مجموعه Font1403**\n\n"
        "ما یک تیم تخصصی در زمینه طراحی و تولید فونت هستیم.\n\n"
        "🎯 **ماموریت ما:**\n"
        "ارائه فونت‌های باکیفیت و استاندارد برای طراحان، چاپخانه‌ها و تولیدکنندگان محتوا.\n\n"
        "📢 **کانال ما:**\n"
        "@Font1403\n\n"
        "با حمایت شما، روز به روز بهتر می‌شیم ❤️"
    )

# ========== پشتیبانی ==========
@dp.message(F.text == "📞 پشتیبانی")
async def support(message: Message):
    await message.answer(
        "📞 **پشتیبانی Font1403**\n\n"
        "سوالات، مشکلات و پیشنهادات خود را با ما در میان بگذارید.\n\n"
        "👤 **پشتیبان:** @Font1403_Support\n"
        "📧 **ایمیل:** support@font1403.ir\n"
        "🌐 **وبسایت:** www.font1403.ir\n\n"
        "ساعت پاسخگویی: ۹ صبح تا ۱۲ شب"
    )

# ========== پنل ادمین ==========
@dp.message(F.text == "👥 کاربران")
async def users_list(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT user_id, phone, is_vip FROM users")
        users = await cur.fetchall()

    if not users:
        await message.answer("❌ هنوز کاربری ثبت نشده است.")
        return

    text = f"👥 **تعداد کل کاربران:** {len(users)}\n\n"
    vip_count = sum(1 for u in users if u[2] == 1)
    text += f"⭐ کاربران VIP: {vip_count}\n\n"
    
    for idx, user in enumerate(users[:20], 1):
        text += f"{idx}. 🆔 {user[0]}\n📱 {user[1]}\n{'⭐ VIP' if user[2] else '👤 عادی'}\n\n"

    await message.answer(text)

@dp.message(F.text == "📊 آمار")
async def stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cur.fetchone())[0]
        
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE is_vip=1")
        total_vip = (await cur.fetchone())[0]
        
        cur = await db.execute("SELECT COUNT(*) FROM files")
        total_files = (await cur.fetchone())[0]

    await message.answer(
        f"📊 **آمار ربات**\n\n"
        f"👥 کاربران کل: {total_users}\n"
        f"⭐ کاربران VIP: {total_vip}\n"
        f"📂 تعداد فایل‌ها: {total_files}"
    )

# ========== آپلود فایل ادمین ==========
@dp.message(F.document)
async def upload_file(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    code = create_code()
    is_vip = 0
    is_free = 0
    
    # تشخیص نوع فایل از متن پیام
    if message.caption and "ویژه" in message.caption:
        is_vip = 1
        is_free = 0
    elif message.caption and "رایگان" in message.caption:
        is_vip = 0
        is_free = 1

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO files (code, file_id, is_free, is_vip) VALUES (?,?,?,?)",
            (code, message.document.file_id, is_free, is_vip)
        )
        await db.commit()

    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={code}"
    file_type = "ویژه" if is_vip else "رایگان"

    await message.answer(
        f"✅ فایل {file_type} با موفقیت آپلود شد!\n\n"
        f"🔗 لینک:\n{link}"
    )

@dp.message(F.text == "📤 آپلود فایل ویژه")
async def upload_vip_file(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📤 فایل ویژه را ارسال کن و در کپشن بنویس `ویژه`")

@dp.message(F.text == "📤 آپلود فایل رایگان")
async def upload_free_file(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("📤 فایل رایگان را ارسال کن و در کپشن بنویس `رایگان`")

@dp.message(F.text == "🎫 ساخت کد تخفیف")
async def create_discount(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer(
        "🎫 **ساخت کد تخفیف جدید**\n\n"
        "فرمت: `/create_discount درصد مدت_اعتبار(روز)`\n"
        "مثال: `/create_discount 20 30`\n"
        "(۳۰ روز اعتبار با ۲۰٪ تخفیف)"
    )

@dp.message(F.text.startswith("/create_discount"))
async def create_discount_code(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❌ فرمت: `/create_discount درصد روز`")
        return

    try:
        percent = int(parts[1])
        days = int(parts[2])
    except ValueError:
        await message.answer("❌ درصد و روز باید عدد باشند.")
        return

    code = f"FONT{random.randint(1000, 9999)}"
    expiry = (datetime.now() + timedelta(days=days)).isoformat()

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO discount_codes (code, discount_percent, expires_at) VALUES (?,?,?)",
            (code, percent, expiry)
        )
        await db.commit()

    await message.answer(
        f"✅ کد تخفیف ساخته شد!\n\n"
        f"🎫 کد: `{code}`\n"
        f"🎁 {percent}٪ تخفیف\n"
        f"📅 اعتبار: {days} روز"
    )

# ========== اجرای ربات ==========
async def main():
    await init_db()
    print("✅ Bot Started")

    threading.Thread(target=run_webserver, daemon=True).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

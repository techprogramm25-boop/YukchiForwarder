import re
import logging
import asyncio
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Update

# ================= CONFIGURATION =================
API_TOKEN_1 = "8726416871:AAEKluMhwL7k4eP0RkchwvF_f82VQmLgc3A" # @YukchiForwarder_Bot (E'lonchi)
API_TOKEN_2 = "8112720689:AAFR_KtcgUYH3vBlsFZcBRj4qH3SGCwI2Zo" # @YukchiForwarderorg_Bot (Nazoratchi)

ADMINS = [6977836294, 8409259397]

REQUIRED_CHANNELS = ["@YukchiForwarder", "@YukchiForwarderPeople"]
TARGET_GROUPS = [-1003968416767, -1003775919755]
SUPPORT_SITE_URL = "https://vercell-flax.vercel.app/"
ELONCHI_BOT_USERNAME = "YukchiForwarder_Bot"

logging.basicConfig(level=logging.INFO)

# Eski versiyalar bilan ham 100% ishlaydigan oddiy va xatosiz e'lon
bot1 = Bot(token=API_TOKEN_1)
dp1 = Dispatcher(storage=MemoryStorage())

bot2 = Bot(token=API_TOKEN_2)
dp2 = Dispatcher(storage=MemoryStorage())

app = FastAPI()

banned_users = {}
drivers_db = {}
curators_db = {}
active_loads = {}
load_counter = 0

class UserRoleState(StatesGroup):
    choosing_role = State()
    driver_get_name = State()
    driver_get_car = State()
    curator_get_name = State()
    curator_choice_type = State()
    load_from = State()
    load_to = State()
    load_weight = State()
    load_info = State()
    load_urgency = State()
    load_days = State()
    load_ready_text = State()

class AdminState(StatesGroup):
    waiting_for_ban_target = State()
    waiting_for_unban_target = State()
    waiting_for_broadcast = State()

class ComplaintState(StatesGroup):
    waiting_for_complaint_text = State()

LINK_REGEX = r'(https?://[^\s]+|t\.me/[^\s]+|@[a-zA-Z0-9_]+)'
SPAM_WORDS = ["kanalga", "gruppaga", "o'ting", "oting", "murojaat", "arzon", "aksiya", "reklama", "lichkaga", "manga oting", "http", "t.me"]

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚛 Haydovchilar", callback_data="admin_list_drivers"),
            InlineKeyboardButton(text="📦 Kuratorlar", callback_data="admin_list_curators")
        ],
        [InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="admin_broadcast")],
        [
            InlineKeyboardButton(text="🚫 Ban qilish", callback_data="admin_ban_user"),
            InlineKeyboardButton(text="✅ Bandan chiqarish", callback_data="admin_unban_user")
        ]
    ])

async def check_subscriptions(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot1.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in [ChatMemberStatus.CREATOR, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
                return False
        except Exception:
            return False
    return True

def get_sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 1-Kanalga qo'shilish", url="https://t.me/YukchiForwarder")],
        [InlineKeyboardButton(text="📢 2-Kanalga qo'shilish", url="https://t.me/YukchiForwarderPeople")],
        [InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_sub")]
    ])

@dp1.message(F.text == "/start")
async def start_cmd_bot1(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id in banned_users:
        await message.answer("⛔️ <b>Siz botdan va guruhlardan bloklangansiz!</b>")
        return
    if user_id in ADMINS:
        await message.answer("👨‍💻 <b>Admin Boshqaruv Paneli:</b>", reply_markup=get_admin_keyboard())
        return
    if not await check_subscriptions(user_id):
        await message.answer("⚠️ <b>Botdan to'liq foydalanish uchun quyidagi kanallarimizga obuna bo'ling:</b>", reply_markup=get_sub_keyboard())
        return
    if user_id in drivers_db:
        d = drivers_db[user_id]
        await message.answer(f"🚛 <b>Xush kelibsiz, haydovchi {d['name']}!</b>\nMashinangiz: {d['car']}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Support Sayt", url=SUPPORT_SITE_URL)]
        ]))
        return
    elif user_id in curators_db:
        c = curators_db[user_id]
        choice_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Qo'lda kiritish", callback_data="load_manual")],
            [InlineKeyboardButton(text="⚡️ Tayyor e'lon tashlash", callback_data="load_ready")]
        ])
        await message.answer(f"📦 <b>Xush kelibsiz, kurator {c['name']}!</b>\nYuk kiritish usulini tanlang:", reply_markup=choice_kb)
        await state.set_state(UserRoleState.curator_choice_type)
        return

    role_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚛 Haydovchi", callback_data="role_driver")],
        [InlineKeyboardButton(text="📦 Kurator", callback_data="role_curator")]
    ])
    await message.answer("<b>Assalomu alaykum!</b> Oq yo'l botiga xush kelibsiz. 🌟\n\nIltimos, o'z rolingizni tanlang:", reply_markup=role_keyboard)
    await state.set_state(UserRoleState.choosing_role)

@dp1.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery, state: FSMContext):
    if await check_subscriptions(call.from_user.id):
        await call.message.delete()
        role_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚛 Haydovchi", callback_data="role_driver")],
            [InlineKeyboardButton(text="📦 Kurator", callback_data="role_curator")]
        ])
        await call.message.answer("✅ Obuna tasdiqlandi! Rolingizni tanlang:", reply_markup=role_keyboard)
        await state.set_state(UserRoleState.choosing_role)
    else:
        await call.answer("❌ Hali hamma kanallarga qo'shilmadingiz!", show_alert=True)

@dp1.callback_query(F.data == "role_driver", UserRoleState.choosing_role)
async def role_driver_chosen(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("👤 Ism-sharifingizni to'liq yuboring:")
    await state.set_state(UserRoleState.driver_get_name)

@dp1.message(UserRoleState.driver_get_name, F.text)
async def driver_get_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(driver_name=message.text.strip())
    await message.answer("🚛 Mashinangizning nomini yozing (masalan: Cobalt, Damas, MAN):")
    await state.set_state(UserRoleState.driver_get_car)

@dp1.message(UserRoleState.driver_get_car, F.text)
async def driver_get_car_handler(message: types.Message, state: FSMContext):
    car = message.text.strip()
    data = await state.get_data()
    user_id = message.from_user.id
    drivers_db[user_id] = {
        "name": data.get("driver_name"),
        "car": car,
        "username": message.from_user.username,
        "phone": "Telegram orqali"
    }
    await message.answer(f"✅ Muvaffaqiyatli ro'yxatdan o'tdingiz!\nIsm: {data.get('driver_name')}\nMashina: {car}")
    await state.clear()

@dp1.callback_query(F.data == "role_curator", UserRoleState.choosing_role)
async def role_curator_chosen(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("👤 Ism-sharifingizni yuboring:")
    await state.set_state(UserRoleState.curator_get_name)

@dp1.message(UserRoleState.curator_get_name, F.text)
async def curator_get_name_handler(message: types.Message, state: FSMContext):
    name = message.text.strip()
    user_id = message.from_user.id
    curators_db[user_id] = {"name": name, "username": message.from_user.username, "phone": "Telegram"}
    choice_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Qo'lda kiritish", callback_data="load_manual")],
        [InlineKeyboardButton(text="⚡️ Tayyor e'lon tashlash", callback_data="load_ready")]
    ])
    await message.answer(f"✅ Xush kelibsiz, kurator <b>{name}</b>!\nUsulni tanlang:", reply_markup=choice_kb)
    await state.set_state(UserRoleState.curator_choice_type)

@dp1.callback_query(F.data == "load_manual", UserRoleState.curator_choice_type)
async def load_manual_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("📍 Yuk qayerdan jo'naydi?")
    await state.set_state(UserRoleState.load_from)

@dp1.message(UserRoleState.load_from, F.text)
async def load_from_handler(message: types.Message, state: FSMContext):
    await state.update_data(load_from=message.text.strip())
    await message.answer("🎯 Yuk qayerga boradi?")
    await state.set_state(UserRoleState.load_to)

@dp1.message(UserRoleState.load_to, F.text)
async def load_to_handler(message: types.Message, state: FSMContext):
    await state.update_data(load_to=message.text.strip())
    await message.answer("⚖️ Mashina turi va yuk vazni qancha?")
    await state.set_state(UserRoleState.load_weight)

@dp1.message(UserRoleState.load_weight, F.text)
async def load_weight_handler(message: types.Message, state: FSMContext):
    await state.update_data(load_weight=message.text.strip())
    await message.answer("📝 Qo'shimcha ma'lumot bering:")
    await state.set_state(UserRoleState.load_info)

@dp1.message(UserRoleState.load_info, F.text)
async def load_info_handler(message: types.Message, state: FSMContext):
    await state.update_data(load_info=message.text.strip())
    urgency_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Shoshilinch", callback_data="urgency_yes")],
        [InlineKeyboardButton(text="⏳ Shoshilinch emas", callback_data="urgency_no")]
    ])
    await message.answer("⚡️ Qanchalik tez kerak?", reply_markup=urgency_kb)
    await state.set_state(UserRoleState.load_urgency)

@dp1.callback_query(F.data.startswith("urgency_"), UserRoleState.load_urgency)
async def load_urgency_handler(call: types.CallbackQuery, state: FSMContext):
    urgency = "Shoshilinch 🔥" if call.data == "urgency_yes" else "Shoshilinch emas ⏳"
    await state.update_data(load_urgency=urgency)
    await call.message.edit_text("⏳ Necha kundan keyin o'chirilsin? (Faqat raqam, masalan: 1):")
    await state.set_state(UserRoleState.load_days)

@dp1.message(UserRoleState.load_days, F.text)
async def load_days_handler(message: types.Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("❌ Faqat raqam kiriting:")
        return
    await state.update_data(load_days=int(message.text.strip()))
    await finalize_and_send_load(message, state, await state.get_data())

@dp1.callback_query(F.data == "load_ready", UserRoleState.curator_choice_type)
async def load_ready_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("📝 Tayyor yuk matnini yuboring:")
    await state.set_state(UserRoleState.load_ready_text)

@dp1.message(UserRoleState.load_ready_text, F.text)
async def load_ready_text_handler(message: types.Message, state: FSMContext):
    await state.update_data(load_ready_text=message.text.strip(), load_days=1, load_urgency="Tayyor e'lon")
    await finalize_and_send_load(message, state, await state.get_data())

async def finalize_and_send_load(message: types.Message, state: FSMContext, data: dict):
    global load_counter
    load_counter += 1
    load_id = load_counter
    user = message.from_user
    curator_info = curators_db.get(user.id, {"name": user.full_name, "phone": "Mavjud emas"})

    if "load_ready_text" in data:
        main_content = data["load_ready_text"]
    else:
        main_content = (
            f"📍 <b>Qayerdan:</b> {data.get('load_from')}\n"
            f"🎯 <b>Qayerga:</b> {data.get('load_to')}\n"
            f"⚖️ <b>Mashina / Vazni:</b> {data.get('load_weight')}\n"
            f"📌 <b>Ma'lumot:</b> {data.get('load_info')}\n"
            f"⚡️ <b>Holati:</b> {data.get('load_urgency')}"
        )
        
    final_caption = (
        f"📦 <b>YUK E'LONI №{load_id}</b>\n\n"
        f"{main_content}\n\n"
        f"_____________________\n"
        f"👤 <b>Kurator:</b> {curator_info['name']} (@{user.username or 'yoq'})\n"
        f"📢 <b>Kanallar:</b> @YukchiForwarder"
    )
    
    expire_time = datetime.now() + timedelta(days=data.get("load_days", 1))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Nomer ko'rish", callback_data=f"show_curator_phone:{user.id}")],
        [InlineKeyboardButton(text="🚛 Qabul qilish", callback_data=f"accept_load:{load_id}")],
        [InlineKeyboardButton(text="🌐 Support", url=SUPPORT_SITE_URL)]
    ])
    
    group_msg_ids = {}
    for group_id in TARGET_GROUPS:
        try:
            sent_msg = await bot1.send_message(chat_id=group_id, text=final_caption, reply_markup=keyboard)
            group_msg_ids[group_id] = sent_msg.message_id
        except Exception:
            pass
            
    active_loads[load_id] = {"user_id": user.id, "group_msg_ids": group_msg_ids, "expire_time": expire_time}
    await message.answer("✅ Yuk guruhlarga yuborildi!")
    await state.clear()

@dp1.callback_query(F.data.startswith("show_curator_phone:"))
async def show_curator_phone(call: types.CallbackQuery):
    curator = curators_db.get(int(call.data.split(":")[1]), {"phone": "Mavjud emas"})
    await call.answer(f"📞 Kurator raqami: {curator['phone']}", show_alert=True)

@dp1.callback_query(F.data.startswith("accept_load:"))
async def accept_load_handler(call: types.CallbackQuery):
    driver = drivers_db.get(call.from_user.id)
    if not driver:
        await call.answer("❌ Siz haydovchi emassiz! /start orqali ro'yxatdan o'ting.", show_alert=True)
        return
    load = active_loads.get(int(call.data.split(":")[1]))
    if not load:
        await call.answer("❌ Bu yuk topilmadi!", show_alert=True)
        return
    try:
        await bot1.send_message(chat_id=load["user_id"], text=f"✅ <b>Haydovchi topildi!</b>\nIsm: {driver['name']}\nMashina: {driver['car']}")
    except Exception:
        pass
    await call.answer("✅ Kuratorga ma'lumotingiz yuborildi!", show_alert=True)

# ================= 2-BOT =================
def get_complaint_keyboard(is_admin: bool = False):
    buttons = [
        [InlineKeyboardButton(text="⚠️ Shikoyat qilish", callback_data="comp_shikoyat")],
        [InlineKeyboardButton(text="❓ Muammo bildirish", callback_data="comp_muammo")],
        [InlineKeyboardButton(text="🌐 Support Sayt", url=SUPPORT_SITE_URL)],
        [InlineKeyboardButton(text="📢 E'lonchi Botga o'tish", url=f"https://t.me/{ELONCHI_BOT_USERNAME}")]
    ]
    if is_admin:
        buttons.insert(0, [InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel_open")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp2.message(F.text == "/start")
async def start_cmd_bot2(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    if user_id in banned_users:
        await message.answer("⛔️ Siz bloklangansiz!")
        return
    is_admin = user_id in ADMINS
    if is_admin:
        await message.answer("👨‍💻 <b>Admin Paneli:</b>", reply_markup=get_admin_keyboard())
    await message.answer("🛡 <b>Nazoratchi va Shikoyat Boti</b>\n\nShikoyat yoki muammo bo'lsa pastdagi tugmani bosing:", reply_markup=get_complaint_keyboard(is_admin))

@dp2.callback_query(F.data == "admin_panel_open")
async def bot2_open_admin_panel(call: types.CallbackQuery):
    if call.from_user.id in ADMINS:
        await call.message.answer("👨‍💻 Boshqaruv:", reply_markup=get_admin_keyboard())

@dp2.callback_query(F.data.in_({"comp_shikoyat", "comp_muammo"}))
async def complaint_type_chosen(call: types.CallbackQuery, state: FSMContext):
    c_type = "Shikoyat" if call.data == "comp_shikoyat" else "Muammo"
    await state.update_data(complaint_type=c_type)
    await call.message.answer(f"📝 Iltimos, {c_type.lower()}ingiz matni yoki rasmini yuboring:")
    await state.set_state(ComplaintState.waiting_for_complaint_text)

@dp2.message(ComplaintState.waiting_for_complaint_text)
async def process_complaint_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    c_type = data.get("complaint_type", "Murojaat")
    user = message.from_user
    user_info = f"👤 <b>Kimdan:</b> {user.full_name} (@{user.username or 'yoq'}, ID: <code>{user.id}</code>)\n📌 <b>Turi:</b> {c_type}"
    for admin_id in ADMINS:
        try:
            if message.photo:
                await bot2.send_photo(chat_id=admin_id, photo=message.photo[-1].file_id, caption=f"{user_info}\n\n💬 {message.caption or ''}")
            else:
                await bot2.send_message(chat_id=admin_id, text=f"{user_info}\n\n💬 {message.text}")
        except Exception:
            pass
    await message.answer(f"✅ {c_type} adminga yuborildi!")
    await state.clear()

@dp2.message(lambda message: message.chat.id in TARGET_GROUPS)
async def security_group_guard(message: types.Message):
    if message.from_user.id in ADMINS: return
    text = (message.text or message.caption or "").lower()
    if any(w in text for w in SPAM_WORDS) or bool(re.search(LINK_REGEX, text)):
        try:
            await message.delete()
            for group_id in TARGET_GROUPS:
                await bot2.ban_chat_member(chat_id=group_id, user_id=message.from_user.id)
            banned_users[message.from_user.id] = message.from_user.full_name
        except Exception:
            pass

async def handle_broadcast_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS: return
    await call.message.answer("📢 Reklama matnini yuboring:")
    await state.set_state(AdminState.waiting_for_broadcast)

async def handle_broadcast_process(message: types.Message, state: FSMContext, bot_inst: Bot):
    if message.from_user.id not in ADMINS: return
    for g in TARGET_GROUPS:
        try: await message.copy_to(chat_id=g)
        except: pass
    await message.answer("✅ Reklama tarqatildi!")
    await state.clear()

async def handle_ban_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS: return
    await call.message.answer("🚫 Ban qilinuvchi ID yoki Username ni kiriting:")
    await state.set_state(AdminState.waiting_for_ban_target)

async def handle_ban_process(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    target = message.text.strip()
    key = int(target) if target.isdigit() else target
    banned_users[key] = target
    if isinstance(key, int):
        for g in TARGET_GROUPS:
            try: await bot1.ban_chat_member(chat_id=g, user_id=key)
            except: pass
    await message.answer(f"✅ {target} ban qilindi!")
    await state.clear()

async def handle_unban_start(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS: return
    await call.message.answer("✅ Bandan chiqarish uchun ID yuboring:")
    await state.set_state(AdminState.waiting_for_unban_target)

async def handle_unban_process(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS: return
    target = message.text.strip()
    key = int(target) if target.isdigit() else target
    if key in banned_users: del banned_users[key]
    await message.answer(f"✅ {target} bandan chiqarildi!")
    await state.clear()

for dp_inst, b_inst in [(dp1, bot1), (dp2, bot2)]:
    @dp_inst.callback_query(F.data == "admin_broadcast")
    async def bc_s(c: types.CallbackQuery, s: FSMContext): await handle_broadcast_start(c, s)
    @dp_inst.message(AdminState.waiting_for_broadcast, F.text)
    async def bc_p(m: types.Message, s: FSMContext): await handle_broadcast_process(m, s, b_inst)
    @dp_inst.callback_query(F.data == "admin_ban_user")
    async def bn_s(c: types.CallbackQuery, s: FSMContext): await handle_ban_start(c, s)
    @dp_inst.message(AdminState.waiting_for_ban_target, F.text)
    async def bn_p(m: types.Message, s: FSMContext): await handle_ban_process(m, s)
    @dp_inst.callback_query(F.data == "admin_unban_user")
    async def ubn_s(c: types.CallbackQuery, s: FSMContext): await handle_unban_start(c, s)
    @dp_inst.message(AdminState.waiting_for_unban_target, F.text)
    async def ubn_p(m: types.Message, s: FSMContext): await handle_unban_process(m, s)

@dp1.callback_query(F.data == "admin_list_drivers")
async def lst_drv(c: types.CallbackQuery):
    if c.from_user.id not in ADMINS: return
    txt = "\n".join([f"{d['name']} | {d['car']}" for d in drivers_db.values()]) or "Yo'q"
    await c.message.answer(f"🚛 Haydovchilar:\n{txt}")

@dp1.callback_query(F.data == "admin_list_curators")
async def lst_cur(c: types.CallbackQuery):
    if c.from_user.id not in ADMINS: return
    txt = "\n".join([f"{c['name']}" for c in curators_db.values()]) or "Yo'q"
    await c.message.answer(f"📦 Kuratorlar:\n{txt}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(background_load_cleaner())

async def background_load_cleaner():
    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        expired = [lid for lid, d in active_loads.items() if now >= d["expire_time"]]
        for lid in expired:
            data = active_loads.pop(lid, None)
            if data:
                for gid, mid in data["group_msg_ids"].items():
                    try: await bot1.delete_message(chat_id=gid, message_id=mid)
                    except: pass

@app.post(f"/webhook/bot1/{API_TOKEN_1}")
async def webhook_bot1(request: Request):
    try:
        update = Update.model_validate(await request.json(), context={"bot": bot1})
        await dp1.feed_update(bot1, update)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post(f"/webhook/bot2/{API_TOKEN_2}")
async def webhook_bot2(request: Request):
    try:
        update = Update.model_validate(await request.json(), context={"bot": bot2})
        await dp2.feed_update(bot2, update)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
async def root():
    return {"status": "Tizim tezkor ishlamoqda!"}

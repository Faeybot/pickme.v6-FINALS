import asyncio
import logging
import os
import html
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto
)
from services.database import DatabaseService

router = Router()
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")

# ==========================================
# 1. DATA MASTER & FSM STATE
# ==========================================
CITY_DATA = {
    "prof_city_medan": {"name": "Medan", "lat": 3.5952, "lng": 98.6722, "tag": "MEDAN"},
    "prof_city_plm": {"name": "Palembang", "lat": -2.9761, "lng": 104.7754, "tag": "PALEMBANG"},
    "prof_city_lamp": {"name": "Lampung", "lat": -5.3971, "lng": 105.2668, "tag": "LAMPUNG"},
    "prof_city_btm": {"name": "Batam", "lat": 1.1301, "lng": 104.0529, "tag": "BATAM"},
    "prof_city_jkt": {"name": "Jakarta", "lat": -6.2088, "lng": 106.8456, "tag": "JAKARTA"},
    "prof_city_bks": {"name": "Bekasi", "lat": -6.2383, "lng": 106.9756, "tag": "BEKASI"},
    "prof_city_bgr": {"name": "Bogor", "lat": -6.5971, "lng": 106.8060, "tag": "BOGOR"},
    "prof_city_bdg": {"name": "Bandung", "lat": -6.9175, "lng": 107.6191, "tag": "BANDUNG"},
    "prof_city_jgj": {"name": "Jogja", "lat": -7.7956, "lng": 110.3695, "tag": "JOGJA"},
    "prof_city_smr": {"name": "Semarang", "lat": -6.9667, "lng": 110.4167, "tag": "SEMARANG"},
    "prof_city_slo": {"name": "Solo", "lat": -7.5707, "lng": 110.8214, "tag": "SOLO"},
    "prof_city_sby": {"name": "Surabaya", "lat": -7.2575, "lng": 112.7521, "tag": "SURABAYA"},
    "prof_city_mlg": {"name": "Malang", "lat": -7.9666, "lng": 112.6326, "tag": "MALANG"},
    "prof_city_dps": {"name": "Bali", "lat": -8.6705, "lng": 115.2126, "tag": "BALI"},
    "prof_city_lmbk": {"name": "Lombok", "lat": -8.5833, "lng": 116.1167, "tag": "LOMBOK"},
}

INTEREST_MAP = {
    "int_adult": "🔞 Adult Content", "int_flirt": "🔥 Flirt & Dirty Talk", "int_rel": "❤️ Relationship",
    "int_net": "🤝 Networking", "int_game": "🎮 Gaming", "int_travel": "✈️ Traveling", "int_coffee": "☕ Coffee & Chill"
}

class EditProfile(StatesGroup):
    waiting_for_bio = State()
    waiting_for_location = State()
    waiting_for_photo_main = State()
    waiting_for_photo_extra = State()
    waiting_for_interests = State()


# ==========================================
# 2. CORE RENDERER: MENU "AKUN SAYA" UTAMA
# ==========================================
async def render_my_account_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None):
    await state.clear()
    user = await db.get_user(user_id)
    if not user: return False

    await db.push_nav(user_id, "account")

    # --- FORMATTING TEXT ---
    minat = ", ".join([INTEREST_MAP.get(i.strip(), i.strip()) for i in (user.interests or "").split(",") if i.strip()]) or "-"
    bio = html.escape(user.bio) if user.bio else "Belum ada bio. Ayo tulis sesuatu!"
    kota = html.escape(user.location_name) if user.location_name else "Belum diatur"
    gender = "👨 Pria" if user.gender == "male" else "👩 Wanita" if user.gender == "female" else "Rahasia"

    kasta = "💎 VIP+" if user.is_vip_plus else "🌟 VIP" if user.is_vip else "👤 FREE"
    status_premium = "✅ Verified (Bisa Tarik Tunai)" if user.is_premium else "❌ Unverified (Tidak bisa WD)"
    total_boost = user.paid_boost_balance + user.weekly_free_boost

    rp_value = (user.points // 10)  # Konversi Poin ke Rupiah

    text_content = (
        f"👤 <b>INFORMASI PROFIL</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<b>Nama:</b> {html.escape(user.full_name)} ({user.age}th) | {gender}\n"
        f"<b>Kota:</b> {kota}\n"
        f"<b>Minat:</b> {minat}\n"
        f"<b>Bio:</b>\n<i>\"{bio}\"</i>\n\n"
        
        f"📊 <b>STATUS & DOMPET</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<b>Kasta:</b> {kasta}\n"
        f"<b>Akun Premium:</b> {status_premium}\n"
        f"<b>Saldo Poin:</b> {user.points} Poin (Rp {rp_value:,})\n"
        f"<b>Tiket Boost:</b> {total_boost} Tiket\n\n"
        
        f"📑 <b>Sisa Kuota Harian:</b>\n"
        f"Swipe: <b>{user.daily_swipe_quota}</b> | Buka Profil: <b>{user.daily_open_profile_quota}</b>\n"
        f"Unmask: <b>{user.daily_unmask_quota}</b> | Kirim DM: <b>{user.daily_message_quota}</b>\n"
        f"Feed: <b>{user.daily_feed_text_quota} Teks, {user.daily_feed_photo_quota} Foto</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>"
    )

    kb_buttons = [
        [InlineKeyboardButton(text="✏️ PENGATURAN PROFIL", callback_data="acc_edit_menu")],
        [InlineKeyboardButton(text="📸 KELOLA GALERI FOTO", callback_data="manage_photos")],
        [InlineKeyboardButton(text="💎 UPGRADE KASTA / BELI TIKET", callback_data="menu_pricing")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Dashboard", callback_data="back_to_dashboard")]
    ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    media_id = user.photo_id if user.photo_id else BANNER_PHOTO_ID
    media = InputMediaPhoto(media=media_id, caption=text_content, parse_mode="HTML")

    anchor_id = user.anchor_msg_id
    success_edit = False

    if anchor_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=anchor_id, media=media, reply_markup=kb)
            success_edit = True
        except Exception: pass

    if not success_edit:
        try:
            if anchor_id:
                try: await bot.delete_message(chat_id=chat_id, message_id=anchor_id)
                except: pass
            sent = await bot.send_photo(chat_id=chat_id, photo=media_id, caption=text_content, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
        except Exception: pass

    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
    return True

@router.callback_query(F.data == "menu_account")
async def show_my_account(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    await render_my_account_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


# ==========================================
# 3. SUB-MENU: PUSAT PENGATURAN PROFIL (HUB)
# ==========================================
async def render_edit_hub(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    user = await db.get_user(user_id)
    text = "✏️ <b>PUSAT PENGATURAN PROFIL</b>\n\nBagian mana yang ingin Anda ubah hari ini?"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Edit Bio", callback_data="update_bio"),
         InlineKeyboardButton(text="📍 Update Lokasi", callback_data="update_loc")],
        [InlineKeyboardButton(text="🔥 Ubah Minat", callback_data="update_interests")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Akun Saya", callback_data="menu_account")]
    ])
    
    media = InputMediaPhoto(media=user.photo_id or BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    try: await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
    except: pass
    
    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass

@router.callback_query(F.data == "acc_edit_menu")
async def handle_edit_hub(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_edit_hub(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)


# ==========================================
# 4. HANDLERS: LOKASI
# ==========================================
@router.callback_query(F.data == "update_loc")
async def ask_location_profile(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService):
    kb_list, temp_row = [], []
    for code, info in CITY_DATA.items():
        temp_row.append(InlineKeyboardButton(text=info["name"], callback_data=code))
        if len(temp_row) == 3: kb_list.append(temp_row); temp_row = []
    if temp_row: kb_list.append(temp_row)
    
    kb_list.append([InlineKeyboardButton(text="❌ Batal", callback_data="acc_edit_menu")])
    text = "📍 <b>UPDATE LOKASI PROFIL</b>\n\nPilih kota domisili Anda dari daftar, atau kirimkan koordinat GPS Anda agar lebih presisi."

    try: await callback.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list), parse_mode="HTML")
    except: pass

    # Tombol GPS di Keyboard Bawah
    gps_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 KIRIM KOORDINAT GPS", request_location=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    msg_gps = await callback.message.answer("<i>Atau tekan tombol GPS di bawah:</i>", reply_markup=gps_kb, parse_mode="HTML")
    
    await state.update_data(gps_msg_id=msg_gps.message_id)
    await state.set_state(EditProfile.waiting_for_location)
    await callback.answer()

@router.callback_query(F.data.startswith("prof_city_"), EditProfile.waiting_for_location)
async def handle_manual_city(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    city_info = CITY_DATA.get(callback.data)
    if city_info:
        async with db.session_factory() as session:
            from services.database import User as UserTable
            user = await session.get(UserTable, callback.from_user.id)
            user.latitude, user.longitude = city_info["lat"], city_info["lng"]
            user.location_name = city_info["name"]
            user.city_hashtag = f"#{city_info['tag']}"
            await session.commit()
        
        data = await state.get_data()
        try: 
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=data.get('gps_msg_id'))
            # Hapus Keyboard Reply GPS
            temp = await callback.message.answer("🔄", reply_markup=ReplyKeyboardRemove())
            await temp.delete()
        except: pass
        
        await state.clear() 
        await callback.answer(f"✅ Lokasi diperbarui ke {city_info['name']}!", show_alert=True)
        await render_my_account_ui(bot, callback.message.chat.id, callback.from_user.id, db, state)

@router.message(F.location, EditProfile.waiting_for_location)
async def handle_gps_profile(message: types.Message, db: DatabaseService, state: FSMContext, bot: Bot):
    lat, lon = message.location.latitude, message.location.longitude
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, message.from_user.id)
        user.latitude, user.longitude = lat, lon
        user.location_name = "Lokasi GPS"
        await session.commit()
            
    try: await message.delete()
    except: pass
    
    data = await state.get_data()
    try: 
        await bot.delete_message(chat_id=message.chat.id, message_id=data.get('gps_msg_id'))
        temp = await message.answer("🔄", reply_markup=ReplyKeyboardRemove())
        await temp.delete()
    except: pass
    
    await state.clear()
    msg_sukses = await message.answer("✅ Lokasi GPS tersimpan!")
    await asyncio.sleep(1)
    try: await msg_sukses.delete()
    except: pass
    
    await render_my_account_ui(bot, message.chat.id, message.from_user.id, db, state)


# ==========================================
# 5. HANDLERS: MINAT & BIO
# ==========================================
@router.callback_query(F.data == "update_interests")
async def ask_interests(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    selected = [i.strip() for i in (user.interests or "").split(",") if i.strip()]
    await state.update_data(selected_interests=selected)
    
    kb = []
    for code, name in INTEREST_MAP.items():
        prefix = "✅ " if code in selected else ""
        kb.append([InlineKeyboardButton(text=f"{prefix}{name}", callback_data=f"prof_int_{code}")])
    
    kb.append([InlineKeyboardButton(text="💾 SIMPAN", callback_data="prof_save_int")])
    kb.append([InlineKeyboardButton(text="❌ Batal", callback_data="acc_edit_menu")])
    
    try: await callback.message.edit_caption(caption="🔥 <b>UBAH MINAT</b>\nPilih maksimal 3 minat yang paling sesuai denganmu:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    except: pass
    await state.set_state(EditProfile.waiting_for_interests)

@router.callback_query(F.data.startswith("prof_int_"), EditProfile.waiting_for_interests)
async def toggle_interest(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_interests", [])
    code = callback.data.replace("prof_int_", "")
    
    if code in selected: selected.remove(code)
    elif len(selected) < 3: selected.append(code)
    else: return await callback.answer("Maksimal 3 minat!", show_alert=True)
    
    await state.update_data(selected_interests=selected)
    kb = []
    for c, n in INTEREST_MAP.items():
        p = "✅ " if c in selected else ""
        kb.append([InlineKeyboardButton(text=f"{p}{n}", callback_data=f"prof_int_{c}")])
    kb.append([InlineKeyboardButton(text="💾 SIMPAN", callback_data="prof_save_int")])
    kb.append([InlineKeyboardButton(text="❌ Batal", callback_data="acc_edit_menu")])
    
    try: await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except: pass

@router.callback_query(F.data == "prof_save_int", EditProfile.waiting_for_interests)
async def save_interests(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService, bot: Bot):
    data = await state.get_data()
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, callback.from_user.id)
        user.interests = ",".join(data.get("selected_interests", []))
        await session.commit()
    
    await state.clear()
    await callback.answer("✅ Minat disimpan!", show_alert=True)
    await render_my_account_ui(bot, callback.message.chat.id, callback.from_user.id, db, state)

@router.callback_query(F.data == "update_bio")
async def ask_bio(callback: types.CallbackQuery, state: FSMContext):
    text = "📝 <b>UPDATE BIO</b>\n\nMasukkan Bio baru Anda (Maks 150 Karakter).\n<i>Ketik dan kirim pesan teks ke bot.</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Batal", callback_data="acc_edit_menu")]])
    
    try: await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except: pass
    await state.set_state(EditProfile.waiting_for_bio)

@router.message(EditProfile.waiting_for_bio)
async def save_bio(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    if len(message.text) > 150: return await message.answer("⚠️ Terlalu panjang! Maks 150 Karakter.")
    
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, message.from_user.id)
        user.bio = message.text
        await session.commit()
            
    try: await message.delete() 
    except: pass
    await state.clear()
    await render_my_account_ui(bot, message.chat.id, message.from_user.id, db, state)


# ==========================================
# 6. MANAJEMEN FOTO (GALERI)
# ==========================================
async def render_manage_photos_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService):
    user = await db.get_user(user_id)
    extra = user.extra_photos or []
    
    kb = [[InlineKeyboardButton(text="🖼️ GANTI FOTO UTAMA", callback_data="change_photo_main")]]
    if len(extra) < 2: kb.append([InlineKeyboardButton(text="➕ TAMBAH FOTO EXTRA", callback_data="add_photo_extra")])
    if extra: kb.append([InlineKeyboardButton(text="🗑️ HAPUS SEMUA FOTO EXTRA", callback_data="clear_photo_extra")])
    kb.append([InlineKeyboardButton(text="⬅️ Kembali ke Akun Saya", callback_data="menu_account")])
    
    caption_text = "📸 <b>MANAJEMEN GALERI FOTO</b>\n\nSesuaikan foto-foto terbaikmu agar lebih memikat di Discovery."
    media = InputMediaPhoto(media=user.photo_id or BANNER_PHOTO_ID, caption=caption_text, parse_mode="HTML")

    try: await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except Exception: pass
    return True

@router.callback_query(F.data == "manage_photos")
async def manage_photos_handler(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_manage_photos_ui(bot, callback.message.chat.id, callback.from_user.id, db)
    await callback.answer()

@router.callback_query(F.data == "change_photo_main")
async def start_change_main(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Batal", callback_data="manage_photos")]])
    try: await callback.message.edit_caption(caption="📸 Kirimkan <b>1 Foto Utama</b> yang baru (Kirim gambar ke bot):", reply_markup=kb, parse_mode="HTML")
    except: pass
    await state.set_state(EditProfile.waiting_for_photo_main)
    await callback.answer()

@router.message(EditProfile.waiting_for_photo_main, F.photo)
async def save_new_main(message: types.Message, db: DatabaseService, state: FSMContext, bot: Bot):
    await db.update_main_photo(message.from_user.id, message.photo[-1].file_id)
    await state.clear()
    try: await message.delete()
    except: pass
    await render_manage_photos_ui(bot, message.chat.id, message.from_user.id, db)

@router.callback_query(F.data == "add_photo_extra")
async def start_add_extra(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Batal", callback_data="manage_photos")]])
    try: await callback.message.edit_caption(caption="📸 Kirimkan <b>Foto Tambahan</b> Anda (Maksimal 2):", reply_markup=kb, parse_mode="HTML")
    except: pass
    await state.set_state(EditProfile.waiting_for_photo_extra)
    await callback.answer()

@router.message(EditProfile.waiting_for_photo_extra, F.photo)
async def save_new_extra(message: types.Message, db: DatabaseService, state: FSMContext, bot: Bot):
    await db.manage_extra_photo(message.from_user.id, message.photo[-1].file_id, action='add')
    await state.clear()
    try: await message.delete()
    except: pass
    await render_manage_photos_ui(bot, message.chat.id, message.from_user.id, db)

@router.callback_query(F.data == "clear_photo_extra")
async def clear_photos(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, callback.from_user.id)
        user.extra_photos = []
        await session.commit()
    await callback.answer("🗑️ Foto Extra dihapus!", show_alert=True)
    await render_manage_photos_ui(bot, callback.message.chat.id, callback.from_user.id, db)

# ==========================================
# 7. DUMMY MENU PRICING
# ==========================================
@router.callback_query(F.data == "menu_pricing")
async def menu_pricing_dummy(callback: types.CallbackQuery):
    await callback.answer("💎 Menu Etalase Upgrade VIP / Pembelian Tiket sedang disiapkan oleh Developer...", show_alert=True)

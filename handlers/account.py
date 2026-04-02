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
# 1. DATA MASTER
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
    "int_adult": "🔞 Adult Content",
    "int_flirt": "🔥 Flirt & Dirty Talk",
    "int_rel": "❤️ Relationship",
    "int_net": "🤝 Networking",
    "int_game": "🎮 Gaming",
    "int_travel": "✈️ Traveling",
    "int_coffee": "☕ Coffee & Chill"
}


class EditProfile(StatesGroup):
    waiting_for_bio = State()
    waiting_for_location = State()
    waiting_for_photo_main = State()
    waiting_for_photo_extra = State()
    waiting_for_interests = State()


# ==========================================
# 2. RENDERER UTAMA: AKUN HUB (GERBANG)
# ==========================================
async def render_account_hub(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None):
    """Menu utama Akun - Hanya gerbang ke sub-menu"""
    
    # Cleanup ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    if state:
        await state.clear()
    
    user = await db.get_user(user_id)
    if not user:
        return False
    
    await db.push_nav(user_id, "account_hub")
    
    # Tentukan kasta
    if user.is_vip_plus:
        kasta = "💎 VIP+"
    elif user.is_vip:
        kasta = "🌟 VIP"
    elif user.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"
    
    text = (
        f"⚙️ <b>PUSAT AKUN & STATUS</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"👤 <b>{user.full_name.upper()}</b> | {kasta}\n"
        f"💰 Saldo: <b>{user.poin_balance:,} Poin</b>\n"
        f"📍 Lokasi: <b>{user.location_name}</b>\n\n"
        f"Kelola bagaimana profilmu tampil di <i>Discovery</i> dan pantau sisa kuota harianmu."
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 LIHAT & EDIT PROFIL", callback_data="acc_view_profile")],
        [InlineKeyboardButton(text="📊 CEK STATUS & KUOTA", callback_data="acc_view_status")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Dashboard", callback_data="back_to_dashboard")]
    ])
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    if callback_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
            await bot.answer_callback_query(callback_id)
        except Exception as e:
            logging.error(f"Edit media gagal: {e}")
    else:
        try:
            sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
        except Exception as e:
            logging.error(f"Kirim ulang gagal: {e}")
    
    return True


# ==========================================
# 3. HANDLER: LIHAT & EDIT PROFIL (PROFIL LENGKAP)
# ==========================================
@router.callback_query(F.data == "acc_view_profile")
async def handle_view_profile(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    """Menampilkan profil lengkap user"""
    await render_full_profile_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


async def render_full_profile_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None):
    """Tampilan profil lengkap user"""
    
    if state:
        await state.clear()
    
    user = await db.get_user(user_id)
    if not user:
        return False
    
    await db.push_nav(user_id, "profile")
    
    # Format minat
    interest_codes = [i.strip() for i in (user.interests or "").split(",") if i.strip()]
    minat_list = [INTEREST_MAP.get(code, code) for code in interest_codes]
    minat = ", ".join(minat_list) if minat_list else "-"
    
    bio = html.escape(user.bio) if user.bio else "Belum ada bio"
    kota = html.escape(user.location_name) if user.location_name else "Belum diatur"
    gender = "👨 Pria" if user.gender == "Pria" else "👩 Wanita" if user.gender == "Wanita" else "Rahasia"
    
    # Tentukan kasta
    if user.is_vip_plus:
        kasta = "💎 VIP+"
    elif user.is_vip:
        kasta = "🌟 VIP"
    elif user.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"
    
    extra_photos = user.extra_photos or []
    total_photos = 1 + len(extra_photos)
    
    text = (
        f"👤 <b>PROFIL SAYA</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"<b>Nama:</b> {html.escape(user.full_name)} ({user.age}th) | {gender}\n"
        f"<b>Kota:</b> {kota}\n"
        f"<b>Status:</b> {kasta}\n"
        f"<b>Minat:</b> {minat}\n"
        f"<b>Bio:</b>\n<i>\"{bio}\"</i>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"📸 Koleksi Foto: <b>{total_photos} / 3 Foto</b>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ EDIT PROFIL", callback_data="acc_edit_menu")],
        [InlineKeyboardButton(text="📸 KELOLA GALERI FOTO", callback_data="manage_photos")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Akun Saya", callback_data="menu_account")]
    ])
    
    media = InputMediaPhoto(media=user.photo_id, caption=text, parse_mode="HTML")
    
    if callback_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
            await bot.answer_callback_query(callback_id)
        except:
            pass
    else:
        try:
            sent = await bot.send_photo(chat_id=chat_id, photo=user.photo_id, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
        except Exception as e:
            logging.error(f"Gagal render profile UI: {e}")
    
    return True


# ==========================================
# 4. HANDLER: CEK STATUS & KUOTA (ALIHKAN KE STATUS.PY)
# ==========================================
@router.callback_query(F.data == "acc_view_status")
async def handle_view_status(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """Menampilkan status kuota user - DIALIHKAN KE status.py"""
    from handlers.status import render_status_ui
    await render_status_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)


# ==========================================
# 5. HANDLER: EDIT PROFIL (MENU)
# ==========================================
@router.callback_query(F.data == "acc_edit_menu")
async def handle_edit_menu(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """Menu edit profil"""
    await render_edit_hub(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)


async def render_edit_hub(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    """Tampilan menu edit profil"""
    user = await db.get_user(user_id)
    if not user:
        return False
    
    await db.push_nav(user_id, "edit_profile")
    
    text = "✏️ <b>EDIT PROFIL</b>\n\nApa yang ingin diubah?"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Edit Bio", callback_data="update_bio"),
         InlineKeyboardButton(text="📍 Edit Lokasi", callback_data="update_loc")],
        [InlineKeyboardButton(text="🔥 Edit Minat", callback_data="update_interests")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Profil", callback_data="menu_profile")]
    ])
    
    media = InputMediaPhoto(media=user.photo_id or BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    if callback_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
            await bot.answer_callback_query(callback_id)
        except:
            pass
    else:
        try:
            sent = await bot.send_photo(chat_id=chat_id, photo=user.photo_id or BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
        except:
            pass
    
    return True


# ==========================================
# 6. HANDLER: KEMBALI KE PROFIL (DARI EDIT)
# ==========================================
@router.callback_query(F.data == "menu_profile")
async def back_to_profile(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    """Kembali ke halaman profil dari dalam edit profil"""
    await render_full_profile_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


# ==========================================
# 7. HANDLER: UPDATE BIO
# ==========================================
@router.callback_query(F.data == "update_bio")
async def ask_bio(callback: types.CallbackQuery, state: FSMContext):
    """Meminta input bio baru"""
    text = "📝 <b>UPDATE BIO</b>\n\nMasukkan Bio baru Anda (Maks 150 Karakter).\n<i>Ketik dan kirim pesan teks ke bot.</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Batal", callback_data="acc_edit_menu")]])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        pass
    await state.set_state(EditProfile.waiting_for_bio)
    await callback.answer()


@router.message(EditProfile.waiting_for_bio)
async def save_bio(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    """Simpan bio baru"""
    if len(message.text) > 150:
        await message.answer("⚠️ Terlalu panjang! Maks 150 Karakter.")
        return
    
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, message.from_user.id)
        user.bio = message.text
        await session.commit()
    
    try:
        await message.delete()
    except:
        pass
    
    await state.clear()
    await message.answer("✅ Bio berhasil diperbarui!", parse_mode="HTML")
    await render_full_profile_ui(bot, message.chat.id, message.from_user.id, db, None)


# ==========================================
# 8. HANDLER: UPDATE LOKASI
# ==========================================
@router.callback_query(F.data == "update_loc")
async def ask_location_profile(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService, bot: Bot):
    """Meminta input lokasi baru"""
    user = await db.get_user(callback.from_user.id)
    
    # Buat keyboard inline untuk pilihan kota
    kb_list, temp_row = [], []
    for code, info in CITY_DATA.items():
        temp_row.append(InlineKeyboardButton(text=info["name"], callback_data=code))
        if len(temp_row) == 3:
            kb_list.append(temp_row)
            temp_row = []
    if temp_row:
        kb_list.append(temp_row)
    
    kb_list.append([InlineKeyboardButton(text="❌ Batal", callback_data="acc_edit_menu")])
    text = "📍 <b>UPDATE LOKASI PROFIL</b>\n\nPilih kota domisili Anda dari daftar, atau kirimkan koordinat GPS Anda agar lebih presisi."

    try:
        await callback.message.edit_caption(caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list), parse_mode="HTML")
    except:
        pass

    # Tombol GPS di Keyboard Bawah (temporary)
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
    """Handle pemilihan kota manual"""
    city_info = CITY_DATA.get(callback.data)
    if city_info:
        async with db.session_factory() as session:
            from services.database import User as UserTable
            user = await session.get(UserTable, callback.from_user.id)
            user.latitude, user.longitude = city_info["lat"], city_info["lng"]
            user.location_name = city_info["name"]
            user.city_hashtag = f"#{city_info['tag']}"
            await session.commit()
        
        # Cleanup GPS message
        data = await state.get_data()
        try:
            await bot.delete_message(chat_id=callback.message.chat.id, message_id=data.get('gps_msg_id'))
            temp = await callback.message.answer("🔄", reply_markup=ReplyKeyboardRemove())
            await temp.delete()
        except:
            pass
        
        await state.clear()
        await callback.answer(f"✅ Lokasi diperbarui ke {city_info['name']}!", show_alert=True)
        await render_full_profile_ui(bot, callback.message.chat.id, callback.from_user.id, db, None)


@router.message(F.location, EditProfile.waiting_for_location)
async def handle_gps_profile(message: types.Message, db: DatabaseService, state: FSMContext, bot: Bot):
    """Handle input GPS otomatis"""
    lat, lon = message.location.latitude, message.location.longitude
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, message.from_user.id)
        user.latitude, user.longitude = lat, lon
        user.location_name = "Lokasi GPS"
        await session.commit()
    
    try:
        await message.delete()
    except:
        pass
    
    # Cleanup
    data = await state.get_data()
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=data.get('gps_msg_id'))
        temp = await message.answer("🔄", reply_markup=ReplyKeyboardRemove())
        await temp.delete()
    except:
        pass
    
    await state.clear()
    await message.answer("✅ Lokasi GPS tersimpan!", parse_mode="HTML")
    await render_full_profile_ui(bot, message.chat.id, message.from_user.id, db, None)


# ==========================================
# 9. HANDLER: UPDATE MINAT
# ==========================================
@router.callback_query(F.data == "update_interests")
async def ask_interests(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext):
    """Memilih minat (maksimal 3)"""
    user = await db.get_user(callback.from_user.id)
    selected = [i.strip() for i in (user.interests or "").split(",") if i.strip()]
    await state.update_data(selected_interests=selected)
    
    kb = []
    for code, name in INTEREST_MAP.items():
        prefix = "✅ " if code in selected else ""
        kb.append([InlineKeyboardButton(text=f"{prefix}{name}", callback_data=f"prof_int_{code}")])
    
    kb.append([InlineKeyboardButton(text="💾 SIMPAN", callback_data="prof_save_int")])
    kb.append([InlineKeyboardButton(text="❌ Batal", callback_data="acc_edit_menu")])
    
    try:
        await callback.message.edit_caption(
            caption="🔥 <b>UBAH MINAT</b>\nPilih maksimal 3 minat yang paling sesuai denganmu:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
            parse_mode="HTML"
        )
    except:
        pass
    await state.set_state(EditProfile.waiting_for_interests)
    await callback.answer()


@router.callback_query(F.data.startswith("prof_int_"), EditProfile.waiting_for_interests)
async def toggle_interest(callback: types.CallbackQuery, state: FSMContext):
    """Toggle pilihan minat"""
    data = await state.get_data()
    selected = data.get("selected_interests", [])
    code = callback.data.replace("prof_int_", "")
    
    if code in selected:
        selected.remove(code)
    elif len(selected) < 3:
        selected.append(code)
    else:
        return await callback.answer("Maksimal 3 minat!", show_alert=True)
    
    await state.update_data(selected_interests=selected)
    
    # Refresh keyboard
    kb = []
    for c, n in INTEREST_MAP.items():
        p = "✅ " if c in selected else ""
        kb.append([InlineKeyboardButton(text=f"{p}{n}", callback_data=f"prof_int_{c}")])
    kb.append([InlineKeyboardButton(text="💾 SIMPAN", callback_data="prof_save_int")])
    kb.append([InlineKeyboardButton(text="❌ Batal", callback_data="acc_edit_menu")])
    
    try:
        await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except:
        pass


@router.callback_query(F.data == "prof_save_int", EditProfile.waiting_for_interests)
async def save_interests(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService, bot: Bot):
    """Simpan minat yang dipilih"""
    data = await state.get_data()
    async with db.session_factory() as session:
        from services.database import User as UserTable
        user = await session.get(UserTable, callback.from_user.id)
        user.interests = ",".join(data.get("selected_interests", []))
        await session.commit()
    
    await state.clear()
    await callback.answer("✅ Minat disimpan!", show_alert=True)
    await render_full_profile_ui(bot, callback.message.chat.id, callback.from_user.id, db, None)

# ==========================================
# 10. GALERI FOTO & MANAJEMEN (VERSI FINAL DENGAN LOGGING)
# ==========================================

# Dictionary untuk menyimpan user yang sedang upload
waiting_for_upload = {}

async def render_gallery_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, message_id: int = None):
    """Menampilkan galeri foto dengan 3 slot: Profil, Album1, Album2"""
    user = await db.get_user(user_id)
    if not user:
        return
    
    extra = user.extra_photos or []
    
    # Tentukan status setiap slot
    photo_main_status = "✅ Ada" if user.photo_id else "❌ Kosong"
    photo_extra_1_status = "✅ Ada" if len(extra) >= 1 else "❌ Kosong"
    photo_extra_2_status = "✅ Ada" if len(extra) >= 2 else "❌ Kosong"
    
    text = (
        "📸 <b>GALERI FOTO PICKME</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
        f"🖼️ <b>Foto Profil:</b> {photo_main_status}\n"
        f"📷 <b>Foto Album 1:</b> {photo_extra_1_status}\n"
        f"📷 <b>Foto Album 2:</b> {photo_extra_2_status}\n\n"
        f"<i>Foto profil adalah foto utama yang terlihat di Discovery.\n"
        f"Foto album akan ditampilkan saat user VIP/VIP+ melihat profilmu.</i>"
    )
    
    # Buat tombol berdasarkan status
    kb = []
    
    # Tombol ganti foto profil (selalu ada)
    kb.append([InlineKeyboardButton(text="🖼️ GANTI FOTO PROFIL", callback_data="gallery_change_main")])
    
    # Tombol untuk Album 1
    if len(extra) >= 1:
        kb.append([InlineKeyboardButton(text="🔄 GANTI FOTO ALBUM 1", callback_data="gallery_change_extra_1")])
    else:
        kb.append([InlineKeyboardButton(text="➕ UPLOAD FOTO ALBUM 1", callback_data="gallery_upload_extra_1")])
    
    # Tombol untuk Album 2
    if len(extra) >= 2:
        kb.append([InlineKeyboardButton(text="🔄 GANTI FOTO ALBUM 2", callback_data="gallery_change_extra_2")])
    else:
        kb.append([InlineKeyboardButton(text="➕ UPLOAD FOTO ALBUM 2", callback_data="gallery_upload_extra_2")])
    
    # Tombol hapus semua album (jika ada)
    if extra:
        kb.append([InlineKeyboardButton(text="🗑️ HAPUS SEMUA FOTO ALBUM", callback_data="gallery_clear_all")])
    
    kb.append([InlineKeyboardButton(text="⬅️ KEMBALI KE PROFIL", callback_data="menu_profile")])
    
    media = InputMediaPhoto(media=user.photo_id or BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    if message_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        except:
            # Jika edit gagal, kirim pesan baru
            sent = await bot.send_photo(chat_id=chat_id, photo=user.photo_id or BANNER_PHOTO_ID, caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
    else:
        sent = await bot.send_photo(chat_id=chat_id, photo=user.photo_id or BANNER_PHOTO_ID, caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
        await db.update_anchor_msg(user_id, sent.message_id)


@router.callback_query(F.data == "manage_photos")
async def open_gallery(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """Membuka galeri foto"""
    await render_gallery_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.message.message_id)
    await callback.answer()


# ==========================================
# UPLOAD/GANTI FOTO PROFIL
# ==========================================
@router.callback_query(F.data == "gallery_change_main")
async def change_main_photo(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    waiting_for_upload[user_id] = "main"
    
    await callback.message.answer(
        "📸 <b>GANTI FOTO PROFIL</b>\n\n"
        "Silakan kirim foto baru untuk foto profil Anda.\n\n"
        "<i>Kirim foto sekarang...</i>",
        parse_mode="HTML"
    )
    await callback.answer()


# ==========================================
# UPLOAD/GANTI FOTO ALBUM 1
# ==========================================
@router.callback_query(F.data == "gallery_upload_extra_1")
@router.callback_query(F.data == "gallery_change_extra_1")
async def handle_extra_1(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    waiting_for_upload[user_id] = "extra_1"
    
    await callback.message.answer(
        "📸 <b>FOTO ALBUM 1</b>\n\n"
        "Silakan kirim foto untuk album 1.\n\n"
        "<i>Kirim foto sekarang...</i>",
        parse_mode="HTML"
    )
    await callback.answer()


# ==========================================
# UPLOAD/GANTI FOTO ALBUM 2
# ==========================================
@router.callback_query(F.data == "gallery_upload_extra_2")
@router.callback_query(F.data == "gallery_change_extra_2")
async def handle_extra_2(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    waiting_for_upload[user_id] = "extra_2"
    
    await callback.message.answer(
        "📸 <b>FOTO ALBUM 2</b>\n\n"
        "Silakan kirim foto untuk album 2.\n\n"
        "<i>Kirim foto sekarang...</i>",
        parse_mode="HTML"
    )
    await callback.answer()


# ==========================================
# HANDLER UNTUK SEMUA FOTO YANG DIKIRIM (DENGAN LOGGING)
# ==========================================
@router.message(F.photo)
async def handle_gallery_upload(message: types.Message, db: DatabaseService, bot: Bot):
    """Menangani semua upload foto dari galeri"""
    
    logging.info("=" * 50)
    logging.info("📸 STEP 1: Handler foto dipanggil")
    
    user_id = message.from_user.id
    action = waiting_for_upload.get(user_id)
    
    logging.info(f"📸 STEP 2: User ID: {user_id}, Action: {action}")
    
    if not action:
        logging.info("📸 STEP 3: Tidak ada action, foto diabaikan")
        return
    
    photo_id = message.photo[-1].file_id
    logging.info(f"📸 STEP 4: Photo ID diterima: {photo_id[:50]}...")
    
    try:
        if action == "main":
            logging.info("📸 STEP 5: Memanggil update_main_photo...")
            
            # Update foto utama
            async with db.session_factory() as session:
                from services.database import User as UserTable
                user = await session.get(UserTable, user_id)
                if user:
                    user.photo_id = photo_id
                    await session.commit()
                    logging.info(f"📸 STEP 6: update_main_photo BERHASIL")
                else:
                    logging.error(f"📸 STEP 6: User tidak ditemukan!")
                    await message.answer("❌ Gagal menyimpan foto! User tidak ditemukan.", parse_mode="HTML")
                    return
            
            # Verifikasi
            user = await db.get_user(user_id)
            logging.info(f"📸 STEP 7: Photo ID di database: {user.photo_id[:50] if user.photo_id else 'None'}...")
            
            await message.answer("✅ Foto profil berhasil diperbarui!", parse_mode="HTML")
            
        elif action == "extra_1":
            logging.info("📸 STEP 5: Memproses extra_1...")
            
            async with db.session_factory() as session:
                from services.database import User as UserTable
                user = await session.get(UserTable, user_id)
                if user:
                    extra = list(user.extra_photos or [])
                    
                    if len(extra) >= 1:
                        extra[0] = photo_id
                    else:
                        extra.append(photo_id)
                    
                    user.extra_photos = extra
                    await session.commit()
                    logging.info(f"📸 STEP 6: Extra photos sekarang: {extra}")
            
            await message.answer("✅ Foto album 1 berhasil diperbarui!", parse_mode="HTML")
            
        elif action == "extra_2":
            logging.info("📸 STEP 5: Memproses extra_2...")
            
            async with db.session_factory() as session:
                from services.database import User as UserTable
                user = await session.get(UserTable, user_id)
                if user:
                    extra = list(user.extra_photos or [])
                    
                    # Pastikan album 1 ada jika album 2 diisi
                    if len(extra) < 1:
                        extra.append(None)
                    
                    if len(extra) >= 2:
                        extra[1] = photo_id
                    else:
                        extra.append(photo_id)
                    
                    # Bersihkan None
                    extra = [x for x in extra if x is not None]
                    
                    user.extra_photos = extra
                    await session.commit()
                    logging.info(f"📸 STEP 6: Extra photos sekarang: {extra}")
            
            await message.answer("✅ Foto album 2 berhasil diperbarui!", parse_mode="HTML")
        
        logging.info("📸 STEP 8: Sukses! Pesan terkirim")
        
    except Exception as e:
        logging.error(f"📸 ERROR: {e}")
        await message.answer(f"❌ Gagal menyimpan foto! Error: {str(e)[:100]}", parse_mode="HTML")
    
    # Hapus session upload
    waiting_for_upload.pop(user_id, None)
    
    # Hapus pesan user
    try:
        await message.delete()
    except:
        pass
    
    # Tunggu sebentar agar user membaca pesan sukses
    await asyncio.sleep(1.5)
    
    # Kembali ke galeri foto
    await render_gallery_ui(bot, message.chat.id, user_id, db)
    
    logging.info("📸 STEP 9: Selesai")
    logging.info("=" * 50)


# ==========================================
@router.message()
async def catch_all_messages(message: types.Message):
    """Menangkap SEMUA pesan (termasuk foto)"""
    import logging
    logging.error(f"🔥 PESAN DITERIMA: {message.content_type}")
    
    if message.photo:
        logging.error(f"🔥 INI FOTO! User: {message.from_user.id}")
        await message.answer("✅ Bot menerima foto! (test)", parse_mode="HTML")

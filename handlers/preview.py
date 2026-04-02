import os
import html
import logging
from aiogram import Router, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove
from services.database import DatabaseService, User
from services.notification import NotificationService

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")

INTEREST_LABELS = {
    "int_adult": "🔞 Adult Content",
    "int_flirt": "🔥 Flirt & Dirty Talk",
    "int_rel": "❤️ Relationship",
    "int_net": "🤝 Networking",
    "int_game": "🎮 Gaming",
    "int_travel": "✈️ Traveling",
    "int_coffee": "☕ Coffee & Chill"
}


# ==========================================
# 1. CORE UI RENDERER: PROFILE PREVIEW
# ==========================================
async def render_preview_ui(bot: Bot, chat_id: int, viewer_id: int, target_id: int, context_source: str, db: DatabaseService):
    """Menampilkan preview profil dari deep link"""
    
    # Cleanup ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    viewer = await db.get_user(viewer_id)
    target = await db.get_user(target_id)
    notif_service = NotificationService(bot, db)
    
    # 🔗 Link Jalan Keluar (Escape Route)
    ch_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}" if CHANNEL_USERNAME else "https://t.me/"
    
    if not target:
        await bot.send_message(chat_id, "❌ Profil tidak ditemukan atau user telah menghapus akunnya.")
        return False
    
    if viewer_id == target_id:
        await bot.send_message(chat_id, "👋 Ini adalah link profil kamu sendiri. Gunakan tombol 'Akun Saya' di Dashboard.")
        return False
    
    is_sultan = (viewer.is_vip or viewer.is_vip_plus)
    is_unmasked_anon = False
    
    # ---------------------------------------------------
    # LOGIKA BONGKAR ANONIM (UNMASK) - KHUSUS VIP+
    # ---------------------------------------------------
    if context_source == "anon":
        if not viewer.is_vip_plus:
            return await render_locked_anon_ui(bot, chat_id, target, viewer, ch_link)
        
        # Pengecekan Kuota
        if viewer.daily_unmask_quota <= 0:
            await bot.send_message(chat_id, "❌ Kuota Harian 'Bongkar Anonim' kamu sudah habis! Tunggu reset besok.")
            return False
        
        success = await db.use_unmask_anon_quota(viewer_id)
        if success:
            # 💰 Berikan Reward ke Target
            await db.add_points_with_log(target_id, 500, f"Unmask_Bonus_{viewer_id}_{target_id}")
            # 🔔 Trigger Notifikasi
            await notif_service.trigger_unmask(target_id, viewer_id)
            is_unmasked_anon = True
    
    # ---------------------------------------------------
    # LOGIKA PUBLIC (INTIP PROFIL DARI FEED/BOOST) - VIP/VIP+
    # ---------------------------------------------------
    elif context_source in ["public", "like", "view", "inbox", "match"]:
        # Untuk like/view, tidak perlu potong kuota
        if context_source not in ["like", "view", "match"]:
            if not is_sultan:
                return await render_upgrade_block_ui(bot, chat_id, target.full_name, viewer, ch_link)
        
        # Hanya untuk context_source "public" yang memotong kuota
        if context_source == "public":
            if viewer.daily_open_profile_quota <= 0:
                await bot.send_message(chat_id, "❌ Kuota Harian 'Buka Foto Profil' kamu sudah habis! Tunggu reset besok.")
                return False
            
            is_new_view = await db.log_and_check_daily_reward(viewer_id, target_id, "VIEW_PROFILE")
            if is_new_view:
                success = await db.use_unmask_quota(viewer_id)
                if success:
                    await db.add_points_with_log(target_id, 100, f"Profil_Diintip_{viewer_id}_{target_id}")
                    await notif_service.trigger_view(target_id, viewer_id)
        
        # Untuk context_source "like" - beri notifikasi like
        elif context_source == "like":
            await notif_service.trigger_like(target_id, viewer_id)
    
    else:
        await bot.send_message(chat_id, "❌ Akses link tidak valid.")
        return False
    
    # ==========================================
    # PEMBENTUKAN TAMPILAN (UI) PROFIL
    # ==========================================
    if target.is_vip_plus:
        target_kasta = "💎 VIP+"
    elif target.is_vip:
        target_kasta = "🌟 VIP"
    elif target.is_premium:
        target_kasta = "🎭 PREMIUM"
    else:
        target_kasta = "👤 FREE"
    
    # Format minat
    minat_list = []
    for i in (target.interests or "").split(","):
        i = i.strip()
        if i in INTEREST_LABELS:
            minat_list.append(INTEREST_LABELS[i])
        elif i:
            minat_list.append(i)
    minat = ", ".join(minat_list) if minat_list else "-"
    
    target_name = html.escape(target.full_name) if target.full_name else "Anonim"
    target_loc = html.escape(target.location_name) if target.location_name else "-"
    target_bio = html.escape(target.bio) if target.bio else "-"
    
    text_full = (
        f"👤 <b>PROFIL: {target_name.upper()}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👑 <b>Status:</b> {target_kasta}\n"
        f"🎂 <b>Usia:</b> {target.age} Tahun\n"
        f"👫 <b>Gender:</b> {target.gender.title() if target.gender else '-'}\n"
        f"📍 <b>Kota:</b> {target_loc}\n"
        f"🔥 <b>Minat:</b> {minat}\n"
        f"📝 <b>Bio:</b>\n<i>{target_bio}</i>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>"
    )
    
    kb_buttons = []
    
    if is_unmasked_anon:
        text_full = f"🔓 <b>IDENTITAS BERHASIL DIBONGKAR!</b>\n\n" + text_full + f"\n\n<i>Sesi chat terbuka! Kuota Bongkar Anonim terpakai 1.</i>"
        kb_buttons.append([InlineKeyboardButton(text="✍️ KIRIM PESAN", callback_data=f"chat_{target_id}_unmask")])
    elif context_source in ["like", "view", "match"]:
        if context_source == "like":
            text_full = f"❤️ <b>SESEORANG MENYUKAIMU!</b>\n\n" + text_full
        elif context_source == "match":
            text_full = f"💖 <b>MATCH! KALIAN SALING SUKA</b>\n\n" + text_full
        else:
            text_full = f"👀 <b>SESEORANG MENGINTIP PROFILMU</b>\n\n" + text_full
        
        kb_buttons.append([InlineKeyboardButton(text="💌 BALAS PESAN", callback_data=f"chat_{target_id}_{context_source}")])
    elif context_source == "inbox":
        text_full = f"📥 <b>PENGIRIM PESAN INBOX</b>\n\n" + text_full
        kb_buttons.append([InlineKeyboardButton(text="💬 BALAS PESAN (+200 Poin)", callback_data=f"chat_{target_id}_inbox")])
    else:
        kb_buttons.append([InlineKeyboardButton(text="💌 KIRIM PESAN", callback_data=f"chat_{target_id}_public")])
    
    # 🚪 TOMBOL JALAN KELUAR (ESCAPE ROUTES)
    kb_buttons.append([
        InlineKeyboardButton(text="📺 Kembali ke Channel", url=ch_link),
        InlineKeyboardButton(text="🏠 Dashboard", callback_data="back_to_dashboard")
    ])
    
    # Kirim sebagai pesan baru (karena berasal dari Deep Link)
    await bot.send_photo(
        chat_id=chat_id,
        photo=target.photo_id,
        caption=text_full,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons),
        parse_mode="HTML"
    )
    return True


# ==========================================
# 2. RENDERER PEMBLOKIR AKSES (UPSELL)
# ==========================================
async def render_upgrade_block_ui(bot: Bot, chat_id: int, target_name: str, viewer: User, ch_link: str):
    """Tampilan untuk user yang belum punya akses VIP"""
    name_safe = html.escape(target_name[:3]) if target_name else "Ano"
    text_lock = (
        f"🔒 <b>PROFIL TERKUNCI</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"Profil <b>{name_safe}***</b> dari Channel hanya bisa dibuka oleh Member <b>VIP / VIP+</b>.\n\n"
        f"<i>Upgrade akunmu sekarang untuk bisa melihat profil lengkap dan mengirim pesan!</i>"
    )
    kb_lock = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 UPGRADE VIP SEKARANG", callback_data="menu_pricing")],
        [InlineKeyboardButton(text="📺 Kembali ke Channel", url=ch_link),
         InlineKeyboardButton(text="🏠 Dashboard", callback_data="back_to_dashboard")]
    ])
    await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_lock, reply_markup=kb_lock, parse_mode="HTML")
    return True


async def render_locked_anon_ui(bot: Bot, chat_id: int, target: User, viewer: User, ch_link: str):
    """Tampilan untuk user yang bukan VIP+ mencoba unmask"""
    loc_safe = html.escape(target.location_name) if target.location_name else "Suatu Tempat"
    text_anon = (
        f"🎭 <b>POSTINGAN ANONIM TERKUNCI</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"Seseorang di <b>{loc_safe}</b> memposting ini.\n"
        f"Identitasnya disembunyikan dan HANYA bisa dibongkar oleh Sultan <b>VIP+</b>."
    )
    kb_anon = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 UPGRADE VIP+ UNTUK BONGKAR", callback_data="menu_pricing")],
        [InlineKeyboardButton(text="📺 Kembali ke Channel", url=ch_link),
         InlineKeyboardButton(text="🏠 Dashboard", callback_data="back_to_dashboard")]
    ])
    await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_anon, reply_markup=kb_anon, parse_mode="HTML")
    return True


# ==========================================
# 3. GATEWAY HANDLER (Dari start.py)
# ==========================================
async def process_profile_preview(message_or_callback: types.Message | types.CallbackQuery, bot: Bot, db: DatabaseService, viewer_id: int, target_id: int, context_source: str):
    """Entry point untuk preview profil dari deep link"""
    chat_id = message_or_callback.chat.id if isinstance(message_or_callback, types.Message) else message_or_callback.message.chat.id
    await render_preview_ui(bot, chat_id, viewer_id, target_id, context_source, db)

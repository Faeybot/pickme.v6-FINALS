import os
import html
import logging
from aiogram import Router, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

from services.database import DatabaseService, User, PointLog
from services.notification import NotificationService

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")

INTEREST_LABELS = {
    "int_adult": "🔞 Adult Content", "int_flirt": "🔥 Flirt & Dirty Talk", "int_rel": "❤️ Relationship",
    "int_net": "🤝 Networking", "int_game": "🎮 Gaming", "int_travel": "✈️ Traveling", "int_coffee": "☕ Coffee & Chill"
}

# ==========================================
# 1. CORE UI RENDERER: PROFILE PREVIEW
# ==========================================
async def render_preview_ui(bot: Bot, chat_id: int, viewer_id: int, target_id: int, context_source: str, db: DatabaseService):
    viewer = await db.get_user(viewer_id)
    target = await db.get_user(target_id)
    notif_service = NotificationService(bot, db)
    
    # 🔗 Link Jalan Keluar (Escape Route)
    ch_link = f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}" if CHANNEL_USERNAME else "https://t.me/"

    if not target:
        msg = await bot.send_message(chat_id, "❌ Profil tidak ditemukan atau user telah menghapus akunnya.")
        return False
        
    if viewer_id == target_id:
        msg = await bot.send_message(chat_id, "👋 Ini adalah link profil kamu sendiri. Gunakan tombol 'Akun Saya' di Dashboard.")
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
            await db.add_points_with_log(target_id, 100, "Profil Dibongkar (Unmask)")
            # 🔔 Trigger Notifikasi (Dieksekusi oleh notification.py)
            await notif_service.trigger_unmask(target_id, viewer_id)
            is_unmasked_anon = True

    # ---------------------------------------------------
    # LOGIKA PUBLIC (INTIP PROFIL DARI FEED/BOOST) - VIP/VIP+
    # ---------------------------------------------------
    elif context_source == "public":
        if not is_sultan:
            return await render_upgrade_block_ui(bot, chat_id, target.full_name, viewer, ch_link)
        
        # Pengecekan Kuota
        if viewer.daily_open_profile_quota <= 0:
            await bot.send_message(chat_id, "❌ Kuota Harian 'Buka Foto Profil' kamu sudah habis! Tunggu reset besok.")
            return False

        is_new_view = await db.log_and_check_daily_reward(viewer_id, target_id, "VIEW_PROFILE")
        if is_new_view:
            success = await db.use_unmask_quota(viewer_id)
            if success:
                # 💰 Berikan Reward ke Target
                await db.add_points_with_log(target_id, 100, "Profil Diintip (Feed)")
                # 🔔 Trigger Notifikasi
                await notif_service.trigger_view(target_id, viewer_id)

    else:
        await bot.send_message(chat_id, "❌ Akses link tidak valid.")
        return False

    # ==========================================
    # PEMBENTUKAN TAMPILAN (UI) PROFIL
    # ==========================================
    target_kasta = "💎 VIP+" if target.is_vip_plus else "🌟 VIP" if target.is_vip else "🎭 PREMIUM" if target.is_premium else "👤 FREE"
    minat_list = [INTEREST_LABELS.get(i.strip(), i.strip()) for i in (target.interests or "").split(",")]
    minat = ", ".join(minat_list) if target.interests else "-"

    target_name = html.escape(target.full_name) if target.full_name else "Anonim"
    target_loc = html.escape(target.location_name) if target.location_name else "-"
    target_bio = html.escape(target.bio) if target.bio else "-"

    text_full = (
        f"👤 <b>PROFIL: {target_name.upper()}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👑 <b>Status:</b> {target_kasta}\n"
        f"🎂 <b>Usia:</b> {target.age} Tahun\n"
        f"👫 <b>Gender:</b> {target.gender.title()}\n"
        f"📍 <b>Kota:</b> {target_loc}\n"
        f"🔥 <b>Minat:</b> {minat}\n"
        f"📝 <b>Bio:</b>\n<i>{target_bio}</i>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>"
    )

    kb_buttons = []

    if is_unmasked_anon:
        text_full = f"🔓 <b>IDENTITAS BERHASIL DIBONGKAR!</b>\n\n" + text_full + f"\n\n<i>Sesi chat terbuka! Kuota Bongkar Anonim terpakai 1.</i>"
        kb_buttons.append([InlineKeyboardButton(text="✍️ KIRIM PESAN", callback_data=f"chat_{target_id}_unmask")])
    else:
        text_full = f"🔍 <b>MENGINTIP PROFIL FEED</b>\n\n" + text_full + f"\n\n<i>Kuota Buka Profil terpakai 1.</i>"
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
    chat_id = message_or_callback.chat.id if isinstance(message_or_callback, types.Message) else message_or_callback.message.chat.id
    await render_preview_ui(bot, chat_id, viewer_id, target_id, context_source, db)

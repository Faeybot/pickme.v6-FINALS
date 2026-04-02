"""
STATUS & KUOTA - Menampilkan sisa kuota harian user
File ini berdiri sendiri, dipanggil dari account.py
"""

import os
import logging
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove
from services.database import DatabaseService

router = Router()
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")


async def render_status_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    """Tampilan status kuota user"""
    
    # Cleanup ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    user = await db.get_user(user_id)
    if not user:
        return False
    
    await db.push_nav(user_id, "status")
    
    # Tentukan kasta dan kuota
    if user.is_vip_plus:
        kasta = "💎 VIP+"
        swipe_limit = 50
    elif user.is_vip:
        kasta = "🌟 VIP"
        swipe_limit = 30
    elif user.is_premium:
        kasta = "🎭 PREMIUM"
        swipe_limit = 20
    else:
        kasta = "👤 FREE"
        swipe_limit = 10
    
    swipe_left = max(0, swipe_limit - user.daily_swipe_count)
    total_boost = user.paid_boost_balance + user.weekly_free_boost
    
    text = (
        f"📊 <b>STATUS AKUN & KUOTA</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"👑 <b>Status Akun:</b> {kasta}\n\n"
        
        f"📑 <b>Sisa Kuota Harian</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"🔍 Swipe Jodoh: <b>{swipe_left} / {swipe_limit}</b>\n"
        f"👀 Buka Profil: <b>{user.daily_open_profile_quota}</b>\n"
        f"🎭 Bongkar Anonim: <b>{user.daily_unmask_quota}</b>\n"
        f"💬 Kirim Pesan: <b>{user.daily_message_quota}</b>\n"
        f"📝 Post Teks Feed: <b>{user.daily_feed_text_quota}</b>\n"
        f"📸 Post Foto Feed: <b>{user.daily_feed_photo_quota}</b>\n"
        f"<i>(Reset setiap pukul 00:00 WIB)</i>\n\n"
        
        f"🚀 <b>Tiket Boost</b>\n"
        f"🎁 Boost Gratis: <b>{user.weekly_free_boost}</b>\n"
        f"🎫 Boost Berbayar: <b>{user.paid_boost_balance}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 UPGRADE KASTA", callback_data="menu_pricing")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Akun Saya", callback_data="menu_account")]
    ])
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    if callback_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
            await bot.answer_callback_query(callback_id)
        except:
            pass
    else:
        try:
            sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
        except Exception as e:
            logging.error(f"Gagal render status UI: {e}")
    
    return True

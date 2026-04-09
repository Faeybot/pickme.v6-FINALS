import os
import math
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove
from services.database import DatabaseService
from utils.helpers import send_temp_message

router = Router()
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")
ITEMS_PER_PAGE = 5


# ==========================================
# 1. RENDER DAFTAR PENGUNJUNG PROFIL
# ==========================================
async def render_who_see_me_list(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, page: int = 0, message_id: int = None):
    """Menampilkan daftar orang yang melihat profil"""
    
    # Cleanup ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    viewers = await db.get_interaction_list(user_id, "VIEW", limit=50)
    user = await db.get_user(user_id)
    
    text_content = "👀 <b>PENGUNJUNG PROFILMU</b>\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
    
    if not viewers:
        text_content += "<i>Belum ada yang melihat profilmu. Coba gunakan Boost Profil!</i>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="menu_notifications")]])
    else:
        total_pages = math.ceil(len(viewers) / ITEMS_PER_PAGE)
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        current_viewers = viewers[start_idx:end_idx]
        
        is_sultan = (user.is_vip or user.is_vip_plus)
        
        if is_sultan:
            text_content += f"Ada <b>{len(viewers)}</b> orang yang mengintip profilmu! Silakan cek:\n\n"
        else:
            text_content += f"Ada <b>{len(viewers)}</b> orang yang mengintip profilmu!\n🔒 <i>Upgrade ke VIP/VIP+ untuk membuka sensor nama dan profil mereka!</i>\n\n"
        
        kb_buttons = []
        for person in current_viewers:
            if is_sultan:
                btn_text = f"👤 {person.full_name}, {person.age}th - {person.location_name}"
                kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"wsm_view_{person.id}_{page}")])
            else:
                btn_text = f"🔒 {person.full_name[:3]}***, {person.age}th - {person.location_name}"
                kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data="menu_pricing")])
        
        # Navigasi Paginasi
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"wsm_page_{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"wsm_page_{page+1}"))
        if nav_row:
            kb_buttons.append(nav_row)
        
        kb_buttons.append([InlineKeyboardButton(text="⬅️ Kembali ke Notifikasi", callback_data="menu_notifications")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text_content, parse_mode="HTML")
    
    if message_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=kb)
        except Exception:
            pass
    else:
        user_db = await db.get_user(user_id)
        if user_db and user_db.anchor_msg_id:
            try:
                await bot.edit_message_media(chat_id=chat_id, message_id=user_db.anchor_msg_id, media=media, reply_markup=kb)
            except:
                sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_content, reply_markup=kb, parse_mode="HTML")
                await db.update_anchor_msg(user_id, sent.message_id)
        else:
            sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_content, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)


@router.callback_query(F.data == "notif_view")
async def handle_list_viewers(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_who_see_me_list(bot, callback.message.chat.id, callback.from_user.id, db, page=0, message_id=callback.message.message_id)
    await callback.answer()


@router.callback_query(F.data.startswith("wsm_page_"))
async def handle_wsm_page(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    page = int(callback.data.split("_")[2])
    await render_who_see_me_list(bot, callback.message.chat.id, callback.from_user.id, db, page=page, message_id=callback.message.message_id)
    await callback.answer()


# ==========================================
# 2. RENDER PROFIL PENGUNJUNG (KHUSUS SULTAN)
# ==========================================
@router.callback_query(F.data.startswith("wsm_view_"))
async def view_visitor_profile(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    user = await db.get_user(callback.from_user.id)
    
    if not (user.is_vip or user.is_vip_plus):
        return await callback.answer("🔒 AKSES DITOLAK: Fitur ini eksklusif untuk VIP / VIP+!", show_alert=True)
    
    _, _, target_id_str, page_str = callback.data.split("_")
    target_id, page = int(target_id_str), int(page_str)
    
    target = await db.get_user(target_id)
    if not target:
        return await callback.answer("Pengguna tidak ditemukan.", show_alert=True)
    
    # Tentukan kasta target
    if target.is_vip_plus:
        kasta = "💎 VIP+"
    elif target.is_vip:
        kasta = "🌟 VIP"
    elif target.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"
    
    text = (
        f"👀 <b>DIA MENGINTIP PROFILMU!</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👤 <b>{target.full_name.upper()}, {target.age}</b>\n"
        f"👑 Kasta: {kasta}\n"
        f"📍 {target.location_name}\n"
        f"🔥 <b>Minat:</b> {target.interests or '-'}\n"
        f"📝 <blockquote>{target.bio or 'Tidak ada bio.'}</blockquote>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ KIRIM LIKE", callback_data=f"swipe_like_from_view_{target.id}"),
         InlineKeyboardButton(text="💌 KIRIM PESAN", callback_data=f"chat_{target.id}_public")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Daftar", callback_data=f"wsm_page_{page}")]
    ])
    
    media = InputMediaPhoto(media=target.photo_id, caption=text, parse_mode="HTML")
    try:
        await callback.message.edit_media(media=media, reply_markup=kb)
    except:
        pass
    
    # Tandai notifikasi sebagai sudah dibaca
    await db.mark_notif_read(callback.from_user.id, target_id, "VIEW")
    await callback.answer()


# ==========================================
# 3. HANDLER LIKE DARI VIEW
# ==========================================
@router.callback_query(F.data.startswith("swipe_like_from_view_"))
async def handle_like_from_view(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    target_id = int(callback.data.split("_")[3])
    user_id = callback.from_user.id
    
    # Record swipe
    await db.record_swipe(user_id, target_id, "like")
    
    # Cek match
    is_match = await db.process_match_logic(user_id, target_id)
    
    if is_match:
        user_a, user_b = await db.get_user(user_id), await db.get_user(target_id)
        try:
            await bot.send_temp_message(target_id, f"🎉 <b>IT'S A MATCH!</b>\nKamu saling suka dengan <b>{user_a.full_name.upper()}</b>!\nSilakan cek menu <b>Notifikasi > Match</b> untuk mulai mengobrol gratis.", parse_mode="HTML")
        except:
            pass
        try:
            await bot.send_temp_message(user_id, f"🎉 <b>IT'S A MATCH!</b>\nKamu saling suka dengan <b>{user_b.full_name.upper()}</b>!\nSilakan cek menu <b>Notifikasi > Match</b> untuk mulai mengobrol gratis.", parse_mode="HTML")
        except:
            pass
        await callback.answer("🎉 IT'S A MATCH! Cek menu Match!", show_alert=True)
    else:
        await callback.answer("❤️ Like terkirim!", show_alert=False)
    
    # Kembali ke daftar
    await render_who_see_me_list(bot, callback.message.chat.id, user_id, db, page=0, message_id=callback.message.message_id)

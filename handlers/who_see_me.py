import os
import math
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")
ITEMS_PER_PAGE = 5

# ==========================================
# 1. RENDER DAFTAR PENGUNJUNG PROFIL
# ==========================================
async def render_who_see_me_list(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, page: int = 0, message_id: int = None):
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
            text_content += f"Ada <b>{len(viewers)}</b> orang yang mengintip profilmu! Silakan cek:\n"
        else:
            text_content += f"Ada <b>{len(viewers)}</b> orang yang mengintip profilmu!\n🔒 <i>Upgrade ke VIP/VIP+ untuk membuka sensor nama dan profil mereka!</i>\n"
            
        kb_buttons = []
        for person in current_viewers:
            if is_sultan:
                btn_text = f"👤 {person.full_name}, {person.age}th - {person.location_name}"
                kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"wsm_view_{person.id}_{page}")])
            else:
                btn_text = f"🔒 {person.full_name[:3]}***, {person.age}th - {person.location_name}"
                kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data="menu_pricing")])
            
        nav_row = []
        if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"wsm_page_{page-1}"))
        if page < total_pages - 1: nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"wsm_page_{page+1}"))
        if nav_row: kb_buttons.append(nav_row)
            
        kb_buttons.append([InlineKeyboardButton(text="⬅️ Kembali ke Notifikasi", callback_data="menu_notifications")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text_content, parse_mode="HTML")
    
    if message_id:
        try: await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=kb)
        except: pass
    else:
        await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_content, reply_markup=kb, parse_mode="HTML")

# --- HANDLER PENANGKAP MENU & HALAMAN ---
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
    if not target: return await callback.answer("Pengguna tidak ditemukan.", show_alert=True)
        
    text = (
        f"👀 <b>DIA MENGINTIP PROFILMU!</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👤 <b>{target.full_name.upper()}, {target.age}</b>\n"
        f"📍 {target.location_name}\n"
        f"🔥 <b>Minat:</b> {target.interests or '-'}\n"
        f"📝 <blockquote>{target.bio or 'Tidak ada bio.'}</blockquote>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ KIRIM LIKE", callback_data=f"swipe_like"), # Menggunakan handler swipe dari discovery
         InlineKeyboardButton(text="💌 KIRIM PESAN", callback_data=f"chat_{target.id}_public")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Daftar", callback_data=f"wsm_page_{page}")]
    ])
    
    media = InputMediaPhoto(media=target.photo_id, caption=text, parse_mode="HTML")
    try: await callback.message.edit_media(media=media, reply_markup=kb)
    except: pass
    
    # Tandai notifikasi sebagai sudah dibaca
    await db.mark_notif_read(callback.from_user.id, target_id, "VIEW")
    await callback.answer()

import os
import math
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")
ITEMS_PER_PAGE = 5

async def render_match_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, page: int = 0, message_id: int = None):
    matches = await db.get_interaction_list(user_id, "MATCH", limit=50)
    
    text_content = "💖 <b>DAFTAR MATCH KAMU</b>\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
    
    if not matches:
        text_content += "<i>Belum ada Match. Terus geser profil di Discovery!</i>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="menu_notifications")]])
    else:
        total_pages = math.ceil(len(matches) / ITEMS_PER_PAGE)
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        current_matches = matches[start_idx:end_idx]
        
        text_content += f"Kamu memiliki <b>{len(matches)}</b> Match!\nPilih profil untuk melihat detail atau mulai mengobrol:\n"
        
        kb_buttons = []
        for person in current_matches:
            btn_text = f"👤 {person.full_name}, {person.age}th - {person.location_name}"
            kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"match_view_{person.id}_{page}")])
            
        # Paginasi Navigasi
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"match_page_{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"match_page_{page+1}"))
            
        if nav_row:
            kb_buttons.append(nav_row)
            
        kb_buttons.append([InlineKeyboardButton(text="⬅️ Kembali ke Notifikasi", callback_data="menu_notifications")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text_content, parse_mode="HTML")
    
    if message_id:
        try: await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=kb)
        except: pass
    else:
        await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_content, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "list_my_matches")
async def handle_list_matches(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_match_ui(bot, callback.message.chat.id, callback.from_user.id, db, page=0, message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("match_page_"))
async def handle_match_page(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    page = int(callback.data.split("_")[2])
    await render_match_ui(bot, callback.message.chat.id, callback.from_user.id, db, page=page, message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("match_view_"))
async def view_match_profile(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    _, _, target_id_str, page_str = callback.data.split("_")
    target_id, page = int(target_id_str), int(page_str)
    
    target = await db.get_user(target_id)
    if not target:
        return await callback.answer("Pengguna tidak ditemukan.", show_alert=True)
        
    text = (
        f"💖 <b>MATCH PROFILE</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👤 <b>{target.full_name.upper()}, {target.age}</b>\n"
        f"📍 {target.location_name}\n"
        f"🔥 <b>Minat:</b> {target.interests or '-'}\n"
        f"📝 <blockquote>{target.bio or 'Tidak ada bio.'}</blockquote>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 KIRIM PESAN", callback_data=f"chat_{target.id}_match")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Daftar Match", callback_data=f"match_page_{page}")]
    ])
    
    media = InputMediaPhoto(media=target.photo_id, caption=text, parse_mode="HTML")
    try: await callback.message.edit_media(media=media, reply_markup=kb)
    except: pass
    await callback.answer()

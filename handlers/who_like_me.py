import os
import math
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")
ITEMS_PER_PAGE = 5

async def render_who_like_me_list(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, page: int = 0, message_id: int = None):
    likers = await db.get_interaction_list(user_id, "LIKE", limit=50)
    user = await db.get_user(user_id)
    
    text_content = "❤️ <b>PENGAGUM RAHASIAMU</b>\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
    
    if not likers:
        text_content += "<i>Belum ada yang menyukaimu. Tingkatkan visibilitasmu dengan Boost atau ubah filter pencarian!</i>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="menu_notifications")]])
    else:
        total_pages = math.ceil(len(likers) / ITEMS_PER_PAGE)
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        current_likers = likers[start_idx:end_idx]
        
        if user.is_vip_plus:
            text_content += f"Ada <b>{len(likers)}</b> orang yang menyukaimu! Silakan cek profil mereka:\n"
        else:
            text_content += f"Ada <b>{len(likers)}</b> orang yang menyukaimu!\n🔒 <i>Upgrade ke VIP+ untuk membuka profil mereka dan langsung Match!</i>\n"
            
        kb_buttons = []
        for person in current_likers:
            # NAMA DITAMPILKAN JELAS, TIDAK DISENSOR
            btn_text = f"👤 {person.full_name}, {person.age}th - {person.location_name}"
            kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"wlm_view_{person.id}_{page}")])
            
        nav_row = []
        if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"wlm_page_{page-1}"))
        if page < total_pages - 1: nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"wlm_page_{page+1}"))
        if nav_row: kb_buttons.append(nav_row)
            
        kb_buttons.append([InlineKeyboardButton(text="⬅️ Kembali ke Notifikasi", callback_data="menu_notifications")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text_content, parse_mode="HTML")
    
    if message_id:
        try: await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=kb)
        except: pass
    else:
        await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_content, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "list_who_like_me")
@router.callback_query(F.data == "notif_like")
async def handle_list_likers(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_who_like_me_list(bot, callback.message.chat.id, callback.from_user.id, db, page=0, message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("wlm_page_"))
async def handle_wlm_page(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    page = int(callback.data.split("_")[2])
    await render_who_like_me_list(bot, callback.message.chat.id, callback.from_user.id, db, page=page, message_id=callback.message.message_id)
    await callback.answer()

# === GATEKEEPER VIP+ & RENDER PROFIL ===
@router.callback_query(F.data.startswith("wlm_view_"))
async def view_liker_profile(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    user = await db.get_user(callback.from_user.id)
    
    # 🛑 JEBAKAN PAYWALL
    if not user.is_vip_plus:
        await callback.answer("🔒 AKSES DITOLAK: Fitur ini eksklusif untuk VIP+! Silakan Upgrade.", show_alert=True)
        from handlers.pricing import render_pricing_ui
        return await render_pricing_ui(bot, callback.message.chat.id, callback.from_user.id, db)
        
    _, _, target_id_str, page_str = callback.data.split("_")
    target_id, page = int(target_id_str), int(page_str)
    
    target = await db.get_user(target_id)
    if not target: return await callback.answer("Pengguna tidak ditemukan.", show_alert=True)
        
    text = (
        f"❤️ <b>DIA MENYUKAIMU!</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👤 <b>{target.full_name.upper()}, {target.age}</b>\n"
        f"📍 {target.location_name}\n"
        f"🔥 <b>Minat:</b> {target.interests or '-'}\n"
        f"📝 <blockquote>{target.bio or 'Tidak ada bio.'}</blockquote>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"<i>Balas Like untuk langsung Match!</i>"
    )
    
    # Tombol Aksi Langsung di Bawah Profil
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❤️ LIKE BALIK (MATCH)", callback_data=f"wlm_action_like_{target.id}_{page}"),
            InlineKeyboardButton(text="❌ SKIP", callback_data=f"wlm_action_skip_{target.id}_{page}")
        ],
        [InlineKeyboardButton(text="⬅️ Kembali ke Daftar", callback_data=f"wlm_page_{page}")]
    ])
    
    media = InputMediaPhoto(media=target.photo_id, caption=text, parse_mode="HTML")
    try: await callback.message.edit_media(media=media, reply_markup=kb)
    except: pass
    await callback.answer()

# === EKSEKUSI MATCH DARI WLM ===
@router.callback_query(F.data.startswith("wlm_action_"))
async def handle_wlm_action(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    parts = callback.data.split("_")
    action = parts[2] # 'like' atau 'skip'
    target_id = int(parts[3])
    page = int(parts[4])
    
    user_id = callback.from_user.id
    
    if action == "like":
        # Eksekusi logika Match di database (menghapus notif LIKE, membuat notif MATCH)
        is_matched = await db.process_match_logic(user_id, target_id)
        if is_matched:
            await callback.answer("🎉 IT'S A MATCH! Kalian sekarang bisa saling berkirim pesan.", show_alert=True)
            try: await bot.send_message(target_id, f"🎉 <b>IT'S A MATCH!</b>\nSeseorang baru saja membalas Like-mu! Cek menu Match sekarang.", parse_mode="HTML")
            except: pass
        else:
            await callback.answer("Match diproses.", show_alert=False)
            
    elif action == "skip":
        # Hapus Notifikasi LIKE agar tidak muncul lagi di list
        await db.remove_interaction(user_id, target_id, "LIKE")
        await callback.answer("Profil dilewati.", show_alert=False)
        
    # Kembalikan ke daftar setelah aksi
    await render_who_like_me_list(bot, callback.message.chat.id, user_id, db, page=page, message_id=callback.message.message_id)

import os
import math
import datetime
import html
import logging
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")
ITEMS_PER_PAGE = 5

# ==========================================
# HELPER: FORMATTER WAKTU & TEKS
# ==========================================
def get_time_left(expires_at: int) -> str:
    now = int(datetime.datetime.now().timestamp())
    if expires_at <= now:
        return "Habis"
    
    diff = expires_at - now
    hours = diff // 3600
    minutes = (diff % 3600) // 60
    
    if hours > 0: return f"{hours}j {minutes}m"
    return f"{minutes}m"

# ==========================================
# 1. CORE UI RENDERER: INBOX LIST
# ==========================================
async def render_inbox_list(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, page: int = 0, message_id: int = None):
    sessions = await db.get_inbox_sessions(user_id)
    
    text_content = "📥 <b>INBOX PESAN AKTIF</b>\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
    
    if not sessions:
        text_content += "<i>Belum ada pesan. Mulai sapa seseorang di Lobi!</i>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Notifikasi", callback_data="menu_notifications")]])
    else:
        total_pages = math.ceil(len(sessions) / ITEMS_PER_PAGE)
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        current_sessions = sessions[start_idx:end_idx]
        
        text_content += f"Kamu memiliki <b>{len(sessions)}</b> histori percakapan.\n<i>Pilih pesan di bawah ini:</i>\n"
        
        kb_buttons = []
        now = int(datetime.datetime.now().timestamp())
        
        for sess in current_sessions:
            target_id = sess.target_id if sess.user_id == user_id else sess.user_id
            target = await db.get_user(target_id)
            if not target: continue
            
            # Format UI: [Username, (Timer), Pesan...]
            name_short = target.full_name[:10]
            time_str = get_time_left(sess.expires_at)
            
            raw_msg = sess.last_message or "Belum ada pesan."
            msg_short = raw_msg[:20] + "..." if len(raw_msg) > 20 else raw_msg
            
            is_active = sess.expires_at > now
            status_icon = "🟢" if is_active else "🔴"
            
            btn_text = f"{status_icon} {name_short} ({time_str}) - {msg_short}"
            
            # Routing: Jika aktif (View), Jika habis (Extend)
            if is_active:
                kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"inx_v_{target_id}_{page}")])
            else:
                kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"inx_x_{target_id}_{page}")])
                
        # Navigasi Paginasi
        nav_row = []
        if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"inx_p_{page-1}"))
        if page < total_pages - 1: nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"inx_p_{page+1}"))
        if nav_row: kb_buttons.append(nav_row)
            
        kb_buttons.append([InlineKeyboardButton(text="⬅️ Kembali ke Notifikasi", callback_data="menu_notifications")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text_content, parse_mode="HTML")
    
    if message_id:
        try: await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=kb)
        except Exception: pass
    else:
        await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_content, reply_markup=kb, parse_mode="HTML")

# --- HANDLER NAVIGASI INBOX ---
@router.callback_query(F.data == "notif_inbox")
async def handle_open_inbox(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await db.push_nav(callback.from_user.id, "inbox")
    await render_inbox_list(bot, callback.message.chat.id, callback.from_user.id, db, page=0, message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("inx_p_"))
async def handle_inbox_pagination(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    page = int(callback.data.split("_")[2])
    await render_inbox_list(bot, callback.message.chat.id, callback.from_user.id, db, page=page, message_id=callback.message.message_id)
    await callback.answer()

# ==========================================
# 2. LOGIKA BUKA PESAN AKTIF & KLAIM POIN
# ==========================================
@router.callback_query(F.data.startswith("inx_v_"))
async def open_active_chat(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # 1. Tandai notifikasi chat ini sudah dibaca
    await db.mark_notif_read(user_id, target_id, "CHAT")
    
    # 2. LOGIKA REWARD (Offloading dari chat.py)
    session_data = await db.get_active_chat_session(user_id, target_id)
    if session_data:
        # Pengecekan: Apakah user ini adalah PENERIMA AWAL dari sesi ini?
        # Asumsi: sess.user_id adalah inisiator, sess.target_id adalah penerima.
        if session_data.target_id == user_id: 
            origin = getattr(session_data, 'origin', 'public')
            amount = 500 if origin == "unmask" else 200
            log_key = f"InboxReplyBonus_{session_data.id}_{user_id}"
            
            bonus_exists = await db.check_bonus_exists(log_key)
            if not bonus_exists:
                sukses = await db.add_points_with_log(user_id, amount, log_key)
                if sukses:
                    try: await callback.message.answer(f"🎉 <b>BONUS INTERAKSI!</b>\nKamu mendapatkan <b>+{amount} Poin</b> karena membalas pesan ini.", parse_mode="HTML")
                    except: pass
    
    await callback.answer()
    
    # 3. LEMPAR KE CHAT.PY UNTUK DIRENDER
    # Pastikan di chat.py nanti Anda punya fungsi start_chat_room(bot, chat_id, user_id, target_id, db, state)
    from handlers.chat import start_chat_room
    await start_chat_room(bot, callback.message.chat.id, user_id, target_id, db, state, callback.message.message_id)

# ==========================================
# 3. LOGIKA PERPANJANG SESI HABIS (EXTEND)
# ==========================================
@router.callback_query(F.data.startswith("inx_x_"))
async def prompt_extend_chat(callback: types.CallbackQuery, db: DatabaseService):
    parts = callback.data.split("_")
    target_id = int(parts[2])
    page = int(parts[3])
    
    target = await db.get_user(target_id)
    if not target: return await callback.answer("User tidak ditemukan.", show_alert=True)
    
    text = (
        f"🔴 <b>SESI BERAKHIR</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"Sesi obrolan dengan <b>{target.full_name}</b> telah habis.\n\n"
        f"Kamu membutuhkan <b>1 Kuota Kirim Pesan (DM)</b> untuk membuka kembali ruang obrolan ini selama 24 Jam ke depan.\n\n"
        f"<i>Lanjutkan perpanjang?</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ YA, PERPANJANG", callback_data=f"inx_c_{target_id}")],
        [InlineKeyboardButton(text="❌ BATAL", callback_data=f"inx_p_{page}")]
    ])
    
    try: await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except: pass
    await callback.answer()

@router.callback_query(F.data.startswith("inx_c_"))
async def confirm_extend_chat(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    # Potong Kuota
    success = await db.use_message_quota(user_id)
    if not success:
        return await callback.answer("❌ Kuota DM (Kirim Pesan) Anda habis! Upgrade tier Anda.", show_alert=True)
        
    # Perpanjang Waktu Sesi (24 Jam)
    expiry_24h = int((datetime.datetime.now() + datetime.timedelta(hours=24)).timestamp())
    await db.upsert_chat_session(user_id, target_id, expires_at=expiry_24h)
    
    await callback.answer("✅ Sesi diperpanjang 24 Jam!", show_alert=True)
    
    # Lempar ke chat.py
    from handlers.chat import start_chat_room
    await start_chat_room(bot, callback.message.chat.id, user_id, target_id, db, state, callback.message.message_id)

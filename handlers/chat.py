import os
import html
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InputMediaPhoto
)

from services.database import DatabaseService
from services.notification import NotificationService

router = Router()


class ChatState(StatesGroup):
    in_room = State()


# ==========================================
# HELPER: Render History Text
# ==========================================
def render_history_text(history_list, limit=15):
    """Render history chat dari database"""
    if not history_list:
        return "<i>(Belum ada percakapan. Kirim pesan pertama!)</i>"
    
    subset = history_list[-limit:]
    lines = []
    for m in subset:
        sender = m.get('s', '?')[:12]
        text = m.get('t', '')[:200]
        time = m.get('ts', '')
        lines.append(f"<b>{sender}:</b> {html.escape(text)}")
    return "\n".join(lines)


# ==========================================
# 1. MASUK KE RUANG OBROLAN
# ==========================================
async def start_chat_room(
    bot: Bot, 
    chat_id: int, 
    user_id: int, 
    target_id: int, 
    db: DatabaseService, 
    state: FSMContext, 
    message_id: int = None
):
    """Memulai room chat dengan UI khusus"""
    
    target = await db.get_user(target_id)
    chat_sess = await db.get_active_chat_session(user_id, target_id)
    
    if not target or not chat_sess:
        return await bot.send_message(chat_id, "❌ Sesi obrolan tidak ditemukan atau sudah berakhir.")

    # ========== CLEANUP: Hapus semua pesan sebelumnya ==========
    # Hapus pesan yang dikirim sebelumnya (anchor message)
    if message_id:
        try:
            await bot.delete_message(chat_id, message_id)
        except:
            pass
    
    # Hapus semua pesan yang mungkin tersisa di state
    data = await state.get_data()
    old_sweep = data.get('sweep_list', [])
    for msg_id in old_sweep:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass
    
    # ========== AMBIL HISTORY DARI DATABASE ==========
    history = await db.get_chat_history(user_id, target_id, limit=20)
    history_text = render_history_text(history, limit=12)
    
    # ========== HEADER PROFIL ==========
    if target.is_vip_plus:
        kasta = "💎 VIP+"
    elif target.is_vip:
        kasta = "🌟 VIP"
    elif target.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"
    
    # Hitung sisa waktu
    import datetime
    now_ts = int(datetime.datetime.now().timestamp())
    if chat_sess.expires_at > now_ts:
        diff = chat_sess.expires_at - now_ts
        hours = diff // 3600
        minutes = (diff % 3600) // 60
        time_left = f"{hours}j {minutes}m" if hours > 0 else f"{minutes}m"
        status_icon = "🟢"
    else:
        time_left = "Habis"
        status_icon = "🔴"
    
    header_caption = (
        f"💬 <b>OBROLAN: {target.full_name.upper()}</b>\n"
        f"{status_icon} Status: {kasta} | 📍 {target.location_name}\n"
        f"⏳ Sesi: {time_left}\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<b>[Riwayat Terakhir]</b>\n{history_text}\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"✍️ <i>Ketik pesanmu di bawah...</i>"
    )

    # Tombol Inline untuk load history
    kb_inline = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Muat Lebih Banyak", callback_data=f"chat_loadmore_{target_id}_20")],
        [InlineKeyboardButton(text="⬇️ Ke Pesan Terbaru", callback_data=f"chat_loadmore_{target_id}_10")]
    ])

    # ========== REPLYKEYBOARD untuk Exit ==========
    kb_exit = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛑 AKHIRI OBROLAN")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    # Kirim Header (Foto Profil + Caption)
    sent_header = await bot.send_photo(
        chat_id=chat_id,
        photo=target.photo_id,
        caption=header_caption,
        reply_markup=kb_inline,
        parse_mode="HTML"
    )
    
    # Kirim instruksi + ReplyKeyboard
    sent_instruction = await bot.send_message(
        chat_id,
        "✍️ <i>Ketik pesanmu di bawah. Gunakan tombol di bawah layar untuk keluar.</i>",
        reply_markup=kb_exit,
        parse_mode="HTML"
    )
    
    # Simpan semua ID pesan untuk cleanup nanti
    await state.update_data(
        current_target_id=target_id,
        header_msg_id=sent_header.message_id,
        instruction_msg_id=sent_instruction.message_id,
        sweep_list=[sent_header.message_id, sent_instruction.message_id]
    )
    
    await state.set_state(ChatState.in_room)


# ==========================================
# 2. LOAD MORE HISTORY (Inline Button)
# ==========================================
@router.callback_query(F.data.startswith("chat_loadmore_"))
async def handle_load_history(callback: types.CallbackQuery, db: DatabaseService):
    parts = callback.data.split("_")
    target_id = int(parts[2])
    limit = int(parts[3])
    user_id = callback.from_user.id
    
    # Ambil history dari database
    history = await db.get_chat_history(user_id, target_id, limit=limit)
    history_text = render_history_text(history, limit=limit)
    
    # Edit caption header
    try:
        current_caption = callback.message.caption
        # Cari dan ganti bagian riwayat
        import re
        pattern = r'<b>\[Riwayat Terakhir\]</b>\n.*?\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>'
        replacement = f'<b>[Riwayat Terakhir]</b>\n{history_text}\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>'
        new_caption = re.sub(pattern, replacement, current_caption, flags=re.DOTALL)
        
        await callback.message.edit_caption(
            caption=new_caption,
            reply_markup=callback.message.reply_markup,
            parse_mode="HTML"
        )
    except Exception as e:
        pass
    await callback.answer()


# ==========================================
# 3. PROSES KIRIM PESAN
# ==========================================
@router.message(ChatState.in_room, F.text != "🛑 AKHIRI OBROLAN")
async def process_chat_relay(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    data = await state.get_data()
    target_id = data.get('current_target_id')
    user = await db.get_user(message.from_user.id)
    notif_service = NotificationService(bot, db)
    
    # ========== CLEANUP: Hapus pesan user agar bersih ==========
    try:
        await message.delete()
    except:
        pass
    
    if not message.text:
        return
    
    # ========== SIMPAN KE HISTORY DATABASE (Rolling Buffer) ==========
    await db.add_chat_history(user.id, target_id, user.full_name, message.text)
    
    # ========== KIRIM KE TARGET ==========
    target_text = f"<b>{user.full_name}:</b>\n{html.escape(message.text)}"
    
    # Cek apakah target sedang di room chat yang sama
    target_user = await db.get_user(target_id)
    is_target_in_room = False
    if target_user and target_user.nav_stack:
        is_target_in_room = target_user.nav_stack[-1] == f"chat_room_{user.id}"
    
    if is_target_in_room:
        # Target sedang di room chat, kirim langsung tanpa notifikasi pop-up
        try:
            await bot.send_message(target_id, target_text, parse_mode="HTML")
        except:
            pass
    else:
        # Target tidak sedang di room, kirim notifikasi
        try:
            await bot.send_message(target_id, target_text, parse_mode="HTML")
            await notif_service.trigger_new_message(target_id, user.id, user.full_name, is_reply=True)
        except:
            pass
    
    # ========== TAMPILKAN BALON PESAN DI ROOM SENDIRI ==========
    sent_bubble = await message.answer(
        f"<b>Anda:</b>\n{html.escape(message.text)}",
        parse_mode="HTML"
    )
    
    # Simpan ID pesan bubble untuk cleanup nanti
    sweep_list = data.get('sweep_list', [])
    sweep_list.append(sent_bubble.message_id)
    await state.update_data(sweep_list=sweep_list)
    
    # Log ke channel admin (opsional)
    chat_sess = await db.get_active_chat_session(user.id, target_id)
    if chat_sess and chat_sess.thread_id:
        try:
            admin_log = f"💬 <b>CHAT RELAY</b>\nFrom: <code>{user.id}</code> To: <code>{target_id}</code>\nMsg: {message.text[:200]}"
            await bot.send_message(os.getenv("CHAT_LOG_GROUP_ID"), admin_log, reply_to_message_id=chat_sess.thread_id)
        except:
            pass


# ==========================================
# 4. EXIT CHAT ROOM (CLEANUP TOTAL)
# ==========================================
@router.message(F.text == "🛑 AKHIRI OBROLAN", ChatState.in_room)
async def exit_chat_room(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    data = await state.get_data()
    sweep_list = data.get('sweep_list', [])
    header_msg_id = data.get('header_msg_id')
    instruction_msg_id = data.get('instruction_msg_id')
    
    # ========== HAPUS SEMUA PESAN DI ROOM ==========
    # Hapus pesan header (foto + caption)
    if header_msg_id:
        try:
            await bot.delete_message(chat_id, header_msg_id)
        except:
            pass
    
    # Hapus pesan instruksi
    if instruction_msg_id:
        try:
            await bot.delete_message(chat_id, instruction_msg_id)
        except:
            pass
    
    # Hapus semua bubble pesan
    for msg_id in sweep_list:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass
    
    # Hapus pesan "🛑 AKHIRI OBROLAN" yang diketik user
    try:
        await message.delete()
    except:
        pass
    
    # ========== HAPUS REPLYKEYBOARD YANG NYANGKUT ==========
    try:
        # Kirim pesan kosong dengan ReplyKeyboardRemove
        temp_msg = await bot.send_message(
            chat_id,
            "🔄",
            reply_markup=ReplyKeyboardRemove()
        )
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    # ========== KEMBALI KE INBOX ==========
    await state.clear()
    
    from handlers.inbox import render_inbox_list
    await render_inbox_list(bot, chat_id, user_id, db, page=0)


# ==========================================
# 5. HANDLER UNTUK MENU LAIN SAAT DI CHAT ROOM
# ==========================================
@router.message(ChatState.in_room, F.text.in_(["🏠 Dashboard", "📱 DASHBOARD UTAMA", "/dashboard", "/start"]))
async def exit_to_dashboard_from_chat(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    """Jika user menekan menu dashboard saat di chat room, tetap bersihkan room"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    data = await state.get_data()
    sweep_list = data.get('sweep_list', [])
    header_msg_id = data.get('header_msg_id')
    instruction_msg_id = data.get('instruction_msg_id')
    
    # Cleanup semua pesan
    if header_msg_id:
        try: await bot.delete_message(chat_id, header_msg_id)
        except: pass
    if instruction_msg_id:
        try: await bot.delete_message(chat_id, instruction_msg_id)
        except: pass
    for msg_id in sweep_list:
        try: await bot.delete_message(chat_id, msg_id)
        except: pass
    
    # Hapus ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except: pass
    
    await state.clear()
    
    # Navigasi ke dashboard
    from handlers.start import render_dashboard_ui
    await render_dashboard_ui(bot, chat_id, user_id, db, state, force_new=True)

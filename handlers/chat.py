import os
import html
import datetime
import logging
import asyncio
import re
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
# 1. HELPER: RENDER HISTORY TEXT
# ==========================================
def render_history_text(history_list, limit=15):
    """Render history chat dari database menjadi teks HTML"""
    if not history_list:
        return "<i>(Belum ada percakapan. Kirim pesan pertama!)</i>"
    
    subset = history_list[-limit:]
    lines = []
    for m in subset:
        sender = m.get('s', '?')[:12]
        text = m.get('t', '')[:200]
        lines.append(f"<b>{sender}:</b> {html.escape(text)}")
    return "\n".join(lines)


# ==========================================
# 2. FUNGSI UTAMA: START CHAT ROOM
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
    """Memulai ruang obrolan dengan tampilan history"""
    
    target = await db.get_user(target_id)
    chat_sess = await db.get_active_chat_session(user_id, target_id)
    
    if not target or not chat_sess:
        await bot.send_message(chat_id, "❌ Sesi obrolan tidak ditemukan atau sudah berakhir.")
        return
    
    # ========== CLEANUP: Hapus pesan sebelumnya ==========
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
        [InlineKeyboardButton(text="🔄 Muat Lebih Banyak", callback_data=f"chat_load_{target_id}_20")],
        [InlineKeyboardButton(text="⬇️ Ke Pesan Terbaru", callback_data=f"chat_load_{target_id}_10")]
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
# 3. HANDLER: MULAI CHAT DARI CALLBACK (PINTU MASUK UTAMA)
# ==========================================
@router.callback_query(F.data.startswith("chat_"))
async def start_chat_from_callback(
    callback: types.CallbackQuery,
    db: DatabaseService,
    bot: Bot,
    state: FSMContext
):
    """Memulai chat dari tombol Kirim Pesan di berbagai tempat:
    - discovery: chat_{target_id}_discovery
    - preview: chat_{target_id}_public
    - unmask: chat_{target_id}_unmask
    - match: chat_{target_id}_match
    - inbox: chat_{target_id}_inbox
    - feed: chat_{target_id}_feed
    """
    parts = callback.data.split("_")
    
    # Format: chat_{target_id}_{origin}
    if len(parts) >= 3:
        target_id = int(parts[1])
        origin = parts[2]  # discovery, public, unmask, match, inbox, feed
    else:
        target_id = int(parts[1])
        origin = "public"
    
    user_id = callback.from_user.id
    target = await db.get_user(target_id)
    
    if not target:
        await callback.answer("❌ Profil tidak ditemukan!", show_alert=True)
        return
    
    # Cek apakah sesi chat sudah ada
    chat_sess = await db.get_active_chat_session(user_id, target_id)
    now_ts = int(datetime.datetime.now().timestamp())
    
    if not chat_sess or chat_sess.expires_at <= now_ts:
        # Belum ada sesi, perlu buat baru
        user = await db.get_user(user_id)
        
        # ========== ORIGIN: DISCOVERY ==========
        if origin == "discovery":
            # Cek apakah user VIP/VIP+
            if not (user.is_vip or user.is_vip_plus):
                await callback.answer("🔒 Fitur Kirim Pesan hanya untuk VIP/VIP+!\nUpgrade dulu ya!", show_alert=True)
                return
            
            # Cek kuota
            if user.daily_message_quota <= 0 and user.extra_message_quota <= 0:
                await callback.answer("❌ Kuota DM habis! Upgrade atau tunggu reset besok.", show_alert=True)
                return
            
            # Potong kuota
            success = await db.use_message_quota(user_id)
            if not success:
                await callback.answer("❌ Gagal memotong kuota!", show_alert=True)
                return
            
            # Tentukan durasi (24 jam untuk VIP, 48 jam untuk VIP+)
            duration_hrs = 48 if user.is_vip_plus else 24
            expires_at = int((datetime.datetime.now() + datetime.timedelta(hours=duration_hrs)).timestamp())
            
            await db.upsert_chat_session(user_id, target_id, expires_at, origin="public")
        
        # ========== ORIGIN: PUBLIC (dari preview/feed) ==========
        elif origin == "public" or origin == "feed":
            # Cek apakah user VIP/VIP+
            if not (user.is_vip or user.is_vip_plus):
                await callback.answer("🔒 Fitur Kirim Pesan hanya untuk VIP/VIP+!\nUpgrade dulu ya!", show_alert=True)
                return
            
            # Cek kuota
            if user.daily_message_quota <= 0 and user.extra_message_quota <= 0:
                await callback.answer("❌ Kuota DM habis! Upgrade atau tunggu reset besok.", show_alert=True)
                return
            
            # Potong kuota
            success = await db.use_message_quota(user_id)
            if not success:
                await callback.answer("❌ Gagal memotong kuota!", show_alert=True)
                return
            
            # Tentukan durasi
            duration_hrs = 48 if user.is_vip_plus else 24
            expires_at = int((datetime.datetime.now() + datetime.timedelta(hours=duration_hrs)).timestamp())
            
            await db.upsert_chat_session(user_id, target_id, expires_at, origin="public")
        
        # ========== ORIGIN: UNMASK ==========
        elif origin == "unmask":
            # Unmask: sudah punya sesi dari proses unmask
            if not chat_sess:
                await callback.answer("❌ Sesi unmask tidak ditemukan! Silakan unmask ulang.", show_alert=True)
                return
        
        # ========== ORIGIN: MATCH ==========
        elif origin == "match":
            # Match: gratis, buat sesi 24 jam
            expires_at = int((datetime.datetime.now() + datetime.timedelta(hours=24)).timestamp())
            await db.upsert_chat_session(user_id, target_id, expires_at, origin="match")
        
        # ========== ORIGIN: INBOX (balas pesan) ==========
        elif origin == "inbox":
            # Inbox: sesi mungkin sudah ada, jika tidak ada buat baru dengan potong kuota
            if not chat_sess:
                if user.daily_message_quota <= 0 and user.extra_message_quota <= 0:
                    await callback.answer("❌ Kuota DM habis! Upgrade atau tunggu reset besok.", show_alert=True)
                    return
                
                success = await db.use_message_quota(user_id)
                if not success:
                    await callback.answer("❌ Gagal memotong kuota!", show_alert=True)
                    return
                
                duration_hrs = 48 if user.is_vip_plus else 24
                expires_at = int((datetime.datetime.now() + datetime.timedelta(hours=duration_hrs)).timestamp())
                await db.upsert_chat_session(user_id, target_id, expires_at, origin="public")
    
    # Tandai notifikasi sebagai dibaca (jika ada)
    await db.mark_notif_read(user_id, target_id, "CHAT")
    
    await callback.answer("⏳ Membuka ruang obrolan...")
    
    # Panggil fungsi start_chat_room
    await start_chat_room(
        bot,
        callback.message.chat.id,
        user_id,
        target_id,
        db,
        state,
        callback.message.message_id
    )


# ==========================================
# 4. HANDLER: LOAD MORE HISTORY
# ==========================================
@router.callback_query(F.data.startswith("chat_load_"))
async def handle_load_history(callback: types.CallbackQuery, db: DatabaseService):
    """Memuat lebih banyak history chat"""
    parts = callback.data.split("_")
    target_id = int(parts[2])
    limit = int(parts[3])
    user_id = callback.from_user.id
    
    history = await db.get_chat_history(user_id, target_id, limit=limit)
    history_text = render_history_text(history, limit=limit)
    
    # Edit caption header
    try:
        current_caption = callback.message.caption
        pattern = r'<b>\[Riwayat Terakhir\]</b>\n.*?\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>'
        replacement = f'<b>[Riwayat Terakhir]</b>\n{history_text}\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>'
        new_caption = re.sub(pattern, replacement, current_caption, flags=re.DOTALL)
        
        await callback.message.edit_caption(
            caption=new_caption,
            reply_markup=callback.message.reply_markup,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Load history error: {e}")
    await callback.answer()


# ==========================================
# 5. HANDLER: PROSES PESAN DI RUANG CHAT (DENGAN SISTEM POIN)
# ==========================================
@router.message(ChatState.in_room, F.text != "🛑 AKHIRI OBROLAN")
async def process_chat_relay(
    message: types.Message,
    state: FSMContext,
    db: DatabaseService,
    bot: Bot
):
    """Memproses pesan yang dikirim di ruang chat dengan sistem poin"""
    
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
    chat_sess = await db.add_chat_history(user.id, target_id, user.full_name, message.text)
    
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
    
    # ========== SISTEM POIN ==========
    # Ambil sesi chat untuk mengetahui origin
    current_sess = await db.get_active_chat_session(user.id, target_id)
    origin = current_sess.origin if current_sess else "public"
    
    # POIN UNTUK TARGET (PENERIMA PESAN)
    # +100 Poin untuk target saat menerima pesan (hanya sekali per sesi)
    if origin != "unmask":  # Unmask sudah punya sistem bonus sendiri di unmask.py
        receive_key = f"Receive_Message_{target_id}_{user.id}_{current_sess.id if current_sess else '0'}"
        bonus_exists = await db.check_bonus_exists(receive_key)
        if not bonus_exists:
            await db.add_points_with_log(target_id, 100, receive_key)
            try:
                await bot.send_message(target_id, "📩 +100 Poin (Pesan masuk!)", parse_mode="HTML")
            except:
                pass
    
    # POIN UNTUK PENGIRIM (YANG MEMBALAS)
    # +200 Poin untuk pengirim jika ini adalah balasan pertama di sesi ini
    if origin != "unmask":  # Unmask sudah punya sistem bonus sendiri di unmask.py
        reply_key = f"First_Reply_{user.id}_{target_id}_{current_sess.id if current_sess else '0'}"
        bonus_exists = await db.check_bonus_exists(reply_key)
        if not bonus_exists:
            # Cek apakah ini balasan pertama (belum ada history dari user ini ke target di sesi ini)
            history_check = await db.get_chat_history(user.id, target_id, limit=2)
            if not history_check or len(history_check) <= 2:  # Hanya pesan pertama atau kedua
                await db.add_points_with_log(user.id, 200, reply_key)
                await message.answer("🎉 +200 Poin (Bonus balas pesan!)", parse_mode="HTML")
    
    # ========== TAMPILKAN BALON PESAN DI ROOM SENDIRI ==========
    sent_bubble = await message.answer(
        f"<b>Anda:</b>\n{html.escape(message.text)}",
        parse_mode="HTML"
    )
    
    # Simpan ID pesan bubble untuk cleanup nanti
    sweep_list = data.get('sweep_list', [])
    sweep_list.append(sent_bubble.message_id)
    await state.update_data(sweep_list=sweep_list)
    
    # ========== LOG KE CHANNEL ADMIN (OPSIONAL) ==========
    if chat_sess and chat_sess.thread_id:
        try:
            admin_log = f"💬 <b>CHAT RELAY</b>\nFrom: <code>{user.id}</code> To: <code>{target_id}</code>\nMsg: {message.text[:200]}"
            await bot.send_message(os.getenv("CHAT_LOG_GROUP_ID"), admin_log, reply_to_message_id=chat_sess.thread_id)
        except:
            pass


# ==========================================
# 6. HANDLER: EXIT CHAT ROOM (CLEANUP TOTAL)
# ==========================================
@router.message(F.text == "🛑 AKHIRI OBROLAN", ChatState.in_room)
async def exit_chat_room(
    message: types.Message,
    state: FSMContext,
    db: DatabaseService,
    bot: Bot
):
    """Keluar dari ruang obrolan dan bersihkan semua pesan"""
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
# 7. HANDLER: KELUAR KE DASHBOARD SAAT DI CHAT ROOM
# ==========================================
@router.message(ChatState.in_room, F.text.in_(["🏠 Dashboard", "📱 DASHBOARD UTAMA", "/dashboard", "/start"]))
async def exit_to_dashboard_from_chat(
    message: types.Message,
    state: FSMContext,
    db: DatabaseService,
    bot: Bot
):
    """Jika user menekan menu dashboard saat di chat room, tetap bersihkan room"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    data = await state.get_data()
    sweep_list = data.get('sweep_list', [])
    header_msg_id = data.get('header_msg_id')
    instruction_msg_id = data.get('instruction_msg_id')
    
    # Cleanup semua pesan
    if header_msg_id:
        try:
            await bot.delete_message(chat_id, header_msg_id)
        except:
            pass
    if instruction_msg_id:
        try:
            await bot.delete_message(chat_id, instruction_msg_id)
        except:
            pass
    for msg_id in sweep_list:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass
    
    # Hapus ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    await state.clear()
    
    # Navigasi ke dashboard
    from handlers.start import render_dashboard_ui
    await render_dashboard_ui(bot, chat_id, user_id, db, None, force_new=True)

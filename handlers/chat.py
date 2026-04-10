import os
import html
import datetime
import logging
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InputMediaPhoto
)
from sqlalchemy import select

from services.database import DatabaseService
from services.notification import NotificationService

router = Router()

class ChatState(StatesGroup):
    in_room = State()

# ==========================================
# 1. KIRIM 50 PESAN HISTORY (SEBAGAI BUBBLE TERPISAH)
# ==========================================
async def send_history_messages(bot: Bot, chat_id: int, user_id: int, target_id: int, db: DatabaseService):
    """Kirim 50 pesan history terakhir sebagai pesan terpisah (dari tertua ke terbaru)"""
    history = await db.get_chat_history(user_id, target_id, limit=50)
    if not history:
        await bot.send_message(chat_id, "💬 <i>Belum ada percakapan. Kirim pesan pertama!</i>", parse_mode="HTML")
        return
    for entry in history:
        sender = entry.get('s', '?')
        text = entry.get('t', '')
        await bot.send_message(chat_id, f"<b>{sender}:</b>\n{html.escape(text)}", parse_mode="HTML")
        await asyncio.sleep(0.05)  # jeda kecil agar tidak flood

# ==========================================
# 2. UPDATE HEADER (INFO PROFIL & SISA WAKTU, TANPA HISTORY)
# ==========================================
async def update_chat_header(bot: Bot, user_id: int, target_id: int, db: DatabaseService):
    user = await db.get_user(user_id)
    if not user or not user.anchor_msg_id:
        return
    target = await db.get_user(target_id)
    chat_sess = await db.get_active_chat_session(user_id, target_id)
    if not target or not chat_sess:
        return

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

    if target.is_vip_plus:
        kasta = "💎 VIP+"
    elif target.is_vip:
        kasta = "🌟 VIP"
    elif target.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"

    header_caption = (
        f"💬 <b>OBROLAN: {target.full_name.upper()}</b>\n"
        f"{status_icon} Status: {kasta} | 📍 {target.location_name}\n"
        f"⏳ Sesi: {time_left}\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<i>Gunakan tombol di bawah layar untuk keluar.</i>"
    )

    try:
        await bot.edit_message_caption(
            chat_id=user_id,
            message_id=user.anchor_msg_id,
            caption=header_caption,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.warning(f"Gagal update header: {e}")

# ==========================================
# 3. START CHAT ROOM
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
    target = await db.get_user(target_id)
    chat_sess = await db.get_active_chat_session(user_id, target_id)

    if not target or not chat_sess:
        await bot.send_message(chat_id, "❌ Sesi obrolan tidak ditemukan atau sudah berakhir.")
        return

    # Cleanup
    if message_id:
        try:
            await bot.delete_message(chat_id, message_id)
        except:
            pass
    data = await state.get_data()
    old_sweep = data.get('sweep_list', [])
    for msg_id in old_sweep:
        try:
            await bot.delete_message(chat_id, msg_id)
        except:
            pass

    # Header
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

    if target.is_vip_plus:
        kasta = "💎 VIP+"
    elif target.is_vip:
        kasta = "🌟 VIP"
    elif target.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"

    header_caption = (
        f"💬 <b>OBROLAN: {target.full_name.upper()}</b>\n"
        f"{status_icon} Status: {kasta} | 📍 {target.location_name}\n"
        f"⏳ Sesi: {time_left}\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<i>Gunakan tombol di bawah layar untuk keluar.</i>"
    )

    kb_exit = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🛑 AKHIRI OBROLAN")]],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    sent_header = await bot.send_photo(
        chat_id=chat_id,
        photo=target.photo_id,
        caption=header_caption,
        parse_mode="HTML"
    )

    sent_instruction = await bot.send_message(
        chat_id,
        "✍️ <i>Ketik pesanmu di bawah. Gunakan tombol di bawah layar untuk keluar.</i>",
        reply_markup=kb_exit,
        parse_mode="HTML"
    )

    await state.update_data(
        current_target_id=target_id,
        header_msg_id=sent_header.message_id,
        instruction_msg_id=sent_instruction.message_id,
        sweep_list=[sent_header.message_id, sent_instruction.message_id]
    )

    # Kirim 50 history bubble
    await send_history_messages(bot, chat_id, user_id, target_id, db)

    # 🔥 Tandai sedang chat room
    await db.push_nav(user_id, f"chat_room_{target_id}")
    await db.update_anchor_msg(user_id, sent_header.message_id)
    await state.set_state(ChatState.in_room)

# ==========================================
# 4. HANDLER MULAI CHAT DARI CALLBACK
# ==========================================
@router.callback_query(F.data.startswith("chat_"))
async def start_chat_from_callback(
    callback: types.CallbackQuery,
    db: DatabaseService,
    bot: Bot,
    state: FSMContext
):
    parts = callback.data.split("_")
    if len(parts) >= 3:
        try:
            target_id = int(parts[1])
        except:
            await callback.answer("❌ Data tidak valid.", show_alert=True)
            return
        origin = parts[2]
    else:
        try:
            target_id = int(parts[1])
        except:
            await callback.answer("❌ Data tidak valid.", show_alert=True)
            return
        origin = "public"

    user_id = callback.from_user.id
    target = await db.get_user(target_id)
    if not target:
        await callback.answer("❌ Profil tidak ditemukan!", show_alert=True)
        return

    chat_sess = await db.get_active_chat_session(user_id, target_id)
    now_ts = int(datetime.datetime.now().timestamp())

    if not chat_sess or chat_sess.expires_at <= now_ts:
        user = await db.get_user(user_id)
        if origin in ["discovery", "public", "feed"]:
            if not (user.is_vip or user.is_vip_plus):
                await callback.answer("🔒 Fitur Kirim Pesan hanya untuk VIP/VIP+!\nUpgrade dulu ya!", show_alert=True)
                return
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
        elif origin == "unmask":
            if not chat_sess:
                await callback.answer("❌ Sesi unmask tidak ditemukan! Silakan unmask ulang.", show_alert=True)
                return
        elif origin == "match":
            expires_at = int((datetime.datetime.now() + datetime.timedelta(hours=24)).timestamp())
            await db.upsert_chat_session(user_id, target_id, expires_at, origin="match")
        elif origin == "inbox":
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

    await db.mark_notif_read(user_id, target_id, "CHAT")
    await callback.answer("⏳ Membuka ruang obrolan...")
    await start_chat_room(bot, callback.message.chat.id, user_id, target_id, db, state, callback.message.message_id)

# ==========================================
# 5. PROSES PESAN (REAL-TIME, TANPA THREADING)
# ==========================================
@router.message(ChatState.in_room, F.text != "🛑 AKHIRI OBROLAN")
async def process_chat_relay(
    message: types.Message,
    state: FSMContext,
    db: DatabaseService,
    bot: Bot
):
    data = await state.get_data()
    target_id = data.get('current_target_id')
    user = await db.get_user(message.from_user.id)
    notif_service = NotificationService(bot, db)

    if not message.text:
        return

    # Simpan history ke database
    chat_sess = await db.add_chat_history(user.id, target_id, user.full_name, message.text)

    # Kirim pesan ke target (REAL TIME)
    target_text = f"<b>{user.full_name}:</b>\n<blockquote>{html.escape(message.text)}</blockquote>"
    try:
        await bot.send_message(target_id, target_text, parse_mode="HTML")
        logging.info(f"Pesan dari {user.id} ke {target_id} terkirim")
    except Exception as e:
        logging.error(f"Gagal kirim pesan ke {target_id}: {e}")

    # ========== SISTEM POIN ==========
    current_sess = await db.get_active_chat_session(user.id, target_id)
    origin = current_sess.origin if current_sess else "public"
    session_id = current_sess.id if current_sess else None

    if origin not in ["match", "unmask"] and session_id:
        first_msg_key = f"first_msg_{session_id}"
        if not await db.check_bonus_exists(first_msg_key):
            await db.add_points_with_log(target_id, 100, first_msg_key)
            try:
                await bot.send_message(target_id, "📩 +100 Poin (Pesan masuk pertama!)", parse_mode="HTML")
            except:
                pass
        else:
            first_reply_key = f"first_reply_{session_id}"
            if not await db.check_bonus_exists(first_reply_key):
                await db.add_points_with_log(user.id, 200, first_reply_key)
                try:
                    await bot.send_message(user.id, "🎉 +200 Poin (Balasan pertama!)", parse_mode="HTML")
                except:
                    pass

    # Update header untuk kedua user (sisa waktu)
    await update_chat_header(bot, user.id, target_id, db)
    await update_chat_header(bot, target_id, user.id, db)

    # Log admin (opsional)
    admin_log_channel = os.getenv("CHAT_LOG_CHANNEL_ID")
    if admin_log_channel and chat_sess:
        try:
            admin_log = f"💬 <b>CHAT RELAY</b>\nFrom: <code>{user.id}</code> To: <code>{target_id}</code>\nMsg: {message.text[:200]}"
            await bot.send_message(admin_log_channel, admin_log, parse_mode="HTML")
        except:
            pass

# ==========================================
# 6. EXIT CHAT ROOM
# ==========================================
@router.message(F.text == "🛑 AKHIRI OBROLAN", ChatState.in_room)
async def exit_chat_room(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    data = await state.get_data()
    sweep_list = data.get('sweep_list', [])
    header_msg_id = data.get('header_msg_id')
    instruction_msg_id = data.get('instruction_msg_id')

    for msg_id in [header_msg_id, instruction_msg_id] + sweep_list:
        if msg_id:
            try:
                await bot.delete_message(chat_id, msg_id)
            except:
                pass
    try:
        await message.delete()
    except:
        pass
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass

    await db.pop_nav(user_id)
    await state.clear()
    from handlers.inbox import render_inbox_list
    await render_inbox_list(bot, chat_id, user_id, db, page=0)

# ==========================================
# 7. EXIT KE DASHBOARD
# ==========================================
@router.message(ChatState.in_room, F.text.in_(["🏠 Dashboard", "📱 DASHBOARD UTAMA", "/dashboard", "/start"]))
async def exit_to_dashboard_from_chat(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    data = await state.get_data()
    sweep_list = data.get('sweep_list', [])
    header_msg_id = data.get('header_msg_id')
    instruction_msg_id = data.get('instruction_msg_id')

    for msg_id in [header_msg_id, instruction_msg_id] + sweep_list:
        if msg_id:
            try:
                await bot.delete_message(chat_id, msg_id)
            except:
                pass
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass

    await db.pop_nav(user_id)
    await state.clear()
    from handlers.start import render_dashboard_ui
    await render_dashboard_ui(bot, chat_id, user_id, db, None, force_new=True)

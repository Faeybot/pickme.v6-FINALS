import os
import html
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto

from services.database import DatabaseService
from services.notification import NotificationService

router = Router()

class ChatState(StatesGroup):
    in_room = State()

# ==========================================
# 1. GERBANG MASUK: START CHAT ROOM
# ==========================================
async def start_chat_room(bot: Bot, chat_id: int, user_id: int, target_id: int, db: DatabaseService, state: FSMContext, message_id: int = None):
    target = await db.get_user(target_id)
    chat_sess = await db.get_active_chat_session(user_id, target_id)
    
    if not target or not chat_sess:
        return await bot.send_message(chat_id, "❌ Sesi obrolan tidak ditemukan atau sudah berakhir.")

    # Bersihkan layar SPA (Hapus Anchor Menu sebelumnya)
    try: await bot.delete_message(chat_id, message_id)
    except: pass

    # Siapkan Tampilan Riwayat (Default 5 pesan terakhir)
    history_text = render_history_text(chat_sess.chat_history, limit=5)
    
    # Header Profil Lawan Chat
    kasta = "💎 VIP+" if target.is_vip_plus else "🌟 VIP" if target.is_vip else "🎭 PREMIUM" if target.is_premium else "👤 FREE"
    header_caption = (
        f"💬 <b>RUANG OBROLAN: {target.full_name.upper()}</b>\n"
        f"👑 Status: {kasta} | 📍 {target.location_name}\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<b>[Riwayat Terakhir]</b>\n{history_text}\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"🟢 Sesi terhubung. Ketik pesanmu di bawah..."
    )

    kb_inline = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Muat Lebih Lama", callback_data=f"chat_load_{target_id}_15")],
        [InlineKeyboardButton(text="⬇️ Ke Pesan Terbaru", callback_data=f"chat_load_{target_id}_5")]
    ])

    # ReplyKeyboard untuk Tombol Exit (Bawah)
    kb_reply = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🛑 Akhiri Obrolan")]], resize_keyboard=True)

    # Kirim Header Profil sebagai Pesan Baru (Mulai Native Scrolling)
    sent = await bot.send_photo(
        chat_id=chat_id,
        photo=target.photo_id,
        caption=header_caption,
        reply_markup=kb_inline,
        parse_mode="HTML"
    )
    
    await bot.send_message(chat_id, "✍️ <i>Silakan mulai mengetik...</i>", reply_markup=kb_reply)
    
    await state.set_state(ChatState.in_room)
    await state.update_data(current_target_id=target_id, header_msg_id=sent.message_id)

# --- Helper: Merakit Teks Riwayat ---
def render_history_text(history_list, limit=5):
    if not history_list: return "<i>(Belum ada percakapan)</i>"
    
    subset = history_list[-limit:]
    lines = []
    for m in subset:
        lines.append(f"<b>{m['s']}:</b> {html.escape(m['t'])}")
    return "\n".join(lines)

# ==========================================
# 2. NAVIGASI RIWAYAT (LOAD MORE / REFRESH)
# ==========================================
@router.callback_query(F.data.startswith("chat_load_"))
async def handle_load_history(callback: types.CallbackQuery, db: DatabaseService):
    _, _, target_id, limit = callback.data.split("_")
    chat_sess = await db.get_active_chat_session(callback.from_user.id, int(target_id))
    
    new_history = render_history_text(chat_sess.chat_history, limit=int(limit))
    
    # Edit Caption Header tanpa menggulir layar
    try:
        current_caption = callback.message.caption.split("<b>[Riwayat Terakhir]</b>")[0]
        footer = callback.message.caption.split("<code>━━━━━━━━━━━━━━━━━━━━━━</code>")[-1]
        
        updated_text = f"{current_caption}<b>[Riwayat Terakhir]</b>\n{new_history}\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>{footer}"
        await callback.message.edit_caption(caption=updated_text, reply_markup=callback.message.reply_markup, parse_mode="HTML")
    except: pass
    await callback.answer()

# ==========================================
# 3. PROSES KURIR PESAN (LIVE CHAT)
# ==========================================
@router.message(ChatState.in_room, F.text != "🛑 Akhiri Obrolan")
async def process_chat_relay(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    data = await state.get_data()
    target_id = data.get('current_target_id')
    user = await db.get_user(message.from_user.id)
    notif_service = NotificationService(bot, db)

    # 1. Simpan ke History JSON
    chat_sess = await db.add_chat_history(user.id, target_id, user.full_name, message.text)
    
    # 2. Lempar ke Target (Forward)
    target_text = f"<b>{user.full_name}:</b>\n{html.escape(message.text)}"
    try:
        await bot.send_message(target_id, target_text, parse_mode="HTML")
        # Trigger notifikasi jika target tidak sedang aktif
        await notif_service.trigger_new_message(target_id, user.id, user.full_name, is_reply=True)
    except: pass

    # 3. Lempar ke Brankas Channel (Thread Admin) sesuai ide Anda
    if chat_sess and chat_sess.thread_id:
        try:
            admin_log = f"💬 <b>CHAT RELAY</b>\nFrom: <code>{user.id}</code> To: <code>{target_id}</code>\nMsg: {message.text}"
            await bot.send_message(os.getenv("CHAT_LOG_GROUP_ID"), admin_log, reply_to_message_id=chat_sess.thread_id)
        except: pass

# ==========================================
# 4. PINTU KELUAR: EXIT & CLEANUP
# ==========================================
@router.message(F.text == "🛑 Akhiri Obrolan", ChatState.in_room)
async def exit_chat_room(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    # Hapus ReplyKeyboard
    temp = await message.answer("🔄 <i>Menutup obrolan...</i>", reply_markup=ReplyKeyboardRemove())
    await bot.delete_message(message.chat.id, temp.message_id)
    
    await state.clear()
    
    # Bangkitkan kembali SPA (Panggil menu Inbox/Dashboard)
    from handlers.inbox import render_inbox_ui
    await render_inbox_ui(bot, message.chat.id, message.from_user.id, db)

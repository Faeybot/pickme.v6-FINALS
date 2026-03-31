import os
import html
import datetime
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")

# ==========================================
# CORE UI RENDERER: INBOX LIST
# ==========================================
async def render_inbox_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None, message_id: int = None):
    user = await db.get_user(user_id)
    if not user: return False

    sessions = await db.get_inbox_sessions(user_id)
    text_content = "<b>📥 INBOX PESAN & HISTORI</b>\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
    kb_buttons = []

    if not sessions:
        text_content += "<i>Belum ada riwayat percakapan. Mulai sapa seseorang di Discovery atau Feed!</i>"
    else:
        now = int(datetime.datetime.now().timestamp())
        
        for i, sess in enumerate(sessions, 1):
            counterpart_id = sess.target_id if sess.user_id == user_id else sess.user_id
            counterpart = await db.get_user(counterpart_id)
            if not counterpart: continue
            
            name = counterpart.full_name
            is_active = sess.expires_at > now
            
            # Label Origin & Poin
            origin = getattr(sess, 'origin', 'public')
            if origin == "unmask":
                jalur_info = "[Jalur VIP+] 🎁 +500 Poin"
            elif origin == "match":
                jalur_info = "[Jalur Match] 🆓 Gratis"
            else:
                jalur_info = "[Jalur Publik] 🎁 +200 Poin"
            
            snippet = sess.last_message[:25] + "..." if sess.last_message else "Belum ada pesan."
            snippet = html.escape(snippet)
            
            if is_active:
                exp_date = datetime.datetime.fromtimestamp(sess.expires_at).strftime("%d/%m %H:%M")
                text_content += f"{i}. 🟢 <b>{name}</b> (Aktif s/d {exp_date})\n🏷 <i>{jalur_info}</i>\n💬 <i>\"{snippet}\"</i>\n\n"
                kb_buttons.append([InlineKeyboardButton(text=f"💬 Buka Obrolan dgn {name}", callback_data=f"chat_{counterpart_id}_inbox")])
            else:
                text_content += f"{i}. 🔴 <b>{name}</b> (Sesi Habis)\n🏷 <i>{jalur_info}</i>\n💬 <i>\"{snippet}\"</i>\n\n"
                kb_buttons.append([InlineKeyboardButton(text=f"🔒 Buka Kembali dgn {name}", callback_data=f"chat_{counterpart_id}_extend")])
                
        text_content += "<i>Pesan dengan tanda 🔴 membutuhkan 1 Kuota Pesan untuk dibuka kembali selama 24 Jam.</i>"

    # Tombol Jalan Keluar
    kb_buttons.append([InlineKeyboardButton(text="⬅️ Kembali ke Notifikasi", callback_data="menu_notifications")])
    kb_nav = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text_content, parse_mode="HTML")

    if message_id:
        try: await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=kb_nav)
        except Exception: pass
    else:
        try:
            if user.anchor_msg_id:
                try: await bot.delete_message(chat_id=chat_id, message_id=user.anchor_msg_id)
                except: pass
            sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_content, reply_markup=kb_nav, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
        except: pass

    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
    return True

# --- HANDLER PENANGKAP SINYAL DARI HUB DASHBOARD ---
@router.callback_query(F.data == "notif_inbox")
async def show_inbox(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_inbox_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id, callback.message.message_id)

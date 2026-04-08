import os
import html
import logging
import re
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove
from services.database import DatabaseService, User
from utils.filters import is_content_safe  # opsional

router = Router()

# ==========================================
# 1. KONFIGURASI DARI ENVIRONMENT VARIABLES
# ==========================================
def get_int_id(key: str):
    val = os.getenv(key)
    if val is None:
        return None
    val = val.strip()
    try:
        return int(val)
    except ValueError:
        return None

FEED_CHANNEL_ID = get_int_id("FEED_CHANNEL_ID")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "")
ADMIN_FEED_GROUP_ID = get_int_id("ADMIN_FEED_GROUP_ID")
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")

class FeedState(StatesGroup):
    waiting_text = State()
    waiting_photo = State()
    waiting_anon_choice = State()

INTEREST_MAP = {
    "int_adult": "#Adult🔞", "int_flirt": "#FlirtAndTalk🔥", "int_rel": "#Relationship❤️",
    "int_net": "#Networking🤝", "int_game": "#Gaming🎮", "int_travel": "#Traveling✈️", "int_coffee": "#Coffee☕"
}

# ==========================================
# 2. FORMATTER POSTINGAN
# ==========================================
def format_feed_post(user: User, caption: str, is_anon: bool, bot_username: str):
    name_header = "🎭 <b>ANONIM</b>" if is_anon else f"👤 <b>{user.full_name.upper()}</b>"
    origin_flag = "anon" if is_anon else "public"
    link_profile = f"https://t.me/{bot_username}?start=view_{user.id}_{origin_flag}"
    
    header = f"{name_header} | <a href=\"{link_profile}\">[Lihat Profil]</a>"
    content = f"<blockquote><code><i>{html.escape(caption)}</i></code></blockquote>"
    
    city_name = user.location_name.replace(' ', '').title() if user.location_name else "Unknown"
    gender_name = user.gender.title() if user.gender else "Rahasia"
    
    interest_hashtags = [INTEREST_MAP.get(item.strip()) for item in (user.interests or "").split(",") if INTEREST_MAP.get(item.strip())]
    hashtags = f"📍 #{city_name} #{gender_name}\n🔥 {' '.join(interest_hashtags) if interest_hashtags else ''}"
    
    return f"{header}\n<code>{'—' * 20}</code>\n{content}\n\n{hashtags}"

# ==========================================
# 3. CORE UI RENDERER: FEED MENU
# ==========================================
async def render_feed_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None):
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    if state:
        await state.clear()
    
    user = await db.get_user(user_id)
    if not user:
        return False
    
    await db.push_nav(user_id, "feed")
    
    text = (
        "📸 <b>MENU FEED & POSTING</b>\n"
        f"<code>{'—' * 20}</code>\n"
        "<i>Postingan teks akan terbit <b>OTOMATIS</b>.\nPostingan foto akan ditinjau <b>MANUAL</b> oleh Admin.</i>\n\n"
        f"📑 <b>Sisa Kuota Harian:</b>\n"
        f"📝 Teks: <b>{user.daily_feed_text_quota}</b> | 📸 Foto: <b>{user.daily_feed_photo_quota}</b>\n\n"
        f"📦 <b>Sisa Kuota Extra (Premium/Talent):</b>\n"
        f"📝 Teks: <b>{user.extra_feed_text_quota}</b> | 📸 Foto: <b>{user.extra_feed_photo_quota}</b>\n"
        f"<code>{'—' * 20}</code>\n"
        f"<i>Tips: Upgrade Tier untuk mendapatkan jatah posting harian lebih banyak!</i>"
    )
    
    ch_user = CHANNEL_USERNAME.replace('@', '').strip() if CHANNEL_USERNAME else ""
    preview_button = [InlineKeyboardButton(text="📺 PREVIEW CHANNEL", url=f"https://t.me/{ch_user}")] if ch_user else []
    
    kb_buttons = [
        [InlineKeyboardButton(text="📝 TULIS TEKS", callback_data="feed_ask_text"),
         InlineKeyboardButton(text="📸 POSTING FOTO", callback_data="feed_ask_photo")],
        [InlineKeyboardButton(text="🚀 BOOSTER POSTINGAN", callback_data="menu_boost")]
    ]
    if preview_button:
        kb_buttons.append(preview_button)
    kb_buttons.append([InlineKeyboardButton(text="⬅️ Kembali ke Dashboard", callback_data="back_to_dashboard")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    if callback_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
            await bot.answer_callback_query(callback_id)
            return
        except Exception as e:
            logging.warning(f"Edit feed UI gagal: {e}")
            if user.anchor_msg_id:
                try:
                    await bot.delete_message(chat_id, user.anchor_msg_id)
                except:
                    pass
                await db.update_anchor_msg(user_id, None)
    
    sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
    await db.update_anchor_msg(user_id, sent.message_id)
    return True

@router.callback_query(F.data == "menu_feed")
async def show_feed_menu(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    await render_feed_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)

@router.callback_query(F.data == "feed_cancel_action")
async def cancel_feed_action(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    await render_feed_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)

# ==========================================
# 4. HANDLER INPUT TEKS & FOTO
# ==========================================
@router.callback_query(F.data == "feed_ask_text")
async def feed_ask_text(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService):
    user = await db.get_user(callback.from_user.id)
    if user.daily_feed_text_quota <= 0 and user.extra_feed_text_quota <= 0:
        return await callback.answer("❌ Kuota Teks Anda habis! Tunggu reset besok.", show_alert=True)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Batal", callback_data="feed_cancel_action")]])
    await callback.message.edit_caption(
        caption="📝 <b>Silakan ketik pesan/status yang ingin kamu posting:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(FeedState.waiting_text)
    await callback.answer()

@router.message(FeedState.waiting_text)
async def handle_text_input(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    try:
        await message.delete()
    except:
        pass
    
    if not message.text:
        return
    
    user = await db.get_user(message.from_user.id)
    if user.daily_feed_text_quota <= 0 and user.extra_feed_text_quota <= 0:
        return
    
    # if not is_content_safe(message.text):
    #     await message.answer("❌ Konten mengandung kata terlarang. Posting dibatalkan.")
    #     await state.clear()
    #     return
    
    await state.update_data(f_type="text", f_caption=message.text)
    await ask_anon_choice(user, state, bot, message.chat.id)

@router.callback_query(F.data == "feed_ask_photo")
async def feed_ask_photo(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService):
    user = await db.get_user(callback.from_user.id)
    if user.daily_feed_photo_quota <= 0 and user.extra_feed_photo_quota <= 0:
        return await callback.answer("❌ Kuota Foto Anda habis! Tunggu reset besok.", show_alert=True)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Batal", callback_data="feed_cancel_action")]])
    await callback.message.edit_caption(
        caption="📸 <b>Kirim Foto berserta caption/keterangannya:</b>\n\n<i>Kirim foto (bisa dengan caption) – foto akan masuk antrian moderator.</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(FeedState.waiting_photo)
    await callback.answer()

@router.message(FeedState.waiting_photo, F.photo)
async def handle_photo_input(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    try:
        await message.delete()
    except:
        pass
    
    user = await db.get_user(message.from_user.id)
    if user.daily_feed_photo_quota <= 0 and user.extra_feed_photo_quota <= 0:
        await message.answer("❌ Kuota Foto habis. Tunggu reset besok.")
        await state.clear()
        return
    
    caption_text = message.caption or ""
    await state.update_data(f_type="photo", f_file_id=message.photo[-1].file_id, f_caption=caption_text)
    await ask_anon_choice(user, state, bot, message.chat.id)

@router.message(FeedState.waiting_photo)
async def handle_non_photo_input(message: types.Message, state: FSMContext):
    if message.document and message.document.mime_type.startswith('image/'):
        await message.answer("❌ Kirim sebagai FOTO (bukan file). Silakan pilih 'Kirim sebagai Foto' dari galeri.")
    else:
        await message.answer("❌ Harap kirim FOTO, bukan teks atau file lain.")
    await state.clear()

# ==========================================
# 5. PEMILIHAN ANONIM & EKSEKUSI
# ==========================================
async def ask_anon_choice(user: User, state: FSMContext, bot: Bot, chat_id: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 PUBLIK", callback_data="anon_no"),
         InlineKeyboardButton(text="🎭 ANONIM", callback_data="anon_yes")],
        [InlineKeyboardButton(text="❌ Batal", callback_data="feed_cancel_action")]
    ])
    text = "Bagaimana postingan ini ingin ditampilkan di Channel?"
    try:
        await bot.edit_message_caption(chat_id=chat_id, message_id=user.anchor_msg_id, caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        pass
    await state.set_state(FeedState.waiting_anon_choice)

@router.callback_query(F.data.in_(["anon_yes", "anon_no"]), FeedState.waiting_anon_choice)
async def process_publish(callback: types.CallbackQuery, state: FSMContext, db: DatabaseService, bot: Bot):
    is_anon = (callback.data == "anon_yes")
    data = await state.get_data()
    user_id = callback.from_user.id
    caption = data.get('f_caption', "").strip()
    post_type = data.get('f_type')
    bot_info = await bot.get_me()
    
    if post_type == "text" and not caption:
        await callback.answer("❌ Caption tidak boleh kosong!", show_alert=True)
        return
    
    # if not is_content_safe(caption):
    #     await callback.answer("❌ Caption mengandung kata terlarang!", show_alert=True)
    #     return
    
    async with db.session_factory() as session:
        user = await session.get(User, user_id)
        used_quota_type = ""
        
        if post_type == "text":
            if user.daily_feed_text_quota > 0:
                user.daily_feed_text_quota -= 1
                used_quota_type = "daily_text"
            else:
                user.extra_feed_text_quota -= 1
                used_quota_type = "extra_text"
        else:
            if user.daily_feed_photo_quota > 0:
                user.daily_feed_photo_quota -= 1
                used_quota_type = "daily_photo"
            else:
                user.extra_feed_photo_quota -= 1
                used_quota_type = "extra_photo"
        await session.commit()
        
        kb_done = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Menu Feed", callback_data="menu_feed")]])
        
        if post_type == "text":
            full_post = format_feed_post(user, caption, is_anon, bot_info.username)
            if FEED_CHANNEL_ID:
                await bot.send_message(FEED_CHANNEL_ID, full_post, parse_mode="HTML", disable_web_page_preview=True)
            else:
                logging.error("FEED_CHANNEL_ID tidak diset")
                await callback.message.edit_caption("❌ Gagal mempublikasikan. Hubungi admin.", reply_markup=kb_done)
                await state.clear()
                return
            await callback.message.edit_caption("✅ <b>Postingan teks berhasil diterbitkan!</b>", reply_markup=kb_done, parse_mode="HTML")
            await state.clear()
        else:
            if not caption:
                caption = "(Tidak ada caption)"
            anon_tag = "1" if is_anon else "0"
            admin_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ TERBITKAN", callback_data=f"apv_f_{user_id}_{anon_tag}"),
                InlineKeyboardButton(text="❌ TOLAK", callback_data=f"rej_f_{user_id}_{used_quota_type}")
            ]])
            admin_text = (
                f"📸 <b>REVIEW FOTO FEED</b>\n"
                f"👤 Pembuat: {user.full_name}\n"
                f"🎭 Tampil: <b>{'ANON' if is_anon else 'PUBLIK'}</b>\n"
                f"📝 Caption:\n{html.escape(caption)}"
            )
            try:
                if not ADMIN_FEED_GROUP_ID:
                    raise ValueError("ADMIN_FEED_GROUP_ID tidak diset")
                await bot.send_photo(ADMIN_FEED_GROUP_ID, photo=data['f_file_id'], caption=admin_text, reply_markup=admin_kb, parse_mode="HTML")
                await callback.message.edit_caption(
                    "⏳ <b>Postingan foto sedang dalam tinjauan Admin.</b>\nJika ditolak, kuota akan dikembalikan.",
                    reply_markup=kb_done,
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Gagal kirim ke admin group: {e}")
                if used_quota_type == "daily_photo":
                    user.daily_feed_photo_quota += 1
                elif used_quota_type == "extra_photo":
                    user.extra_feed_photo_quota += 1
                await session.commit()
                await callback.message.edit_caption(
                    f"❌ Gagal mengirim foto ke moderator. Error: {str(e)}",
                    reply_markup=kb_done,
                    parse_mode="HTML"
                )
            finally:
                await state.clear()
    await callback.answer()

# ==========================================
# 6. MODERASI ADMIN (APPROVE / REJECT)
# ==========================================
@router.callback_query(F.data.startswith("apv_f_"))
async def handle_approve_feed(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    parts = callback.data.split("_")
    if len(parts) < 3:
        return await callback.answer("Data tidak valid.")
    user_id = int(parts[2])
    is_anon = (parts[3] == "1") if len(parts) > 3 else False
    
    user = await db.get_user(user_id)
    if not user:
        return await callback.answer("❌ User tidak ditemukan.")
    
    # === EKSTRAKSI CAPTION YANG LEBIH ROBUST ===
    original_caption = ""
    # Cari baris yang mengandung "📝 Caption:"
    for line in callback.message.caption.split('\n'):
        if '📝 Caption:' in line:
            # Ambil teks setelah marker
            raw = line.split('📝 Caption:', 1)[1].strip()
            original_caption = raw
            break
    # Fallback dengan regex
    if not original_caption:
        match = re.search(r"📝 Caption:\s*(.*?)(?:\n|$)", callback.message.caption)
        if match:
            original_caption = match.group(1).strip()
    if not original_caption:
        original_caption = "(Tidak ada caption)"
    
    logging.info(f"DEBUG: Caption yang diekstrak = '{original_caption}'")
    
    bot_info = await bot.get_me()
    full_post = format_feed_post(user, original_caption, is_anon, bot_info.username)
    
    if FEED_CHANNEL_ID:
        await bot.send_photo(FEED_CHANNEL_ID, photo=callback.message.photo[-1].file_id, caption=full_post, parse_mode="HTML")
    else:
        logging.error("FEED_CHANNEL_ID tidak diset")
    
    try:
        await bot.send_message(user_id, "🎉 <b>POSTINGAN FOTO TERBIT!</b> Foto kamu telah disetujui admin.", parse_mode="HTML")
    except:
        pass
    
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n✅ <b>APPROVED</b>", reply_markup=None)
    await callback.answer("Postingan disetujui.")

@router.callback_query(F.data.startswith("rej_f_"))
async def handle_reject_feed(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    parts = callback.data.split("_")
    if len(parts) < 3:
        return await callback.answer("Data tidak valid.")
    user_id = int(parts[2])
    quota_info = parts[3] if len(parts) > 3 else "daily_photo"
    
    async with db.session_factory() as session:
        u = await session.get(User, user_id)
        if u:
            if quota_info == "daily_photo":
                u.daily_feed_photo_quota += 1
            elif quota_info == "extra_photo":
                u.extra_feed_photo_quota += 1
            await session.commit()
    
    try:
        await bot.send_message(user_id, "❌ <b>POSTINGAN DITOLAK.</b>\nFoto kamu tidak memenuhi panduan komunitas. Kuota foto telah dikembalikan.", parse_mode="HTML")
    except:
        pass
    
    await callback.message.edit_caption(caption=f"{callback.message.caption}\n\n🔴 <b>REJECTED & REFUNDED</b>", reply_markup=None)
    await callback.answer("Ditolak & Refund Sukses.")

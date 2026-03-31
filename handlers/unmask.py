import os
import math
import datetime
import html
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")
ITEMS_PER_PAGE = 5

# ==========================================
# HELPER: FORMATTER WAKTU
# ==========================================
def get_time_left(expires_at: int) -> str:
    if not expires_at: return "Habis"
    now = int(datetime.datetime.now().timestamp())
    if expires_at <= now: return "Habis"
    
    diff = expires_at - now
    hours = diff // 3600
    minutes = (diff % 3600) // 60
    
    if hours > 0: return f"{hours}j {minutes}m"
    return f"{minutes}m"

# ==========================================
# 1. CORE UI RENDERER: DAFTAR UNMASK
# ==========================================
async def render_unmask_list(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, page: int = 0, message_id: int = None):
    # Mengambil daftar VIP+ yang melakukan UNMASK ke user ini
    unmaskers = await db.get_interaction_list(user_id, "UNMASK_CHAT", limit=50)
    
    text_content = "🔓 <b>DAFTAR BONGKAR ANONIM (SULTAN VIP+)</b>\n<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n\n"
    
    if not unmaskers:
        text_content += "<i>Belum ada Sultan VIP+ yang membongkar identitas anonimmu dari Feed.</i>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Notifikasi", callback_data="menu_notifications")]])
    else:
        total_pages = math.ceil(len(unmaskers) / ITEMS_PER_PAGE)
        start_idx = page * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        current_unmaskers = unmaskers[start_idx:end_idx]
        
        text_content += f"Ada <b>{len(unmaskers)}</b> Sultan VIP+ yang sangat tertarik dengan postinganmu hingga rela membayar untuk membongkar profilmu!\n<i>Pilih profil untuk melihat detail:</i>\n"
        
        kb_buttons = []
        now = int(datetime.datetime.now().timestamp())
        
        for person in current_unmaskers:
            # Cek sesi chat aktif
            session_data = await db.get_active_chat_session(person.id, user_id)
            expires_at = session_data.expires_at if session_data else 0
            
            time_str = get_time_left(expires_at)
            is_active = expires_at > now
            status_icon = "🟢" if is_active else "🔴"
            
            name_short = person.full_name[:10]
            city_short = person.location_name[:10] if person.location_name else "Unknown"
            
            btn_text = f"{status_icon} {name_short}, {person.age}th, {city_short} ({time_str})"
            kb_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"unm_v_{person.id}_{page}")])
                
        # Navigasi Paginasi
        nav_row = []
        if page > 0: nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"unm_p_{page-1}"))
        if page < total_pages - 1: nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"unm_p_{page+1}"))
        if nav_row: kb_buttons.append(nav_row)
            
        kb_buttons.append([InlineKeyboardButton(text="⬅️ Kembali ke Notifikasi", callback_data="menu_notifications")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text_content, parse_mode="HTML")
    
    if message_id:
        try: await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=kb)
        except Exception: pass
    else:
        await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text_content, reply_markup=kb, parse_mode="HTML")

# --- HANDLER NAVIGASI UNMASK LIST ---
@router.callback_query(F.data == "notif_unmask")
async def handle_open_unmask(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await db.push_nav(callback.from_user.id, "unmask")
    await render_unmask_list(bot, callback.message.chat.id, callback.from_user.id, db, page=0, message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("unm_p_"))
async def handle_unmask_pagination(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    page = int(callback.data.split("_")[2])
    await render_unmask_list(bot, callback.message.chat.id, callback.from_user.id, db, page=page, message_id=callback.message.message_id)
    await callback.answer()


# ==========================================
# 2. TAMPILAN PROFIL SULTAN & REWARD INFO
# ==========================================
@router.callback_query(F.data.startswith("unm_v_"))
async def view_unmasker_profile(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    target_id = int(callback.data.split("_")[2]) # ID Sultan VIP+
    page = int(callback.data.split("_")[3])
    user_id = callback.from_user.id
    
    target = await db.get_user(target_id)
    if not target: return await callback.answer("Profil Sultan tidak ditemukan.", show_alert=True)
    
    # Cek durasi chat
    session_data = await db.get_active_chat_session(target_id, user_id)
    expires_at = session_data.expires_at if session_data else 0
    now = int(datetime.datetime.now().timestamp())
    is_active = expires_at > now
    
    minat = target.interests.replace(",", ", ") if target.interests else "-"
    target_loc = html.escape(target.location_name) if target.location_name else "-"
    target_bio = html.escape(target.bio) if target.bio else "-"

    text_full = (
        f"👑 <b>SULTAN VIP+ MENGINCARMU!</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👤 <b>{target.full_name.upper()}, {target.age} Tahun</b>\n"
        f"📍 <b>Kota:</b> {target_loc}\n"
        f"🔥 <b>Minat:</b> {minat}\n"
        f"📝 <b>Bio:</b>\n<i>{target_bio}</i>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"🎁 <b>INFO BONUS:</b>\n"
        f"Setiap member yang Unmask profilmu, kamu mendapat <b>500 poin</b>.\n"
        f"Buka, balas, dan Kirim pesan ke VIP+ ini untuk klaim extra bonus poin <b>+500</b>!"
    )

    kb_buttons = []
    
    if is_active:
        time_str = get_time_left(expires_at)
        text_full += f"\n\n⏳ <i>Sesi chat gratis terbuka ({time_str} tersisa).</i>"
        kb_buttons.append([InlineKeyboardButton(text="💬 BALAS / KIRIM PESAN", callback_data=f"unm_go_{target_id}")])
    else:
        text_full += f"\n\n🔴 <i>Sesi obrolan 48 jam telah berakhir. Butuh 1 Kuota Pesan untuk membukanya kembali.</i>"
        kb_buttons.append([InlineKeyboardButton(text="🔒 Buka Kembali Obrolan (1 Kuota)", callback_data=f"unm_xt_{target_id}_{page}")])
        
    kb_buttons.append([InlineKeyboardButton(text="⬅️ Kembali ke Daftar", callback_data=f"unm_p_{page}")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    
    media = InputMediaPhoto(media=target.photo_id, caption=text_full, parse_mode="HTML")
    try: await callback.message.edit_media(media=media, reply_markup=kb)
    except: pass
    
    # Tandai notifikasi sebagai sudah dibaca
    await db.mark_notif_read(user_id, target_id, "UNMASK_CHAT")
    await callback.answer()


# ==========================================
# 3. LOGIKA KLAIM POIN & ROUTING KE CHAT.PY
# ==========================================
@router.callback_query(F.data.startswith("unm_go_"))
async def execute_unmask_chat(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    session_data = await db.get_active_chat_session(target_id, user_id)
    if not session_data or session_data.expires_at <= int(datetime.datetime.now().timestamp()):
        return await callback.answer("⏳ Waktu obrolan sudah habis! Silakan perpanjang sesi.", show_alert=True)
    
    # 💰 DISTRIBUSI EXTRA BONUS +500 POIN (Tahap 2)
    log_key = f"UnmaskReplyBonus_{target_id}_{user_id}" 
    bonus_exists = await db.check_bonus_exists(log_key)
    if not bonus_exists:
        sukses = await db.add_points_with_log(user_id, 500, log_key)
        if sukses:
            try: await callback.message.answer("🎉 <b>BONUS KLAIM BERHASIL!</b>\nKamu mendapatkan <b>+500 Poin Extra</b> karena berinisiatif membalas Sultan.", parse_mode="HTML")
            except: pass
            
    await callback.answer("Memasuki ruang obrolan...", show_alert=False)
    
    # 🚀 HANDOFF KE CHAT.PY
    from handlers.chat import start_chat_room
    await start_chat_room(bot, callback.message.chat.id, user_id, target_id, db, state, callback.message.message_id)


# ==========================================
# 4. LOGIKA PERPANJANGAN SESI (EXTEND)
# ==========================================
@router.callback_query(F.data.startswith("unm_xt_"))
async def prompt_extend_unmask(callback: types.CallbackQuery, db: DatabaseService):
    parts = callback.data.split("_")
    target_id = int(parts[2])
    page = int(parts[3])
    
    target = await db.get_user(target_id)
    if not target: return await callback.answer("User tidak ditemukan.", show_alert=True)
    
    text = (
        f"🔴 <b>SESI BERAKHIR</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"Sesi obrolan dengan Sultan <b>{target.full_name}</b> telah habis.\n\n"
        f"Kamu membutuhkan <b>1 Kuota Kirim Pesan (DM)</b> untuk membuka kembali ruang obrolan ini selama 24 Jam ke depan.\n\n"
        f"<i>Lanjutkan perpanjang?</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ YA, PERPANJANG", callback_data=f"unm_ok_{target_id}")],
        [InlineKeyboardButton(text="❌ BATAL", callback_data=f"unm_p_{page}")]
    ])
    
    try: await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except: pass
    await callback.answer()

@router.callback_query(F.data.startswith("unm_ok_"))
async def confirm_extend_unmask(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    success = await db.use_message_quota(user_id)
    if not success:
        return await callback.answer("❌ Kuota DM (Kirim Pesan) Anda habis! Silakan Topup/Upgrade.", show_alert=True)
        
    expiry_24h = int((datetime.datetime.now() + datetime.timedelta(hours=24)).timestamp())
    await db.upsert_chat_session(user_id, target_id, expires_at=expiry_24h)
    
    await callback.answer("✅ Sesi diperpanjang 24 Jam!", show_alert=True)
    
    # 🚀 HANDOFF KE CHAT.PY
    from handlers.chat import start_chat_room
    await start_chat_room(bot, callback.message.chat.id, user_id, target_id, db, state, callback.message.message_id)

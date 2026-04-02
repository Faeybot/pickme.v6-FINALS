import os
import html
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, update
from services.database import DatabaseService, User, PointLog

router = Router()


# ==========================================
# 0. KONFIGURASI ID & HAK AKSES ADMIN
# ==========================================
def get_int_id(key: str, default=0):
    val = os.getenv(key)
    if not val:
        return default
    val = str(val).strip().replace("'", "").replace('"', '')
    if val.startswith("-") or val.isdigit():
        try:
            return int(val)
        except:
            return val
    return default


def get_list_ids(key: str):
    val = os.getenv(key, "")
    return [int(x) for x in val.split(",") if x.strip().lstrip('-').isdigit()]


# ID Publik, Log & Grup Approval
FEED_CHANNEL_ID = get_int_id("FEED_CHANNEL_ID")
FINANCE_CHANNEL_ID = get_int_id("FINANCE_CHANNEL_ID")
FINANCE_GROUP_ID = get_int_id("FINANCE_GROUP_ID")

# Hak Akses
OWNER_ID = get_int_id("OWNER_ID")
ADMIN_FINANCE_IDS = get_list_ids("ADMIN_FINANCE_IDS")
ADMIN_MODERATOR_IDS = get_list_ids("ADMIN_MODERATOR_IDS")

ALL_FINANCE_ADMINS = [OWNER_ID] + ADMIN_FINANCE_IDS
ALL_MODERATORS = [OWNER_ID] + ADMIN_MODERATOR_IDS
ALL_ADMINS = list(set([OWNER_ID] + ADMIN_FINANCE_IDS + ADMIN_MODERATOR_IDS))


class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in ALL_ADMINS


class ChatAdminState(StatesGroup):
    waiting_admin_msg = State()
    waiting_for_broadcast = State()


# ==========================================
# 1. DIVISI KEUANGAN (WD & TRIAL APPROVAL)
# ==========================================

@router.callback_query(F.data.startswith("wd_confirm_"))
async def admin_confirm_wd(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    if callback.from_user.id not in ALL_FINANCE_ADMINS:
        return await callback.answer("🚫 Akses Ditolak!", show_alert=True)
    
    parts = callback.data.split("_")
    user_id = int(parts[2])
    trx_id = parts[3]
    
    async with db.session_factory() as session:
        user = await session.get(User, user_id)
        if user:
            user.has_withdrawn_before = True
        await session.commit()
    
    old_text = callback.message.text
    new_text = f"{old_text}\n\n✅ <b>LUNAS (DITRANSFER)</b>\nOleh: {callback.from_user.first_name}"
    await callback.message.edit_text(new_text, reply_markup=None, parse_mode="HTML")
    
    if FINANCE_CHANNEL_ID:
        log_text = (
            f"🧾 <b>LAPORAN KAS KELUAR (WD)</b>\n"
            f"ID TRX: <code>{trx_id}</code>\n"
            f"Penerima: <code>{user_id}</code>\n"
            f"Status: ✅ SUKSES DITRANSFER"
        )
        try:
            await bot.send_message(FINANCE_CHANNEL_ID, log_text, parse_mode="HTML")
        except:
            pass
    
    try:
        await bot.send_message(user_id, "🎊 <b>WITHDRAW BERHASIL!</b>\nDana telah dikirim ke rekening/e-wallet Anda. Silakan cek saldo!", parse_mode="HTML")
    except:
        pass
    await callback.answer("Withdraw Selesai!")


@router.callback_query(F.data.startswith("trial_apv_"))
async def admin_approve_trial_jackpot(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    if callback.from_user.id not in ALL_FINANCE_ADMINS:
        return await callback.answer("🚫 Akses Ditolak!", show_alert=True)
    
    parts = callback.data.split("_")
    user_id = int(parts[2])
    package_type = parts[3] if len(parts) > 3 else "vipplus"
    
    expiry_date = datetime.now() + timedelta(days=7)
    
    async with db.session_factory() as session:
        user = await session.get(User, user_id)
        if not user:
            return await callback.answer("User tidak ditemukan")
        
        if package_type == "premium":
            user.is_premium = True
            user.is_vip = False
            user.is_vip_plus = False
            user.daily_feed_text_quota = 3
            user.daily_feed_photo_quota = 1
            user.daily_message_quota = 0
            user.daily_open_profile_quota = 0
            user.daily_unmask_quota = 0
            user.daily_swipe_quota = 20
        elif package_type == "vip":
            user.is_premium = False
            user.is_vip = True
            user.is_vip_plus = False
            user.vip_expires_at = expiry_date
            user.daily_feed_text_quota = 10
            user.daily_feed_photo_quota = 5
            user.daily_message_quota = 10
            user.daily_open_profile_quota = 10
            user.daily_unmask_quota = 0
            user.daily_swipe_quota = 30
        else:  # vipplus
            user.is_premium = False
            user.is_vip = False
            user.is_vip_plus = True
            user.vip_expires_at = expiry_date
            user.daily_feed_text_quota = 10
            user.daily_feed_photo_quota = 5
            user.daily_message_quota = 10
            user.daily_open_profile_quota = 10
            user.daily_unmask_quota = 10
            user.daily_swipe_quota = 50
        
        await session.commit()
    
    old_text = callback.message.text
    await callback.message.edit_text(f"{old_text}\n\n✅ <b>{package_type.upper()} AKTIF (7 HARI)</b>\nApproved by: {callback.from_user.first_name}", reply_markup=None)
    
    if FINANCE_CHANNEL_ID:
        log_trial = (
            f"🎁 <b>LOG TRIAL</b>\n"
            f"User ID: <code>{user_id}</code>\n"
            f"Paket: {package_type.upper()}\n"
            f"Durasi: 7 Hari"
        )
        try:
            await bot.send_message(FINANCE_CHANNEL_ID, log_trial, parse_mode="HTML")
        except:
            pass
    
    msg_user = (
        f"🎉 <b>SELAMAT! PENGAJUAN DISETUJUI</b>\n\n"
        f"Akunmu telah ditingkatkan menjadi <b>{package_type.upper()}</b> selama <b>7 hari masa trial</b>.\n\n"
        f"Nikmati fitur eksklusifnya sekarang juga!"
    )
    try:
        await bot.send_message(user_id, msg_user, parse_mode="HTML")
    except:
        pass
    await callback.answer(f"Trial {package_type.upper()} Aktif!")


@router.callback_query(F.data.startswith("trial_rej_"))
async def admin_reject_trial(callback: types.CallbackQuery, bot: Bot):
    user_id = int(callback.data.split("_")[2])
    await callback.message.edit_text(f"{callback.message.text}\n\n❌ <b>DITOLAK</b>", reply_markup=None)
    try:
        await bot.send_message(user_id, "❌ <b>PENGAJUAN DITOLAK</b>\nMaaf, permintaan trial Anda belum dapat disetujui saat ini.", parse_mode="HTML")
    except:
        pass
    await callback.answer("Ditolak.")


# ==========================================
# 2. DIVISI MODERASI (FEED)
# ==========================================
@router.callback_query(F.data.startswith("apv_f_"))
async def admin_approve_feed(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    if callback.from_user.id not in ALL_MODERATORS:
        return await callback.answer("🚫 Moderator Only!", show_alert=True)
    
    parts = callback.data.split("_")
    target_id = int(parts[2])
    is_anon = parts[3] == "1"
    
    user = await db.get_user(target_id)
    bot_info = await bot.get_me()
    
    raw_caption = callback.message.caption or ""
    original_caption = raw_caption.split("Caption:")[1].strip() if "Caption:" in raw_caption else ""
    
    name_header = "🎭 <b>ANONIM</b>" if is_anon else f"👤 <b>{user.full_name.upper()}</b>"
    link_profile = f"https://t.me/{bot_info.username}?start=view_{user.id}"
    
    city_tag = f"#{user.location_name.replace(' ', '').title()}" if user.location_name else "#Indonesia"
    gender_tag = f"#{user.gender.title()}" if user.gender else ""
    
    final_post = (
        f"{name_header} | <a href='{link_profile}'>VIEW PROFILE</a>\n"
        f"<code>{'—' * 20}</code>\n"
        f"<blockquote><i>{html.escape(original_caption)}</i></blockquote>\n\n"
        f"📍 {city_tag} {gender_tag}"
    )
    
    try:
        await bot.send_photo(FEED_CHANNEL_ID, photo=callback.message.photo[-1].file_id, caption=final_post, parse_mode="HTML")
        await callback.message.edit_caption(caption=f"{raw_caption}\n\n✅ <b>APPROVED</b>", reply_markup=None)
        await bot.send_message(target_id, "🎉 <b>POSTINGAN DITERIMA!</b>\nFoto Anda telah tayang di Channel Feed.", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error Feed: {e}")
        await callback.answer("Gagal kirim ke Channel.")


# ==========================================
# 3. INTERAKSI ADMIN (CHAT & VIEW)
# ==========================================
@router.callback_query(F.data.startswith("admin_msg_"))
async def admin_chat_start(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    await state.update_data(chat_target_id=target_id)
    await state.set_state(ChatAdminState.waiting_admin_msg)
    await callback.message.answer(f"💬 Ketik pesan untuk User <code>{target_id}</code>:", parse_mode="HTML")
    await callback.answer()


@router.message(ChatAdminState.waiting_admin_msg)
async def admin_chat_send(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    target_id = data.get("chat_target_id")
    
    text = f"📩 <b>PESAN ADMIN PICKME</b>\n<code>{'—' * 20}</code>\n{html.escape(message.text)}"
    try:
        await bot.send_message(target_id, text, parse_mode="HTML")
        await message.answer("✅ Pesan terkirim.")
    except:
        await message.answer("❌ Gagal kirim.")
    await state.clear()


@router.callback_query(F.data.startswith("admin_view_"))
async def admin_view_profile(callback: types.CallbackQuery, db: DatabaseService):
    target_id = int(callback.data.split("_")[2])
    user = await db.get_user(target_id)
    
    if user.is_vip_plus:
        status = "💎 VIP+"
    elif user.is_vip:
        status = "🌟 VIP"
    elif user.is_premium:
        status = "🎭 PREMIUM"
    else:
        status = "👤 FREE"
    
    info = (
        f"👤 <b>ADMIN VIEW: {user.full_name}</b>\n"
        f"Kasta: {status}\n"
        f"Saldo: {user.poin_balance:,} Poin\n"
        f"ID: <code>{user.id}</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Chat", callback_data=f"admin_msg_{user.id}")],
        [InlineKeyboardButton(text="❌ Tutup", callback_data="close_admin_view")]
    ])
    await callback.message.answer_photo(photo=user.photo_id, caption=info, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "close_admin_view")
async def close_view(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except Exception:
        pass


# ==========================================
# 4. CONTROL PANEL GOD MODE
# ==========================================
async def render_admin_panel(bot: Bot, chat_id: int):
    """Menampilkan admin control panel"""
    
    # Cleanup ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    text = (
        "⚙️ <b>ADMIN CONTROL PANEL (GOD MODE)</b>\n"
        f"<code>{'—' * 25}</code>\n"
        "Selamat datang, Komandan. Gunakan panel ini dengan bijak.\n\n"
        "👇 <i>Pilih perintah eksekusi:</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 STATISTIK DATABASE", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📢 BROADCAST PENGUMUMAN", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔄 FORCE RESET SPA (ALL USERS)", callback_data="admin_force_reset")],
        [InlineKeyboardButton(text="❌ TUTUP PANEL", callback_data="admin_close")]
    ])
    
    await bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


@router.message(Command("open_control_panel"), IsAdmin())
async def open_panel_command(message: types.Message, bot: Bot):
    try:
        await message.delete()
    except:
        pass
    await render_admin_panel(bot, message.chat.id)


@router.message(Command("open_control_panel"))
async def ignore_non_admin(message: types.Message):
    pass


@router.callback_query(F.data == "admin_menu", IsAdmin())
async def back_to_admin_menu(callback: types.CallbackQuery, bot: Bot):
    try:
        await callback.message.delete()
    except:
        pass
    await render_admin_panel(bot, callback.message.chat.id)
    await callback.answer()


@router.callback_query(F.data == "admin_close", IsAdmin())
async def close_admin_panel(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer("Control Panel Ditutup.")


@router.callback_query(F.data == "admin_stats", IsAdmin())
async def show_bot_statistics(callback: types.CallbackQuery, db: DatabaseService):
    async with db.session_factory() as session:
        total_users = await session.execute(select(func.count(User.id)))
        total_premium = await session.execute(select(func.count(User.id)).where(User.is_premium == True))
        total_vip = await session.execute(select(func.count(User.id)).where(User.is_vip == True))
        total_vipplus = await session.execute(select(func.count(User.id)).where(User.is_vip_plus == True))
        total_points = await session.execute(select(func.sum(User.poin_balance)))
        
        t_usr = total_users.scalar() or 0
        t_prem = total_premium.scalar() or 0
        t_vip = total_vip.scalar() or 0
        t_vipplus = total_vipplus.scalar() or 0
        t_pts = total_points.scalar() or 0
    
    text = (
        "📊 <b>STATISTIK PICKME BOT</b>\n"
        f"<code>{'—' * 25}</code>\n"
        f"👥 <b>Total Pengguna:</b> {t_usr:,} Orang\n"
        f"🎭 <b>Total Premium:</b> {t_prem:,} Orang\n"
        f"🌟 <b>Total VIP:</b> {t_vip:,} Orang\n"
        f"💎 <b>Total VIP+:</b> {t_vipplus:,} Orang\n\n"
        f"💰 <b>Total Poin Beredar:</b> {t_pts:,} Poin\n"
        f"💵 <b>Est. Beban Rupiah:</b> Rp {(t_pts // 10):,}\n"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_menu")]])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        pass


@router.callback_query(F.data == "admin_broadcast", IsAdmin())
async def ask_broadcast_message(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "📢 <b>MODE BROADCAST</b>\n\n"
        "Kirimkan Teks, Foto, atau Video yang ingin Anda siarkan ke seluruh member bot.\n"
        "<i>(Ketik /cancel untuk membatalkan)</i>"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except:
        pass
    await state.set_state(ChatAdminState.waiting_for_broadcast)


@router.message(ChatAdminState.waiting_for_broadcast, IsAdmin())
async def process_broadcast(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        return await render_admin_panel(bot, message.chat.id)
    
    async with db.session_factory() as session:
        result = await session.execute(select(User.id))
        all_users = result.scalars().all()
    
    await state.clear()
    msg_status = await message.answer(f"⏳ <b>Memulai Broadcast ke {len(all_users)} user...</b>\n<i>Ini mungkin memakan waktu beberapa menit.</i>")
    
    success_count = 0
    fail_count = 0
    
    for user_id in all_users:
        try:
            await message.copy_to(chat_id=user_id)
            success_count += 1
        except Exception:
            fail_count += 1
        await asyncio.sleep(0.05)
    
    text_report = (
        "✅ <b>BROADCAST SELESAI!</b>\n"
        f"<code>{'—' * 25}</code>\n"
        f"Berhasil dikirim: <b>{success_count}</b>\n"
        f"Gagal (Blokir bot): <b>{fail_count}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Control Panel", callback_data="admin_menu")]])
    await msg_status.edit_text(text_report, reply_markup=kb)


@router.callback_query(F.data == "admin_force_reset", IsAdmin())
async def confirm_force_reset(callback: types.CallbackQuery):
    text = (
        "⚠️ <b>PERINGATAN BAHAYA (FORCE RESET)</b> ⚠️\n\n"
        "Tindakan ini akan menghapus navigasi SPA semua user saat ini dan mereset layar mereka kembali ke Lobi Dashboard.\n\n"
        "Apakah Anda yakin ingin mengeksekusi ini sekarang?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚨 YA, RESET SELURUH BOT", callback_data="admin_execute_reset")],
        [InlineKeyboardButton(text="❌ BATAL", callback_data="admin_menu")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        pass


@router.callback_query(F.data == "admin_execute_reset", IsAdmin())
async def execute_force_reset(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    msg_status = await callback.message.edit_text("⏳ <b>Menjalankan Force Reset Massal...</b>\n<i>Harap tunggu, jangan matikan server.</i>")
    
    async with db.session_factory() as session:
        result = await session.execute(select(User.id))
        all_users = result.scalars().all()
    
    from handlers.start import render_dashboard_ui
    success_count = 0
    
    for user_id in all_users:
        try:
            async with db.session_factory() as session:
                await session.execute(update(User).where(User.id == user_id).values(nav_stack=["dashboard"]))
                await session.commit()
            
            await render_dashboard_ui(bot, user_id, user_id, db, None, force_new=True)
            success_count += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_menu")]])
    await msg_status.edit_text(f"✅ <b>FORCE RESET SELESAI!</b>\n{success_count} User berhasil dipulihkan ke Dashboard baru.", reply_markup=kb)

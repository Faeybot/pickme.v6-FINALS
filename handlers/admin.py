import os
import html
import logging
from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.database import DatabaseService, User, PointLog

router = Router()


# ==========================================
# 0. KONFIGURASI HAK AKSES
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


FEED_CHANNEL_ID = get_int_id("FEED_CHANNEL_ID")
FINANCE_CHANNEL_ID = get_int_id("FINANCE_CHANNEL_ID")
FINANCE_GROUP_ID = get_int_id("FINANCE_GROUP_ID")

OWNER_ID = get_int_id("OWNER_ID")
ADMIN_FINANCE_IDS = get_list_ids("ADMIN_FINANCE_IDS")
ADMIN_MODERATOR_IDS = get_list_ids("ADMIN_MODERATOR_IDS")

ALL_FINANCE_ADMINS = [OWNER_ID] + ADMIN_FINANCE_IDS
ALL_MODERATORS = [OWNER_ID] + ADMIN_MODERATOR_IDS


# ==========================================
# 1. MODERASI FEED (APPROVE/REJECT)
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


@router.callback_query(F.data.startswith("rej_f_"))
async def admin_reject_feed(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    if callback.from_user.id not in ALL_MODERATORS:
        return await callback.answer("🚫 Moderator Only!", show_alert=True)
    
    parts = callback.data.split("_")
    user_id, quota_info = int(parts[2]), parts[3]
    
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


# ==========================================
# 2. APPROVAL WITHDRAW
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


@router.callback_query(F.data.startswith("wd_deny_"))
async def admin_deny_wd(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    if callback.from_user.id not in ALL_FINANCE_ADMINS:
        return await callback.answer("🚫 Akses Ditolak!", show_alert=True)
    
    parts = callback.data.split("_")
    user_id = int(parts[2])
    trx_id = parts[3]
    
    async with db.session_factory() as session:
        u = await session.get(User, user_id)
        if u:
            # Refund poin
            u.poin_balance += data.get('wd_amount_poin', 0)
        await session.commit()
    
    old_text = callback.message.text
    new_text = f"{old_text}\n\n❌ <b>DITOLAK & DIREFUND</b>\nOleh: {callback.from_user.first_name}"
    await callback.message.edit_text(new_text, reply_markup=None, parse_mode="HTML")
    
    try:
        await bot.send_message(user_id, "❌ <b>WITHDRAW DITOLAK</b>\nPoin Anda telah dikembalikan ke saldo. Silakan hubungi admin untuk info lebih lanjut.", parse_mode="HTML")
    except:
        pass
    await callback.answer("Withdraw Ditolak & Refund!")


# ==========================================
# 3. APPROVAL TRIAL
# ==========================================
@router.callback_query(F.data.startswith("trial_apv_"))
async def admin_approve_trial(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
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

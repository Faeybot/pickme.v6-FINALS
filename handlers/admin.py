import os
import html
import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, 
    Message, ReplyKeyboardRemove, InputMediaPhoto
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, update, and_
from services.database import DatabaseService, User, PointLog, ChatSession

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
BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")

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


class AdminState(StatesGroup):
    waiting_user_id = State()
    waiting_points_amount = State()
    waiting_broadcast = State()
    waiting_search_query = State()


# ==========================================
# 1. MAIN ADMIN PANEL
# ==========================================
async def render_admin_panel(bot: Bot, chat_id: int, message_id: int = None, callback_id: str = None):
    """Menampilkan admin control panel utama"""
    
    # Cleanup ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    text = (
        "⚙️ <b>ADMIN CONTROL PANEL (GOD MODE)</b>\n"
        f"<code>{'—' * 30}</code>\n"
        "Selamat datang, Komandan. Gunakan panel ini dengan bijak.\n\n"
        "👇 <i>Pilih perintah eksekusi:</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 STATISTIK DATABASE", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔍 CARI & KELOLA USER", callback_data="admin_search_user")],
        [InlineKeyboardButton(text="📢 BROADCAST PENGUMUMAN", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="💎 KELOLA KASTA USER", callback_data="admin_manage_tier")],
        [InlineKeyboardButton(text="💰 TAMBAH/KURANGI POIN", callback_data="admin_manage_points")],
        [InlineKeyboardButton(text="🔄 FORCE RESET SPA (ALL USERS)", callback_data="admin_force_reset")],
        [InlineKeyboardButton(text="📤 EXPORT DATA USER", callback_data="admin_export_users")],
        [InlineKeyboardButton(text="❌ TUTUP PANEL", callback_data="admin_close")]
    ])
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    if message_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=message_id, media=media, reply_markup=kb)
        except:
            pass
    else:
        sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
    
    if callback_id:
        try:
            await bot.answer_callback_query(callback_id)
        except:
            pass


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
    await render_admin_panel(bot, callback.message.chat.id, callback.message.message_id, callback.id)


@router.callback_query(F.data == "admin_close", IsAdmin())
async def close_admin_panel(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer("Control Panel Ditutup.")


# ==========================================
# 2. STATISTIK LENGKAP
# ==========================================
@router.callback_query(F.data == "admin_stats", IsAdmin())
async def show_bot_statistics(callback: types.CallbackQuery, db: DatabaseService):
    async with db.session_factory() as session:
        # Total users
        total_users = await session.execute(select(func.count(User.id)))
        t_usr = total_users.scalar() or 0
        
        # Users by tier
        total_premium = await session.execute(select(func.count(User.id)).where(User.is_premium == True))
        total_vip = await session.execute(select(func.count(User.id)).where(User.is_vip == True))
        total_vipplus = await session.execute(select(func.count(User.id)).where(User.is_vip_plus == True))
        total_free = t_usr - (total_premium.scalar() or 0) - (total_vip.scalar() or 0) - (total_vipplus.scalar() or 0)
        
        # Points
        total_points = await session.execute(select(func.sum(User.poin_balance)))
        t_pts = total_points.scalar() or 0
        
        # Active users (last 24 hours)
        day_ago = datetime.utcnow() - timedelta(hours=24)
        active_users = await session.execute(select(func.count(User.id)).where(User.last_active_at >= day_ago))
        active_24h = active_users.scalar() or 0
        
        # Chat sessions active
        now_ts = int(datetime.now().timestamp())
        active_chats = await session.execute(select(func.count(ChatSession.id)).where(ChatSession.expires_at > now_ts))
        active_chats_count = active_chats.scalar() or 0
        
        # Today's new users
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        new_today = await session.execute(select(func.count(User.id)).where(User.last_active_at >= today_start))
        new_today_count = new_today.scalar() or 0
        
        # Swipes today
        swipes_today = await session.execute(select(func.count(SwipeHistory.id)).where(SwipeHistory.created_at >= today_start))
        swipes_count = swipes_today.scalar() or 0
        
        # Withdraw requests pending
        pending_wd = await session.execute(select(func.count(WithdrawRequest.id)).where(WithdrawRequest.status == "PENDING"))
        pending_wd_count = pending_wd.scalar() or 0
    
    text = (
        "📊 <b>STATISTIK PICKME BOT</b>\n"
        f"<code>{'—' * 30}</code>\n"
        f"👥 <b>Total Pengguna:</b> {t_usr:,} Orang\n"
        f"├─ 💎 VIP+: {total_vipplus.scalar() or 0:,}\n"
        f"├─ 🌟 VIP: {total_vip.scalar() or 0:,}\n"
        f"├─ 🎭 Premium: {total_premium.scalar() or 0:,}\n"
        f"└─ 👤 Free: {total_free:,}\n\n"
        
        f"📈 <b>Aktivitas 24 Jam:</b>\n"
        f"├─ Aktif: {active_24h:,} User\n"
        f"├─ User Baru: {new_today_count:,}\n"
        f"├─ Swipe: {swipes_count:,}\n"
        f"└─ Chat Aktif: {active_chats_count:,} Sesi\n\n"
        
        f"💰 <b>Keuangan:</b>\n"
        f"├─ Poin Beredar: {t_pts:,} Poin\n"
        f"├─ Estimasi Rupiah: Rp {(t_pts // 10):,}\n"
        f"└─ WD Pending: {pending_wd_count} Request\n"
        f"<code>{'—' * 30}</code>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_stats")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Panel", callback_data="admin_menu")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==========================================
# 3. CARI & KELOLA USER
# ==========================================
@router.callback_query(F.data == "admin_search_user", IsAdmin())
async def ask_user_id(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "🔍 <b>CARI USER</b>\n\n"
        "Masukkan <b>ID Telegram</b> atau <b>Username</b> user yang ingin dicari.\n"
        "<i>(Contoh: 123456789 atau @username)</i>\n\n"
        "Ketik /cancel untuk membatalkan."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_menu")]])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    
    await state.set_state(AdminState.waiting_search_query)
    await callback.answer()


@router.message(AdminState.waiting_search_query, IsAdmin())
async def process_user_search(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        return await render_admin_panel(bot, message.chat.id)
    
    query = message.text.strip()
    user = None
    
    # Cari berdasarkan ID
    if query.lstrip('-').isdigit():
        user = await db.get_user(int(query))
    # Cari berdasarkan username
    elif query.startswith("@"):
        username = query[1:]
        async with db.session_factory() as session:
            result = await session.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
    
    try:
        await message.delete()
    except:
        pass
    
    if not user:
        err_text = f"❌ User dengan ID/Username <code>{query}</code> tidak ditemukan."
        await message.answer(err_text, parse_mode="HTML")
        return
    
    # Tampilkan detail user
    await show_user_detail(message.chat.id, user, bot, db)


async def show_user_detail(chat_id: int, user: User, bot: Bot, db: DatabaseService):
    """Menampilkan detail user dengan opsi kelola"""
    
    if user.is_vip_plus:
        kasta = "💎 VIP+"
    elif user.is_vip:
        kasta = "🌟 VIP"
    elif user.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"
    
    # Hitung sisa waktu VIP jika ada
    vip_expiry = ""
    if user.vip_expires_at:
        remaining = user.vip_expires_at - datetime.utcnow()
        days = remaining.days
        hours = remaining.seconds // 3600
        if days > 0:
            vip_expiry = f" (Sisa {days} hari)"
        elif hours > 0:
            vip_expiry = f" (Sisa {hours} jam)"
        else:
            vip_expiry = " (Segera habis)"
    
    text = (
        f"👤 <b>DETAIL USER</b>\n"
        f"<code>{'—' * 30}</code>\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📛 Nama: {html.escape(user.full_name)}\n"
        f"👑 Kasta: {kasta}{vip_expiry}\n"
        f"💰 Poin: {user.poin_balance:,}\n"
        f"📍 Lokasi: {user.location_name}\n"
        f"🎂 Usia: {user.age} tahun\n"
        f"👫 Gender: {user.gender}\n"
        f"📝 Bio: {user.bio[:50] if user.bio else '-'}...\n"
        f"📅 Terakhir aktif: {user.last_active_at.strftime('%d/%m %H:%M') if user.last_active_at else '-'}\n"
        f"<code>{'—' * 30}</code>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Tambah Poin", callback_data=f"admin_add_points_{user.id}"),
         InlineKeyboardButton(text="💎 Ubah Kasta", callback_data=f"admin_change_tier_{user.id}")],
        [InlineKeyboardButton(text="💬 Kirim Pesan", callback_data=f"admin_msg_{user.id}"),
         InlineKeyboardButton(text="👀 Lihat Profil", callback_data=f"admin_view_{user.id}")],
        [InlineKeyboardButton(text="🔄 Reset SPA", callback_data=f"admin_reset_spa_{user.id}")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Cari User", callback_data="admin_search_user"),
         InlineKeyboardButton(text="🏠 Menu Utama", callback_data="admin_menu")]
    ])
    
    media = InputMediaPhoto(media=user.photo_id or BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    try:
        await bot.send_photo(chat_id=chat_id, photo=user.photo_id or BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode="HTML")


# ==========================================
# 4. KELOLA POIN USER
# ==========================================
@router.callback_query(F.data.startswith("admin_add_points_"), IsAdmin())
async def ask_points_amount(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[3])
    await state.update_data(target_user_id=user_id)
    
    text = (
        "💰 <b>TAMBAH/KURANGI POIN</b>\n\n"
        "Masukkan jumlah poin yang ingin ditambahkan.\n"
        "Gunakan tanda <b>-</b> untuk mengurangi poin.\n\n"
        "<i>Contoh: 5000 atau -1000</i>\n\n"
        "Ketik /cancel untuk membatalkan."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="admin_search_user")]])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    
    await state.set_state(AdminState.waiting_points_amount)
    await callback.answer()


@router.message(AdminState.waiting_points_amount, IsAdmin())
async def process_points_change(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        return await render_admin_panel(bot, message.chat.id)
    
    data = await state.get_data()
    target_id = data.get("target_user_id")
    
    try:
        amount = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Masukkan angka yang valid!")
        return
    
    try:
        await message.delete()
    except:
        pass
    
    user = await db.get_user(target_id)
    if not user:
        await message.answer("❌ User tidak ditemukan.")
        await state.clear()
        return
    
    # Update poin
    async with db.session_factory() as session:
        u = await session.get(User, target_id)
        u.poin_balance += amount
        session.add(PointLog(user_id=target_id, amount=amount, source=f"Admin Adjustment by {message.from_user.id}"))
        await session.commit()
    
    # Notifikasi ke user
    if amount > 0:
        notif_text = f"🎉 <b>BONUS DARI ADMIN!</b>\nSaldo poin Anda bertambah <b>+{amount:,} Poin</b>."
    else:
        notif_text = f"⚠️ <b>PENYESUAIAN ADMIN</b>\nSaldo poin Anda berkurang <b>{amount:,} Poin</b>."
    
    try:
        await bot.send_message(target_id, notif_text, parse_mode="HTML")
    except:
        pass
    
    await message.answer(f"✅ Poin user <code>{target_id}</code> telah diubah: {'+' if amount > 0 else ''}{amount:,} poin. Saldo sekarang: {user.poin_balance + amount:,}")
    await state.clear()
    await show_user_detail(message.chat.id, user, bot, db)


# ==========================================
# 5. KELOLA KASTA USER
# ==========================================
@router.callback_query(F.data.startswith("admin_change_tier_"), IsAdmin())
async def show_tier_options(callback: types.CallbackQuery, db: DatabaseService):
    user_id = int(callback.data.split("_")[3])
    user = await db.get_user(user_id)
    
    if not user:
        return await callback.answer("User tidak ditemukan.", show_alert=True)
    
    text = (
        f"💎 <b>UBAH KASTA USER</b>\n"
        f"<code>{'—' * 30}</code>\n"
        f"User: <b>{user.full_name}</b>\n"
        f"Kasta Saat Ini: "
    )
    
    if user.is_vip_plus:
        text += "💎 VIP+\n\n"
    elif user.is_vip:
        text += "🌟 VIP\n\n"
    elif user.is_premium:
        text += "🎭 PREMIUM\n\n"
    else:
        text += "👤 FREE\n\n"
    
    text += "Pilih kasta baru untuk user ini:"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 FREE", callback_data=f"admin_set_tier_{user_id}_free")],
        [InlineKeyboardButton(text="🎭 PREMIUM (Seumur Hidup)", callback_data=f"admin_set_tier_{user_id}_premium")],
        [InlineKeyboardButton(text="🌟 VIP (30 Hari)", callback_data=f"admin_set_tier_{user_id}_vip")],
        [InlineKeyboardButton(text="💎 VIP+ (30 Hari)", callback_data=f"admin_set_tier_{user_id}_vipplus")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data=f"admin_view_{user_id}")]
    ])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin_set_tier_"), IsAdmin())
async def execute_tier_change(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    parts = callback.data.split("_")
    user_id = int(parts[3])
    tier = parts[4]
    
    expiry_date = datetime.utcnow() + timedelta(days=30) if tier in ["vip", "vipplus"] else None
    
    async with db.session_factory() as session:
        user = await session.get(User, user_id)
        if not user:
            return await callback.answer("User tidak ditemukan.", show_alert=True)
        
        if tier == "free":
            user.is_premium = False
            user.is_vip = False
            user.is_vip_plus = False
            user.vip_expires_at = None
            user.daily_feed_text_quota = 2
            user.daily_feed_photo_quota = 0
            user.daily_message_quota = 0
            user.daily_open_profile_quota = 0
            user.daily_unmask_quota = 0
            user.daily_swipe_quota = 10
            tier_name = "FREE"
        elif tier == "premium":
            user.is_premium = True
            user.is_vip = False
            user.is_vip_plus = False
            user.vip_expires_at = None
            user.daily_feed_text_quota = 3
            user.daily_feed_photo_quota = 1
            user.daily_message_quota = 0
            user.daily_open_profile_quota = 0
            user.daily_unmask_quota = 0
            user.daily_swipe_quota = 20
            tier_name = "PREMIUM"
        elif tier == "vip":
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
            tier_name = "VIP"
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
            tier_name = "VIP+"
        
        await session.commit()
    
    # Notifikasi ke user
    notif_text = (
        f"👑 <b>UPDATE KASTA AKUN</b>\n\n"
        f"Selamat! Kasta akun Anda telah diubah menjadi <b>{tier_name}</b> oleh Admin.\n"
        f"{'Berlaku selama 30 hari ke depan.' if expiry_date else 'Status ini permanen.'}\n\n"
        f"Silakan cek menu Akun Saya untuk melihat detail kuota baru Anda."
    )
    try:
        await bot.send_message(user_id, notif_text, parse_mode="HTML")
    except:
        pass
    
    await callback.answer(f"✅ Kasta user diubah menjadi {tier_name}!")
    user = await db.get_user(user_id)
    await show_user_detail(callback.message.chat.id, user, bot, db)


# ==========================================
# 6. FORCE RESET SPA (INDIVIDUAL)
# ==========================================
@router.callback_query(F.data.startswith("admin_reset_spa_"), IsAdmin())
async def reset_individual_spa(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    user_id = int(callback.data.split("_")[3])
    
    async with db.session_factory() as session:
        await session.execute(update(User).where(User.id == user_id).values(nav_stack=["dashboard"]))
        await session.commit()
    
    await callback.answer("✅ SPA user telah direset ke Dashboard!")
    
    # Coba kirim ulang dashboard ke user
    from handlers.start import render_dashboard_ui
    try:
        await render_dashboard_ui(bot, user_id, user_id, db, None, force_new=True)
    except:
        pass
    
    user = await db.get_user(user_id)
    await show_user_detail(callback.message.chat.id, user, bot, db)


# ==========================================
# 7. FORCE RESET SPA (MASSAL)
# ==========================================
@router.callback_query(F.data == "admin_force_reset", IsAdmin())
async def confirm_force_reset(callback: types.CallbackQuery):
    text = (
        "⚠️ <b>PERINGATAN BAHAYA (FORCE RESET MASSAL)</b> ⚠️\n\n"
        "Tindakan ini akan menghapus navigasi SPA <b>SEMUA USER</b> saat ini dan mereset layar mereka kembali ke Dashboard.\n\n"
        "⚠️ <b>Efek:</b>\n"
        "• Semua user akan kembali ke halaman utama\n"
        "• Tidak ada data yang hilang\n"
        "• Proses ini memakan waktu beberapa menit\n\n"
        "Apakah Anda yakin ingin mengeksekusi ini sekarang?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚨 YA, RESET SEMUA USER", callback_data="admin_execute_reset")],
        [InlineKeyboardButton(text="❌ BATAL", callback_data="admin_menu")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


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
            
            # Coba kirim ulang dashboard (abaikan error jika user block)
            try:
                await render_dashboard_ui(bot, user_id, user_id, db, None, force_new=True)
            except:
                pass
            
            success_count += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Panel", callback_data="admin_menu")]])
    await msg_status.edit_text(f"✅ <b>FORCE RESET SELESAI!</b>\n{success_count} User berhasil dipulihkan ke Dashboard baru.", reply_markup=kb)
    await callback.answer()


# ==========================================
# 8. BROADCAST PENGUMUMAN
# ==========================================
@router.callback_query(F.data == "admin_broadcast", IsAdmin())
async def ask_broadcast_message(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "📢 <b>MODE BROADCAST</b>\n\n"
        "Kirimkan Teks, Foto, atau Video yang ingin Anda siarkan ke seluruh member bot.\n\n"
        "⚠️ <b>Tips:</b>\n"
        "• Broadcast akan dikirim ke SEMUA user\n"
        "• Proses bisa memakan waktu lama (1-2 menit per 1000 user)\n"
        "• User yang memblokir bot tidak akan menerima\n\n"
        "<i>Ketik /cancel untuk membatalkan</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Panel", callback_data="admin_menu")]])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    
    await state.set_state(AdminState.waiting_broadcast)
    await callback.answer()


@router.message(AdminState.waiting_broadcast, IsAdmin())
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
            if message.photo:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption or "",
                    parse_mode="HTML"
                )
            elif message.video:
                await bot.send_video(
                    chat_id=user_id,
                    video=message.video.file_id,
                    caption=message.caption or "",
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=message.text or message.caption or "",
                    parse_mode="HTML"
                )
            success_count += 1
        except Exception:
            fail_count += 1
        await asyncio.sleep(0.05)
    
    text_report = (
        "✅ <b>BROADCAST SELESAI!</b>\n"
        f"<code>{'—' * 30}</code>\n"
        f"Berhasil dikirim: <b>{success_count}</b>\n"
        f"Gagal (Blokir/Error): <b>{fail_count}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Control Panel", callback_data="admin_menu")]])
    await msg_status.edit_text(text_report, reply_markup=kb)


# ==========================================
# 9. EXPORT DATA USER
# ==========================================
@router.callback_query(F.data == "admin_export_users", IsAdmin())
async def export_users_data(callback: types.CallbackQuery, db: DatabaseService):
    msg_status = await callback.message.edit_text("⏳ <b>Mengambil data user...</b>\n<i>Harap tunggu.</i>")
    
    async with db.session_factory() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
    
    # Buat file CSV
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Nama", "Usia", "Gender", "Kota", "Kasta", "Poin", "Terakhir Aktif", "Tanggal Daftar"])
    
    for user in users:
        if user.is_vip_plus:
            kasta = "VIP+"
        elif user.is_vip:
            kasta = "VIP"
        elif user.is_premium:
            kasta = "Premium"
        else:
            kasta = "Free"
        
        writer.writerow([
            user.id,
            user.full_name,
            user.age,
            user.gender,
            user.location_name,
            kasta,
            user.poin_balance,
            user.last_active_at.strftime("%Y-%m-%d %H:%M") if user.last_active_at else "-",
            user.created_at.strftime("%Y-%m-%d") if hasattr(user, 'created_at') else "-"
        ])
    
    output.seek(0)
    
    # Kirim file ke admin
    from aiogram.types import BufferedInputFile
    file = BufferedInputFile(output.getvalue().encode('utf-8'), filename="pickme_users_export.csv")
    
    await msg_status.delete()
    await callback.message.answer_document(
        document=file,
        caption=f"📊 <b>Export Data User</b>\nTotal: {len(users)} user\n\nFile CSV siap diunduh.",
        parse_mode="HTML"
    )
    await callback.answer()


# ==========================================
# 10. DIVISI KEUANGAN (WD & TRIAL APPROVAL)
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


# ==========================================
# 11. DIVISI MODERASI (FEED)
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
# 12. INTERAKSI ADMIN (CHAT & VIEW)
# ==========================================
class ChatAdminState(StatesGroup):
    waiting_admin_msg = State()


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
    await show_user_detail(callback.message.chat.id, user, callback.bot, db)
    await callback.answer()

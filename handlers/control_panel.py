"""
CONTROL PANEL - Untuk Owner dan Admin Penuh
Fitur: Statistik, Cari User, Kelola Poin, Kelola Kasta, Broadcast, Reset SPA, Export Data
"""

import os
import html
import asyncio
import logging
import csv
import io
from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, 
    Message, ReplyKeyboardRemove, InputMediaPhoto, BufferedInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func, update, and_
from services.database import DatabaseService, User, PointLog, ChatSession, SwipeHistory, WithdrawRequest

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")


# ==========================================
# 0. KONFIGURASI HAK AKSES ADMIN
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


OWNER_ID = get_int_id("OWNER_ID")
ADMIN_FINANCE_IDS = get_list_ids("ADMIN_FINANCE_IDS")
ADMIN_MODERATOR_IDS = get_list_ids("ADMIN_MODERATOR_IDS")

# CONTROL PANEL hanya untuk Owner dan Finance Admin
CONTROL_PANEL_ADMINS = list(set([OWNER_ID] + ADMIN_FINANCE_IDS))


class IsControlPanelAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in CONTROL_PANEL_ADMINS


class ControlPanelState(StatesGroup):
    waiting_search_query = State()
    waiting_points_amount = State()
    waiting_user_id = State()
    waiting_broadcast = State()


# ==========================================
# 1. FUNGSI SHOW USER DETAIL
# ==========================================
async def show_user_detail(chat_id: int, user, bot: Bot, db: DatabaseService):
    """Menampilkan detail user dengan opsi kelola"""
    
    if user.is_vip_plus:
        kasta = "💎 VIP+"
    elif user.is_vip:
        kasta = "🌟 VIP"
    elif user.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"
    
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
        [InlineKeyboardButton(text="💰 Tambah Poin", callback_data=f"cp_add_points_{user.id}"),
         InlineKeyboardButton(text="💎 Ubah Kasta", callback_data=f"cp_change_tier_{user.id}")],
        [InlineKeyboardButton(text="💬 Kirim Pesan", callback_data=f"cp_msg_{user.id}"),
         InlineKeyboardButton(text="👀 Lihat Profil", callback_data=f"cp_view_{user.id}")],
        [InlineKeyboardButton(text="🔄 Reset SPA", callback_data=f"cp_reset_spa_{user.id}")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="cp_menu")]
    ])
    
    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=user.photo_id or BANNER_PHOTO_ID,
            caption=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
    except:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode="HTML")


# ==========================================
# 2. RENDERER: CONTROL PANEL UTAMA
# ==========================================
async def render_control_panel(bot: Bot, chat_id: int, message_id: int = None, callback_id: str = None):
    """Menampilkan Control Panel utama"""
    
    # Cleanup ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    text = (
        "🎮 <b>CONTROL PANEL - PICKME BOT</b>\n"
        f"<code>{'—' * 30}</code>\n"
        "Panel khusus untuk Owner & Admin Finance.\n\n"
        "👇 <i>Pilih perintah eksekusi:</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 STATISTIK", callback_data="cp_stats")],
        [InlineKeyboardButton(text="🔍 CARI & KELOLA USER", callback_data="cp_search_user")],
        [InlineKeyboardButton(text="📢 BROADCAST", callback_data="cp_broadcast")],
        [InlineKeyboardButton(text="💎 KELOLA KASTA", callback_data="cp_manage_tier")],
        [InlineKeyboardButton(text="💰 TAMBAH/KURANGI POIN", callback_data="cp_manage_points")],
        [InlineKeyboardButton(text="🔄 RESET SPA (ALL USERS)", callback_data="cp_reset_all")],
        [InlineKeyboardButton(text="📤 EXPORT DATA USER", callback_data="cp_export_users")],
        [InlineKeyboardButton(text="❌ TUTUP PANEL", callback_data="cp_close")]
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


@router.message(Command("control_panel"), IsControlPanelAdmin())
async def open_control_panel(message: types.Message, bot: Bot):
    try:
        await message.delete()
    except:
        pass
    await render_control_panel(bot, message.chat.id)


@router.message(Command("control_panel"))
async def ignore_non_admin(message: types.Message):
    pass


@router.callback_query(F.data == "cp_menu", IsControlPanelAdmin())
async def back_to_cp_menu(callback: types.CallbackQuery, bot: Bot):
    await render_control_panel(bot, callback.message.chat.id, callback.message.message_id, callback.id)


@router.callback_query(F.data == "cp_close", IsControlPanelAdmin())
async def close_control_panel(callback: types.CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer("Control Panel Ditutup.")


# ==========================================
# 3. STATISTIK
# ==========================================
@router.callback_query(F.data == "cp_stats", IsControlPanelAdmin())
async def show_statistics(callback: types.CallbackQuery, db: DatabaseService):
    await callback.answer("⏳ Mengambil data statistik...")
    
    async with db.session_factory() as session:
        total_users = await session.execute(select(func.count(User.id)))
        t_usr = total_users.scalar() or 0
        
        total_premium = await session.execute(select(func.count(User.id)).where(User.is_premium == True))
        total_vip = await session.execute(select(func.count(User.id)).where(User.is_vip == True))
        total_vipplus = await session.execute(select(func.count(User.id)).where(User.is_vip_plus == True))
        total_free = t_usr - (total_premium.scalar() or 0) - (total_vip.scalar() or 0) - (total_vipplus.scalar() or 0)
        
        total_points = await session.execute(select(func.sum(User.poin_balance)))
        t_pts = total_points.scalar() or 0
        
        day_ago = datetime.utcnow() - timedelta(hours=24)
        active_users = await session.execute(select(func.count(User.id)).where(User.last_active_at >= day_ago))
        active_24h = active_users.scalar() or 0
        
        now_ts = int(datetime.now().timestamp())
        active_chats = await session.execute(select(func.count(ChatSession.id)).where(ChatSession.expires_at > now_ts))
        active_chats_count = active_chats.scalar() or 0
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        new_today = await session.execute(select(func.count(User.id)).where(User.last_active_at >= today_start))
        new_today_count = new_today.scalar() or 0
        
        swipes_today = await session.execute(select(func.count(SwipeHistory.id)).where(SwipeHistory.created_at >= today_start))
        swipes_count = swipes_today.scalar() or 0
        
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
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="cp_stats")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="cp_menu")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        except:
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# ==========================================
# 4. CARI USER
# ==========================================
@router.callback_query(F.data == "cp_search_user", IsControlPanelAdmin())
async def ask_search_user(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "🔍 <b>CARI USER</b>\n\n"
        "Masukkan <b>ID Telegram</b> user yang ingin dicari.\n"
        "<i>(Contoh: 123456789)</i>\n\n"
        "Ketik /cancel untuk membatalkan."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="cp_menu")]])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    
    await state.set_state(ControlPanelState.waiting_search_query)
    await callback.answer()


@router.message(ControlPanelState.waiting_search_query, IsControlPanelAdmin())
async def process_search_user(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        return await render_control_panel(bot, message.chat.id)
    
    query = message.text.strip()
    user = None
    
    if query.lstrip('-').isdigit():
        user = await db.get_user(int(query))
    
    try:
        await message.delete()
    except:
        pass
    
    if not user:
        await message.answer(f"❌ User dengan ID <code>{query}</code> tidak ditemukan.", parse_mode="HTML")
        return
    
    await show_user_detail(message.chat.id, user, bot, db)
    await state.clear()


# ==========================================
# 5. TAMBAH/KURANGI POIN
# ==========================================
@router.callback_query(F.data == "cp_manage_points", IsControlPanelAdmin())
async def ask_points_user_id(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "💰 <b>TAMBAH/KURANGI POIN</b>\n\n"
        "Masukkan <b>ID Telegram</b> user yang ingin diubah poinnya.\n"
        "<i>(Contoh: 123456789)</i>\n\n"
        "Ketik /cancel untuk membatalkan."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="cp_menu")]])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    
    await state.set_state(ControlPanelState.waiting_user_id)
    await callback.answer()


@router.message(ControlPanelState.waiting_user_id, IsControlPanelAdmin())
async def process_points_user_id(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        return await render_control_panel(bot, message.chat.id)
    
    query = message.text.strip()
    if not query.lstrip('-').isdigit():
        await message.answer("⚠️ Masukkan ID Telegram yang valid (angka)!")
        return
    
    user_id = int(query)
    user = await db.get_user(user_id)
    
    try:
        await message.delete()
    except:
        pass
    
    if not user:
        await message.answer(f"❌ User dengan ID <code>{user_id}</code> tidak ditemukan.", parse_mode="HTML")
        await state.clear()
        return
    
    await state.update_data(target_user_id=user_id)
    
    text = (
        "💰 <b>MASUKKAN NOMINAL POIN</b>\n\n"
        f"User: <b>{user.full_name}</b>\n"
        f"Saldo saat ini: <b>{user.poin_balance:,} Poin</b>\n\n"
        "Masukkan jumlah poin yang ingin ditambahkan.\n"
        "Gunakan tanda <b>-</b> untuk mengurangi poin.\n\n"
        "<i>Contoh: 5000 atau -1000</i>\n\n"
        "Ketik /cancel untuk membatalkan."
    )
    
    await message.answer(text, parse_mode="HTML")
    await state.set_state(ControlPanelState.waiting_points_amount)


@router.message(ControlPanelState.waiting_points_amount, IsControlPanelAdmin())
async def process_points_change(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        return await render_control_panel(bot, message.chat.id)
    
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
    
    async with db.session_factory() as session:
        u = await session.get(User, target_id)
        u.poin_balance += amount
        session.add(PointLog(user_id=target_id, amount=amount, source=f"Admin Adjustment by {message.from_user.id}"))
        await session.commit()
    
    if amount > 0:
        notif_text = f"🎉 <b>BONUS DARI ADMIN!</b>\nSaldo poin Anda bertambah <b>+{amount:,} Poin</b>."
    else:
        notif_text = f"⚠️ <b>PENYESUAIAN ADMIN</b>\nSaldo poin Anda berkurang <b>{abs(amount):,} Poin</b>."
    
    try:
        await bot.send_message(target_id, notif_text, parse_mode="HTML")
    except:
        pass
    
    await message.answer(f"✅ Poin user <code>{target_id}</code> telah diubah: {'+' if amount > 0 else ''}{amount:,} poin. Saldo sekarang: {user.poin_balance + amount:,}")
    await state.clear()
    await show_user_detail(message.chat.id, user, bot, db)


# ==========================================
# 6. KELOLA KASTA USER
# ==========================================
@router.callback_query(F.data == "cp_manage_tier", IsControlPanelAdmin())
async def ask_tier_user_id(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "💎 <b>KELOLA KASTA USER</b>\n\n"
        "Masukkan <b>ID Telegram</b> user yang ingin diubah kastanya.\n"
        "<i>(Contoh: 123456789)</i>\n\n"
        "Ketik /cancel untuk membatalkan."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="cp_menu")]])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    
    await state.set_state(ControlPanelState.waiting_user_id)
    await callback.answer()


async def show_tier_options(chat_id: int, user, bot: Bot, db: DatabaseService, state: FSMContext):
    """Menampilkan opsi pemilihan kasta"""
    
    if user.is_vip_plus:
        current_tier = "💎 VIP+"
    elif user.is_vip:
        current_tier = "🌟 VIP"
    elif user.is_premium:
        current_tier = "🎭 PREMIUM"
    else:
        current_tier = "👤 FREE"
    
    text = (
        f"💎 <b>UBAH KASTA USER</b>\n"
        f"<code>{'—' * 30}</code>\n"
        f"User: <b>{user.full_name}</b>\n"
        f"Kasta Saat Ini: {current_tier}\n\n"
        f"Pilih kasta baru untuk user ini:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 FREE", callback_data=f"cp_set_tier_{user.id}_free")],
        [InlineKeyboardButton(text="🎭 PREMIUM (Seumur Hidup)", callback_data=f"cp_set_tier_{user.id}_premium")],
        [InlineKeyboardButton(text="🌟 VIP (30 Hari)", callback_data=f"cp_set_tier_{user.id}_vip")],
        [InlineKeyboardButton(text="💎 VIP+ (30 Hari)", callback_data=f"cp_set_tier_{user.id}_vipplus")],
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="cp_menu")]
    ])
    
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data.startswith("cp_set_tier_"), IsControlPanelAdmin())
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
# 7. RESET SPA (INDIVIDUAL)
# ==========================================
@router.callback_query(F.data.startswith("cp_reset_spa_"), IsControlPanelAdmin())
async def reset_individual_spa(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    user_id = int(callback.data.split("_")[3])
    
    async with db.session_factory() as session:
        await session.execute(update(User).where(User.id == user_id).values(nav_stack=["dashboard"]))
        await session.commit()
    
    await callback.answer("✅ SPA user telah direset ke Dashboard!")
    
    from handlers.start import render_dashboard_ui
    try:
        await render_dashboard_ui(bot, user_id, user_id, db, None, force_new=True)
    except:
        pass
    
    user = await db.get_user(user_id)
    await show_user_detail(callback.message.chat.id, user, bot, db)


# ==========================================
# 8. RESET SPA (MASSAL)
# ==========================================
@router.callback_query(F.data == "cp_reset_all", IsControlPanelAdmin())
async def confirm_reset_all(callback: types.CallbackQuery):
    text = (
        "⚠️ <b>PERINGATAN BAHAYA (RESET MASSAL)</b> ⚠️\n\n"
        "Tindakan ini akan menghapus navigasi SPA <b>SEMUA USER</b> dan mereset layar mereka ke Dashboard.\n\n"
        "⚠️ <b>Efek:</b>\n"
        "• Semua user akan kembali ke halaman utama\n"
        "• Tidak ada data yang hilang\n"
        "• Proses ini memakan waktu beberapa menit\n\n"
        "Apakah Anda yakin ingin melanjutkan?"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚨 YA, RESET SEMUA", callback_data="cp_execute_reset")],
        [InlineKeyboardButton(text="❌ BATAL", callback_data="cp_menu")]
    ])
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "cp_execute_reset", IsControlPanelAdmin())
async def execute_reset_all(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    msg_status = await callback.message.edit_text("⏳ <b>Menjalankan Reset Massal...</b>\n<i>Harap tunggu.</i>")
    
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
            
            try:
                await render_dashboard_ui(bot, user_id, user_id, db, None, force_new=True)
            except:
                pass
            
            success_count += 1
        except Exception:
            pass
        await asyncio.sleep(0.05)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="cp_menu")]])
    await msg_status.edit_text(f"✅ <b>RESET SELESAI!</b>\n{success_count} User berhasil dipulihkan.", reply_markup=kb)
    await callback.answer()


# ==========================================
# 9. BROADCAST
# ==========================================
@router.callback_query(F.data == "cp_broadcast", IsControlPanelAdmin())
async def ask_broadcast(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "📢 <b>BROADCAST PENGUMUMAN</b>\n\n"
        "Kirimkan Teks, Foto, atau Video yang ingin Anda siarkan ke seluruh member bot.\n\n"
        "⚠️ <b>Tips:</b>\n"
        "• Broadcast akan dikirim ke SEMUA user\n"
        "• Proses bisa memakan waktu lama\n"
        "• User yang memblokir bot tidak akan menerima\n\n"
        "<i>Ketik /cancel untuk membatalkan</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="cp_menu")]])
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    
    await state.set_state(ControlPanelState.waiting_broadcast)
    await callback.answer()


@router.message(ControlPanelState.waiting_broadcast, IsControlPanelAdmin())
async def process_broadcast(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    if message.text == "/cancel":
        await state.clear()
        return await render_control_panel(bot, message.chat.id)
    
    async with db.session_factory() as session:
        result = await session.execute(select(User.id))
        all_users = result.scalars().all()
    
    await state.clear()
    msg_status = await message.answer(f"⏳ <b>Memulai Broadcast ke {len(all_users)} user...</b>\n<i>Mohon tunggu.</i>")
    
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
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="cp_menu")]])
    await msg_status.edit_text(text_report, reply_markup=kb)


# ==========================================
# 10. EXPORT DATA USER
# ==========================================
@router.callback_query(F.data == "cp_export_users", IsControlPanelAdmin())
async def export_users_data(callback: types.CallbackQuery, db: DatabaseService):
    msg_status = await callback.message.edit_text("⏳ <b>Mengambil data user...</b>\n<i>Harap tunggu.</i>")
    
    async with db.session_factory() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Nama", "Usia", "Gender", "Kota", "Kasta", "Poin", "Terakhir Aktif"])
    
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
            user.last_active_at.strftime("%Y-%m-%d %H:%M") if user.last_active_at else "-"
        ])
    
    output.seek(0)
    
    file = BufferedInputFile(output.getvalue().encode('utf-8'), filename="pickme_users_export.csv")
    
    await msg_status.delete()
    await callback.message.answer_document(
        document=file,
        caption=f"📊 <b>Export Data User</b>\nTotal: {len(users)} user\n\nFile CSV siap diunduh.",
        parse_mode="HTML"
    )
    await callback.answer()


# ==========================================
# 11. KIRIM PESAN KE USER
# ==========================================
class ChatAdminState(StatesGroup):
    waiting_admin_msg = State()


@router.callback_query(F.data.startswith("cp_msg_"), IsControlPanelAdmin())
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


@router.callback_query(F.data.startswith("cp_view_"), IsControlPanelAdmin())
async def admin_view_profile(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    target_id = int(callback.data.split("_")[2])
    user = await db.get_user(target_id)
    await show_user_detail(callback.message.chat.id, user, bot, db)
    await callback.answer()

import os
import uuid
import html
import logging
import asyncio
from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove
from sqlalchemy import select, and_
from services.database import DatabaseService, User, PointLog, ReferralTracking

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")
FINANCE_GROUP_ID = os.getenv("FINANCE_GROUP_ID")
POIN_TO_IDR_RATE = 0.1  # 10 Poin = Rp 1


class WithdrawState(StatesGroup):
    waiting_amount = State()
    waiting_wallet_type = State()
    waiting_wallet_number = State()
    waiting_wallet_name = State()


# ==========================================
# 1. CORE UI RENDERER: DOMPET & REWARD
# ==========================================
async def render_wallet_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None):
    """Menampilkan dashboard dompet"""
    
    # Cleanup ReplyKeyboard
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
    
    await db.push_nav(user_id, "wallet")
    
    saldo_rp = int(user.poin_balance * POIN_TO_IDR_RATE)
    
    text = (
        f"💰 <b>DOMPET & REWARD PENGHASILAN</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"<b>💎 SALDO AKTIF ANDA:</b>\n"
        f"🪙 Poin: <b>{user.poin_balance:,} Poin</b>\n"
        f"💵 Estimasi: <b>Rp {saldo_rp:,}</b>\n\n"
        
        f"<b>📊 RINCIAN PENDAPATAN:</b>\n"
        f"• Profil Dilihat: <b>+100 Poin</b>\n"
        f"• Pesan Masuk: <b>+100 Poin</b>\n"
        f"🎁 <b>Bonus Balas Chat:</b> <b>+200 Poin</b>\n"
        f"• Unmask Profil: <b>+500 Poin</b>\n"
        f"🎁 <b>Bonus Balas Unmask:</b> <b>+500 Poin</b>\n\n"
        
        f"👇 <i>Pilih menu di bawah ini untuk mengelola saldo atau menambah cuan dari program undangan!</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏧 TARIK SALDO (WITHDRAW)", callback_data="wallet_withdraw")],
        [InlineKeyboardButton(text="🎁 PROGRAM REFERRAL (AJAK TEMAN)", callback_data="wallet_referral")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Dashboard", callback_data="back_to_dashboard")]
    ])
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    if callback_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
            await bot.answer_callback_query(callback_id)
        except:
            pass
    else:
        try:
            if user.anchor_msg_id:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=user.anchor_msg_id)
                except:
                    pass
            sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
        except Exception as e:
            logging.error(f"Gagal render wallet UI: {e}")
    
    return True


@router.callback_query(F.data == "menu_finance")
async def show_wallet_dashboard(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext, bot: Bot):
    await render_wallet_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


# ==========================================
# 2. SUB-MENU: WITHDRAWAL LOGIC
# ==========================================
@router.callback_query(F.data == "wallet_withdraw")
async def start_withdraw(callback: types.CallbackQuery, db: DatabaseService, state: FSMContext):
    user = await db.get_user(callback.from_user.id)
    
    if not user.is_premium:
        text_lock = "🔒 <b>AKSES TERKUNCI</b>\n\n<i>Hanya akun <b>Premium (Talent Verified)</b> yang bisa mencairkan poin menjadi uang tunai.</i>"
        kb_lock = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 DAFTAR PREMIUM SEKARANG", callback_data="menu_pricing")],
            [InlineKeyboardButton(text="⬅️ Kembali", callback_data="menu_finance")]
        ])
        try:
            await callback.message.edit_caption(caption=text_lock, reply_markup=kb_lock, parse_mode="HTML")
        except:
            pass
        return await callback.answer()
    
    min_wd_rp = 50000 if getattr(user, 'has_withdrawn_before', False) else 20000
    min_wd_poin = int(min_wd_rp / POIN_TO_IDR_RATE)
    
    if user.poin_balance < min_wd_poin:
        text_err = f"⚠️ <b>SALDO TIDAK CUKUP</b>\n\nMinimal penarikan adalah <b>Rp {min_wd_rp:,}</b> ({min_wd_poin:,} Poin).\nTerus balas pesan untuk mengumpulkan poin!"
        kb_err = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali", callback_data="menu_finance")]])
        try:
            await callback.message.edit_caption(caption=text_err, reply_markup=kb_err, parse_mode="HTML")
        except:
            pass
        return await callback.answer()
    
    text = (
        f"💸 <b>PENCAIRAN SALDO</b>\n\n"
        f"Saldo Aktif: <b>{user.poin_balance:,} Poin</b>\n"
        f"Minimal Tarik: <b>{min_wd_poin:,} Poin</b>\n\n"
        f"✍️ <i>Ketik nominal angka <b>POIN</b> yang ingin ditarik (tanpa titik/koma):\n(Gunakan navigasi bawah untuk membatalkan)</i>"
    )
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=None, parse_mode="HTML")
    except:
        pass
    
    await state.set_state(WithdrawState.waiting_amount)
    await callback.answer()


@router.message(WithdrawState.waiting_amount)
async def process_wd_amount(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    user = await db.get_user(message.from_user.id)
    try:
        await message.delete()
    except:
        pass
    
    if not message.text.isdigit():
        err = await message.answer("⚠️ Format Salah! Masukkan angka poin saja.")
        await asyncio.sleep(2)
        try:
            await err.delete()
        except:
            pass
        return
    
    amount_poin = int(message.text)
    min_wd_rp = 50000 if getattr(user, 'has_withdrawn_before', False) else 20000
    min_wd_poin = int(min_wd_rp / POIN_TO_IDR_RATE)
    
    if amount_poin < min_wd_poin or amount_poin > user.poin_balance:
        err = await message.answer(f"⚠️ Nominal tidak valid. Min: {min_wd_poin}, Maks: {user.poin_balance}.")
        await asyncio.sleep(2)
        try:
            await err.delete()
        except:
            pass
        return
    
    amount_rp = int(amount_poin * POIN_TO_IDR_RATE)
    await state.update_data(wd_amount_poin=amount_poin, wd_amount_rp=amount_rp)
    
    kb = [
        [InlineKeyboardButton(text="🔵 DANA", callback_data="wd_wallet_DANA"),
         InlineKeyboardButton(text="🟢 GOPAY", callback_data="wd_wallet_GOPAY")],
        [InlineKeyboardButton(text="🟣 OVO", callback_data="wd_wallet_OVO"),
         InlineKeyboardButton(text="🟠 SHOPEEPAY", callback_data="wd_wallet_SHOPEEPAY")],
        [InlineKeyboardButton(text="🏦 TRANSFER BANK", callback_data="wd_wallet_BANK")],
        [InlineKeyboardButton(text="❌ Batal", callback_data="menu_finance")]
    ]
    
    text = f"✅ <b>KONFIRMASI: Tarik {amount_poin:,} Poin (Rp {amount_rp:,})</b>\n\n👇 <i>Pilih metode pencairan:</i>"
    try:
        await bot.edit_message_caption(chat_id=message.chat.id, message_id=user.anchor_msg_id, caption=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="HTML")
    except:
        pass
    await state.set_state(WithdrawState.waiting_wallet_type)


@router.callback_query(F.data.startswith("wd_wallet_"), WithdrawState.waiting_wallet_type)
async def process_wallet_type(callback: types.CallbackQuery, state: FSMContext):
    wallet_type = callback.data.split("_")[2]
    await state.update_data(wd_wallet_type=wallet_type)
    label = "Nama Bank & No Rekening" if wallet_type == "BANK" else "Nomor Handphone"
    text = f"💳 Metode: <b>{wallet_type}</b>\n\n✍️ Ketik <b>{label}</b> Anda di bawah ini:"
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=None, parse_mode="HTML")
    except:
        pass
    await state.set_state(WithdrawState.waiting_wallet_number)
    await callback.answer()


@router.message(WithdrawState.waiting_wallet_number)
async def process_wallet_number(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    await state.update_data(wd_wallet_number=message.text)
    user = await db.get_user(message.from_user.id)
    try:
        await message.delete()
    except:
        pass
    
    text = "👤 Ketik <b>Nama Lengkap</b> Anda (Sesuai di rekening/e-wallet):"
    try:
        await bot.edit_message_caption(chat_id=message.chat.id, message_id=user.anchor_msg_id, caption=text, reply_markup=None, parse_mode="HTML")
    except:
        pass
    await state.set_state(WithdrawState.waiting_wallet_name)


@router.message(WithdrawState.waiting_wallet_name)
async def process_wallet_name(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    await state.update_data(wd_wallet_name=message.text)
    data = await state.get_data()
    try:
        await message.delete()
    except:
        pass
    
    user_id = message.from_user.id
    trx_id = f"WD-{uuid.uuid4().hex[:6].upper()}"
    user = await db.get_user(user_id)
    
    # Potong poin
    async with db.session_factory() as session:
        u = await session.get(User, user_id)
        u.poin_balance -= data['wd_amount_poin']
        await session.commit()
    
    # Kirim ke grup admin
    admin_text = (
        f"🟡 <b>REQ WITHDRAW BARU</b>\n"
        f"ID: <code>{trx_id}</code>\n"
        f"User: <code>{user_id}</code>\n"
        f"Nominal: <b>Rp {data['wd_amount_rp']:,}</b>\n"
        f"Poin Ditarik: {data['wd_amount_poin']:,}\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"💳 {data['wd_wallet_type']}: <code>{data['wd_wallet_number']}</code>\n"
        f"👤 A/N: {html.escape(data['wd_wallet_name'])}"
    )
    
    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ TANDAI SUDAH DITRANSFER", callback_data=f"wd_confirm_{user_id}_{trx_id}")],
        [InlineKeyboardButton(text="❌ TOLAK & REFUND POIN", callback_data=f"wd_deny_{user_id}_{trx_id}")]
    ])
    
    if FINANCE_GROUP_ID:
        try:
            await bot.send_message(FINANCE_GROUP_ID, admin_text, reply_markup=kb_admin, parse_mode="HTML")
        except:
            pass
    
    text_success = (
        f"✅ <b>PENARIKAN BERHASIL DIAJUKAN!</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        f"ID Tiket: <code>{trx_id}</code>\n"
        f"Status: <b>Menunggu Transfer Admin</b>\n"
        f"Estimasi Cair: Maksimal 24 Jam Kerja.\n\n"
        f"<i>Gunakan navigasi bawah untuk kembali.</i>"
    )
    kb_done = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Dompet", callback_data="menu_finance")]])
    try:
        await bot.edit_message_caption(chat_id=message.chat.id, message_id=user.anchor_msg_id, caption=text_success, reply_markup=kb_done, parse_mode="HTML")
    except:
        pass
    await state.clear()


# ==========================================
# 3. SUB-MENU: REFERRAL LOGIC
# ==========================================
@router.callback_query(F.data == "wallet_referral")
async def show_referral_ui(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    
    async with db.session_factory() as session:
        total_invited_query = await session.execute(select(ReferralTracking).where(ReferralTracking.referrer_id == user_id))
        total_invited = len(total_invited_query.scalars().all())
        
        active_query = await session.execute(select(ReferralTracking).where(
            and_(ReferralTracking.referrer_id == user_id, ReferralTracking.is_active == True)
        ))
        active_users = len(active_query.scalars().all())
    
    text = (
        f"🎁 <b>PROGRAM REFERRAL SULTAN</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"Ajak teman bergabung dan dapatkan <b>Gaji Mingguan Bersama!</b>\n"
        f"Syarat: Temanmu harus aktif klik bot & tidak keluar dari Grup.\n\n"
        f"💸 <b>Sama-sama Untung! Kalian BERDUA akan mendapat:</b>\n"
        f"• Join Awal: <b>Masing-masing +1.000 Poin</b>\n"
        f"• Aktif 7 Hari: <b>Masing-masing +1.000 Poin</b>\n"
        f"• Aktif 14 Hari: <b>Masing-masing +1.000 Poin</b>\n"
        f"• Aktif 21 Hari: <b>Masing-masing +1.000 Poin</b>\n"
        f"• Aktif 28 Hari: <b>Masing-masing +1.000 Poin</b>\n"
        f"Total Maksimal: <b>5.000 Poin per Orang!</b> 💰\n\n"
        f"📊 <b>Statistik Undanganku:</b>\n"
        f"Total Diundang: {total_invited} Orang\n"
        f"Masih Bertahan: {active_users} Orang\n\n"
        f"👇 <b>Link Sakti Kamu:</b> (Tekan untuk menyalin)\n"
        f"<code>{ref_link}</code>\n"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Dompet", callback_data="menu_finance")]])
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except:
        pass
    await callback.answer()

import os
import logging
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import InputMediaPhoto

from services.database import DatabaseService
from utils.ui_manager import UIManager

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")


# ==========================================
# 1. CORE UI RENDERER (DASHBOARD UTAMA)
# ==========================================
async def render_dashboard_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None, force_new: bool = False):
    """Menampilkan dashboard utama dengan navigasi inline"""
    # ========== CLEANUP: Hapus ReplyKeyboard jika ada ==========
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

    # Tentukan kasta
    if user.is_vip_plus:
        kasta = "💎 VIP+"
    elif user.is_vip:
        kasta = "🌟 VIP"
    elif user.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"
    
    dashboard_text = (
        f"👋 Halo, <b>{user.full_name.upper()}</b>!\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👑 Status: <b>{kasta}</b>\n"
        f"💰 Saldo: <b>{user.poin_balance:,} Poin</b>\n"
        f"📍 Lokasi: <b>{user.location_name}</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>"
    )

    unreads = await db.get_all_unread_counts(user_id)
    total_notif = sum(unreads.values())
    
    inline_kb = UIManager.get_dashboard_inline_kb(total_notif)
    
    if callback_id and not force_new:
        media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=dashboard_text, parse_mode="HTML")
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=inline_kb)
            await bot.answer_callback_query(callback_id)
            return True
        except Exception:
            pass

    try:
        sent_message = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=dashboard_text, reply_markup=inline_kb, parse_mode="HTML")
        await db.update_anchor_msg(user_id, sent_message.message_id)
    except Exception as e:
        logging.error(f"Gagal mengirim Dashboard UI: {e}")

    if callback_id:
        try:
            await bot.answer_callback_query(callback_id)
        except:
            pass
        
    return True


# ==========================================
# 2. SUB-MENU RENDERERS (HUB)
# ==========================================
async def render_notification_hub(message_or_callback, db: DatabaseService, bot: Bot, user_id: int):
    """Menampilkan pusat notifikasi"""
    unreads = await db.get_all_unread_counts(user_id)
    text = "🔔 <b>PUSAT NOTIFIKASI</b>\n\nPantau semua interaksi profilmu di sini. Jangan biarkan pesan atau <i>match</i> barumu menunggu terlalu lama!"
    kb = UIManager.get_notification_center_kb(unreads)
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_media(media=media, reply_markup=kb)
    else:
        await message_or_callback.answer_photo(photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")


async def render_account_hub(message_or_callback, db: DatabaseService, bot: Bot, user_id: int):
    """Menampilkan pusat akun"""
    user = await db.get_user(user_id)
    if user.is_vip_plus:
        kasta = "💎 VIP+"
    elif user.is_vip:
        kasta = "🌟 VIP"
    elif user.is_premium:
        kasta = "🎭 PREMIUM"
    else:
        kasta = "👤 FREE"
    
    text = f"⚙️ <b>PUSAT AKUN & STATUS</b>\n\nKelola bagaimana profilmu tampil di <i>Discovery</i> dan pantau sisa kuota harian tier <b>{kasta}</b> kamu hari ini."
    kb = UIManager.get_account_center_kb()
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_media(media=media, reply_markup=kb)
    else:
        await message_or_callback.answer_photo(photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")


async def render_finance_hub(message_or_callback, db: DatabaseService, bot: Bot, user_id: int):
    """Menampilkan pusat keuangan"""
    user = await db.get_user(user_id)
    text = f"💳 <b>DOMPET & REWARD</b>\n\nSaldo Poin: <b>{user.poin_balance:,} Poin</b>\n\nBagikan <i>link</i> referralmu untuk mendapatkan koin tambahan, atau cairkan poinmu menjadi uang tunai (Syarat: Status Premium)."
    kb = UIManager.get_finance_center_kb()
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.edit_media(media=media, reply_markup=kb)
    else:
        await message_or_callback.answer_photo(photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")


# ==========================================
# 3. HANDLERS UTAMA (/start & Command)
# ==========================================
@router.message(CommandStart())
@router.message(Command("dashboard"))
async def command_start_handler(message: types.Message, command: CommandObject = None, db: DatabaseService = None, bot: Bot = None, state: FSMContext = None):
    args = command.args if command else None 
    user_id = message.from_user.id 
    chat_id = message.chat.id

    try:
        await message.delete()
    except:
        pass

    # IRON GATE: Wajib Join Grup & Channel
    from handlers.registration import check_membership, CHANNEL_LINK, GROUP_LINK
    is_joined = await check_membership(bot, user_id)
    if not is_joined:
        text_stop = "<b>STOP! Join Dulu ya Guys!!!</b> ✋\n\nUntuk menjaga kualitas komunitas, kamu wajib bergabung di Channel dan Grup kami sebelum bisa beraksi."
        return await message.answer_photo(photo=BANNER_PHOTO_ID, caption=text_stop, reply_markup=UIManager.get_join_gate_kb(CHANNEL_LINK, GROUP_LINK), parse_mode="HTML")

    user = await db.get_user(user_id)
    if not user:
        if state:
            await state.clear()
        from handlers.registration import RegState
        text_new = "👋 <b>Selamat Datang di PickMe Bot!</b>\n\nMari buat profil singkatmu sekarang!\nSiapa <b>nama panggilanmu(username)</b>? (3-15 karakter)"
        await message.answer(text_new, parse_mode="HTML", reply_markup=types.ReplyKeyboardRemove())
        return await state.set_state(RegState.waiting_nickname)

    # Deep Link Routing (View Profile)
    if args and args.startswith("view_"):
        parts = args.split("_")
        try:
            target_id = int(parts[1])
            origin_type = parts[2] if len(parts) >= 3 else "public"
            from handlers.preview import process_profile_preview
            return await process_profile_preview(message, bot, db, viewer_id=user_id, target_id=target_id, context_source=origin_type)
        except Exception as e:
            logging.error(f"Deep Link Error: {e}")

    await render_dashboard_ui(bot, chat_id, user_id, db, state, force_new=True)


@router.message(Command("notifikasi"))
async def cmd_notifikasi(message: types.Message, db: DatabaseService, bot: Bot):
    try:
        await message.delete()
    except:
        pass
    await render_notification_hub(message, db, bot, message.from_user.id)


@router.message(Command("wallet"))
async def cmd_wallet(message: types.Message, db: DatabaseService, bot: Bot):
    try:
        await message.delete()
    except:
        pass
    await render_finance_hub(message, db, bot, message.from_user.id)


# ==========================================
# 4. CALLBACK ROUTER (Navigasi Inline)
# ==========================================
@router.callback_query(F.data == "check_join_start")
async def verify_join_start(callback: types.CallbackQuery, bot: Bot, db: DatabaseService, state: FSMContext):
    from handlers.registration import check_membership
    if await check_membership(bot, callback.from_user.id):
        try:
            await callback.message.delete()
        except:
            pass
        await render_dashboard_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, force_new=True)
    else:
        await callback.answer("❌ Kamu belum join Channel/Grup!", show_alert=True)


@router.callback_query(F.data == "back_to_dashboard")
async def back_to_dashboard_callback(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    await render_dashboard_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


@router.callback_query(F.data == "menu_notifications")
async def cb_menu_notifications(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_notification_hub(callback, db, bot, callback.from_user.id)


@router.callback_query(F.data == "menu_account")
async def cb_menu_account(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_account_hub(callback, db, bot, callback.from_user.id)


@router.callback_query(F.data == "menu_finance")
async def cb_menu_finance(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_finance_hub(callback, db, bot, callback.from_user.id)


@router.callback_query(F.data == "menu_feed")
async def cb_menu_feed(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    from handlers.feed import render_feed_ui
    await render_feed_ui(bot, callback.message.chat.id, callback.from_user.id, db, state)
    await callback.answer()


@router.callback_query(F.data == "menu_discovery")
async def cb_menu_discovery(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    from handlers.discovery import render_discovery_ui
    await render_discovery_ui(bot, callback.message.chat.id, callback.from_user.id, db, state)
    await callback.answer()
    

@router.callback_query(F.data == "menu_pricing")
async def cb_menu_pricing(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    from handlers.pricing import render_pricing_main_ui
    await render_pricing_main_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)

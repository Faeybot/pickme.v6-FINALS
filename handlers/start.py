import os
import logging
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import InputMediaPhoto, ReplyKeyboardRemove

from services.database import DatabaseService
from utils.ui_manager import UIManager

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")


# ==========================================
# 1. FUNGSI BERSIHKAN LAYAR
# ==========================================
async def cleanup_chat_history(chat_id: int, user_id: int, bot: Bot, db: DatabaseService):
    """Menghapus semua pesan yang ada di layar user saat ini"""
    user = await db.get_user(user_id)
    if not user:
        return
    
    # Hapus anchor message jika ada
    if user.anchor_msg_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=user.anchor_msg_id)
            logging.info(f"✅ Anchor message deleted for user {user_id}")
        except Exception as e:
            logging.warning(f"Failed to delete anchor message for user {user_id}: {e}")
        
        # Reset anchor di database
        await db.update_anchor_msg(user_id, None)
    
    # Hapus ReplyKeyboard jika ada
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass


# ==========================================
# 2. NOTIFICATION HUB
# ==========================================
async def render_notification_hub(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    """Menampilkan pusat notifikasi"""
    from aiogram.types import InputMediaPhoto
    
    user = await db.get_user(user_id)
    if not user:
        return
    
    await db.push_nav(user_id, "notifications")
    
    unreads = await db.get_all_unread_counts(user_id)
    
    text = (
        "🔔 <b>PUSAT NOTIFIKASI</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━━━━━</code>\n"
        "Pantau semua interaksi profilmu di sini.\n"
        "Jangan biarkan pesan atau match barumu menunggu terlalu lama!"
    )
    
    kb = UIManager.get_notification_center_kb(unreads)
    
    photo_to_use = user.photo_id if user.photo_id else BANNER_PHOTO_ID
    media = InputMediaPhoto(media=photo_to_use, caption=text, parse_mode="HTML")
    
    # Hapus anchor lama jika ada
    if user.anchor_msg_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=user.anchor_msg_id)
        except:
            pass
        await db.update_anchor_msg(user_id, None)
    
    # Kirim pesan baru
    sent = await bot.send_photo(chat_id=chat_id, photo=photo_to_use, caption=text, reply_markup=kb, parse_mode="HTML")
    await db.update_anchor_msg(user_id, sent.message_id)
    
    if callback_id:
        try:
            await bot.answer_callback_query(callback_id)
        except:
            pass


# ==========================================
# 3. CORE UI RENDERER (DASHBOARD UTAMA)
# ==========================================
async def render_dashboard_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None, force_new: bool = False):
    """Menampilkan dashboard utama dengan navigasi inline - AUTO RESET & CLEANUP"""
    
    # ========== 🔥 FORCE RESET FSM ==========
    if state:
        try:
            await state.clear()
            logging.info(f"✅ FSM cleared for user {user_id}")
        except Exception as e:
            logging.error(f"Failed to clear FSM: {e}")
    
    # ========== 🔥 BERSIHKAN LAYAR & HAPUS ANCHOR LAMA ==========
    await cleanup_chat_history(chat_id, user_id, bot, db)
    
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
    
    # Gunakan foto profil user jika ada, fallback ke banner default
    photo_to_use = user.photo_id if user.photo_id else BANNER_PHOTO_ID
    
    # Kirim pesan baru (layar sudah bersih, anchor sudah dihapus)
    sent_message = await bot.send_photo(chat_id=chat_id, photo=photo_to_use, caption=dashboard_text, reply_markup=inline_kb, parse_mode="HTML")
    await db.update_anchor_msg(user_id, sent_message.message_id)
    
    if callback_id:
        try:
            await bot.answer_callback_query(callback_id)
        except:
            pass
        
    return True


# ==========================================
# 4. HANDLERS UTAMA (/start, /dashboard, tombol Dashboard)
# ==========================================
@router.message(CommandStart())
@router.message(Command("dashboard"))
@router.message(F.text == "🏠 Dashboard")
@router.message(F.text == "📱 DASHBOARD UTAMA")
async def command_start_handler(message: types.Message, command: CommandObject = None, db: DatabaseService = None, bot: Bot = None, state: FSMContext = None):
    args = command.args if command else None 
    user_id = message.from_user.id 
    chat_id = message.chat.id

    # ========== 🔥 FORCE RESET FSM ==========
    if state:
        try:
            await state.clear()
            logging.info(f"✅ FSM cleared for user {user_id} on /start")
        except Exception as e:
            logging.error(f"Failed to clear FSM: {e}")

    # Hapus pesan perintah user
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


# ==========================================
# 5. HANDLER: VERIFIKASI JOIN (IRON GATE)
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


# ==========================================
# 6. HANDLER: KEMBALI KE DASHBOARD (DARI MANAPUN)
# ==========================================
@router.callback_query(F.data == "back_to_dashboard")
async def back_to_dashboard_callback(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    """Kembali ke dashboard - DENGAN RESET FSM & CLEANUP TOTAL"""
    
    # ========== 🔥 FORCE RESET FSM ==========
    if state:
        try:
            await state.clear()
            logging.info(f"✅ FSM cleared for user {callback.from_user.id} on back_to_dashboard")
        except Exception as e:
            logging.error(f"Failed to clear FSM: {e}")
    
    await render_dashboard_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


# ==========================================
# 7. GERBANG KE MODUL LAIN
# ==========================================
@router.callback_query(F.data == "menu_account")
async def cb_menu_account(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    """GERBANG: Arahkan ke Account Hub di account.py"""
    # Reset FSM sebelum pindah
    if state:
        await state.clear()
    from handlers.account import render_account_hub
    await render_account_hub(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


@router.callback_query(F.data == "menu_finance")
async def cb_menu_finance(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    """GERBANG: Arahkan ke Wallet Hub di wallet.py"""
    if state:
        await state.clear()
    from handlers.wallet import render_wallet_hub
    await render_wallet_hub(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


@router.callback_query(F.data == "menu_notifications")
async def cb_menu_notifications(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """GERBANG: Arahkan ke Notification Hub"""
    await render_notification_hub(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)


@router.callback_query(F.data == "menu_feed")
async def cb_menu_feed(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    """GERBANG: Arahkan ke Feed Menu"""
    if state:
        await state.clear()
    from handlers.feed import render_feed_ui
    await render_feed_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


@router.callback_query(F.data == "menu_discovery")
async def cb_menu_discovery(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    """GERBANG: Arahkan ke Discovery Menu"""
    if state:
        await state.clear()
    from handlers.discovery import render_discovery_ui
    await render_discovery_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)


@router.callback_query(F.data == "menu_pricing")
async def cb_menu_pricing(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """GERBANG: Arahkan ke Pricing Store"""
    from handlers.pricing import render_pricing_main_ui
    await render_pricing_main_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)


# ==========================================
# 8. COMMAND VIA TELEGRAM MENU BIRU
# ==========================================
@router.message(Command("notifikasi"))
async def cmd_notifikasi(message: types.Message, db: DatabaseService, bot: Bot):
    try:
        await message.delete()
    except:
        pass
    await render_notification_hub(bot, message.chat.id, message.from_user.id, db)


@router.message(Command("wallet"))
async def cmd_wallet(message: types.Message, db: DatabaseService, bot: Bot, state: FSMContext):
    try:
        await message.delete()
    except:
        pass
    if state:
        await state.clear()
    from handlers.wallet import render_wallet_hub
    await render_wallet_hub(bot, message.chat.id, message.from_user.id, db, state)


@router.message(Command("account"))
async def cmd_account(message: types.Message, db: DatabaseService, bot: Bot, state: FSMContext):
    try:
        await message.delete()
    except:
        pass
    if state:
        await state.clear()
    from handlers.account import render_account_hub
    await render_account_hub(bot, message.chat.id, message.from_user.id, db, state)


# ==========================================
# 9. HANDLER UNTUK CALLBACK YANG TIDAK DIKENAL (DEBUG)
# ==========================================
@router.callback_query()
async def handle_unknown_callback(callback: types.CallbackQuery):
    """Handler untuk callback yang tidak dikenal"""
    logging.warning(f"⚠️ Unknown callback: {callback.data} from user {callback.from_user.id}")
    await callback.answer("⚠️ Menu sedang diperbaiki. Silakan coba lagi nanti.", show_alert=True)

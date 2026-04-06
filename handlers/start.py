import os
import logging
import asyncio
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import InputMediaPhoto

from services.database import DatabaseService, User
from utils.ui_manager import UIManager 

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")

# ==========================================
# 1. CORE UI RENDERER (DASHBOARD UTAMA)
# ==========================================
async def render_dashboard_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, state: FSMContext, callback_id: str = None, force_new: bool = False):
    # Bersihkan state apa pun saat kembali ke Dashboard
    if state: await state.clear()
    
    user = await db.get_user(user_id)
    if not user: return False

    kasta = "💎 VIP+" if user.is_vip_plus else "🌟 VIP" if user.is_vip else "🎭 PREMIUM" if user.is_premium else "👤 FREE"
    
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
    
    # Pendekatan render sederhana (Kirim ulang jika force_new, edit jika dari callback)
    if callback_id and not force_new:
        media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=dashboard_text, parse_mode="HTML")
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=inline_kb)
            await bot.answer_callback_query(callback_id)
            return True
        except Exception:
            pass # Lanjut kirim pesan baru jika edit gagal

    try:
        sent_message = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=dashboard_text, reply_markup=inline_kb, parse_mode="HTML")
        await db.update_anchor_msg(user_id, sent_message.message_id)
    except Exception as e:
        logging.error(f"Gagal mengirim Dashboard UI: {e}")

    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
        
    return True

# ==========================================
# 2. SUB-MENU RENDERERS (HUB)
# ==========================================
async def render_notification_hub(message_or_callback, db: DatabaseService, bot: Bot, user_id: int):
    unreads = await db.get_all_unread_counts(user_id)
    text = "🔔 <b>PUSAT NOTIFIKASI</b>\n\nPantau semua interaksi profilmu di sini. Jangan biarkan pesan atau <i>match</i> barumu menunggu terlalu lama!"
    kb = UIManager.get_notification_center_kb(unreads)
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    # Ambil user untuk anchor
    user = await db.get_user(user_id)
    if isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_media(media=media, reply_markup=kb)
            await message_or_callback.answer()
            return
        except Exception as e:
            logging.warning(f"Edit notif hub gagal: {e}")
            # fallback: kirim baru
            if user and user.anchor_msg_id:
                try:
                    await bot.delete_message(message_or_callback.message.chat.id, user.anchor_msg_id)
                except:
                    pass
                await db.update_anchor_msg(user_id, None)
            sent = await bot.send_photo(message_or_callback.message.chat.id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
            await message_or_callback.answer()
    else:
        await message_or_callback.answer_photo(photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")

async def render_account_hub(message_or_callback, db: DatabaseService, bot: Bot, user_id: int):
    user = await db.get_user(user_id)
    kasta = "💎 VIP+" if user.is_vip_plus else "🌟 VIP" if user.is_vip else "🎭 PREMIUM" if user.is_premium else "👤 FREE"
    text = f"⚙️ <b>PUSAT AKUN & STATUS</b>\n\nKelola bagaimana profilmu tampil di <i>Discovery</i> dan pantau sisa kuota harian tier <b>{kasta}</b> kamu hari ini."
    kb = UIManager.get_account_center_kb()
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    if isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_media(media=media, reply_markup=kb)
            await message_or_callback.answer()
            return
        except Exception as e:
            logging.warning(f"Edit account hub gagal: {e}")
            # fallback: kirim baru
            if user and user.anchor_msg_id:
                try:
                    await bot.delete_message(message_or_callback.message.chat.id, user.anchor_msg_id)
                except:
                    pass
                await db.update_anchor_msg(user_id, None)
            sent = await bot.send_photo(message_or_callback.message.chat.id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
            await message_or_callback.answer()
    else:
        await message_or_callback.answer_photo(photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")

async def render_finance_hub(message_or_callback, db: DatabaseService, bot: Bot, user_id: int):
    user = await db.get_user(user_id)
    text = f"💳 <b>DOMPET & REWARD</b>\n\nSaldo Poin: <b>{user.poin_balance:,} Poin</b>\n\nBagikan <i>link</i> referralmu untuk mendapatkan koin tambahan, atau cairkan poinmu menjadi uang tunai (Syarat: Status Premium)."
    kb = UIManager.get_finance_center_kb()
    
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    
    if isinstance(message_or_callback, types.CallbackQuery):
        try:
            await message_or_callback.message.edit_media(media=media, reply_markup=kb)
            await message_or_callback.answer()
            return
        except Exception as e:
            logging.warning(f"Edit finance hub gagal: {e}")
            if user and user.anchor_msg_id:
                try:
                    await bot.delete_message(message_or_callback.message.chat.id, user.anchor_msg_id)
                except:
                    pass
                await db.update_anchor_msg(user_id, None)
            sent = await bot.send_photo(message_or_callback.message.chat.id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
            await message_or_callback.answer()
    else:
        await message_or_callback.answer_photo(photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")

# ==========================================
# 3. HANDLERS UTAMA (/start & Menu Biru)
# ==========================================
@router.message(CommandStart())
@router.message(Command("dashboard"))
async def command_start_handler(message: types.Message, command: CommandObject = None, db: DatabaseService = None, bot: Bot = None, state: FSMContext = None):
    args = command.args if command else None 
    user_id = message.from_user.id 
    chat_id = message.chat.id

    try: await message.delete()
    except: pass

    # IRON GATE: Wajib Join Grup & Channel
    from handlers.registration import check_membership, CHANNEL_LINK, GROUP_LINK
    is_joined = await check_membership(bot, user_id)
    if not is_joined:
        text_stop = "<b>STOP! Join Dulu ya Guys!!!</b> ✋\n\nUntuk menjaga kualitas komunitas, kamu wajib bergabung di Channel dan Grup kami sebelum bisa beraksi."
        return await message.answer_photo(photo=BANNER_PHOTO_ID, caption=text_stop, reply_markup=UIManager.get_join_gate_kb(CHANNEL_LINK, GROUP_LINK), parse_mode="HTML")

    user = await db.get_user(user_id)
    if not user:
        if state: await state.clear()
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
            pass

    await render_dashboard_ui(bot, chat_id, user_id, db, state, force_new=True)

# Handler Menu Biru Lainya
@router.message(Command("notifikasi"))
async def cmd_notifikasi(message: types.Message, db: DatabaseService, bot: Bot):
    try: await message.delete()
    except: pass
    await render_notification_hub(message, db, bot, message.from_user.id)

@router.message(Command("finance"))
async def cmd_finance(message: types.Message, db: DatabaseService, bot: Bot):
    try: await message.delete()
    except: pass
    await render_finance_hub(message, db, bot, message.from_user.id)

# ==========================================
# TAMBAHAN: HANDLER UNTUK COMMAND MENU BIRU YANG HILANG
# ==========================================
@router.message(Command("feed"))
async def cmd_feed(message: types.Message, db: DatabaseService, bot: Bot, state: FSMContext):
    try: await message.delete()
    except: pass
    from handlers.feed import render_feed_ui
    await render_feed_ui(bot, message.chat.id, message.from_user.id, db, state)

@router.message(Command("discovery"))
async def cmd_discovery(message: types.Message, db: DatabaseService, bot: Bot, state: FSMContext):
    try: await message.delete()
    except: pass
    from handlers.discovery import render_discovery_ui
    await render_discovery_ui(bot, message.chat.id, message.from_user.id, db, state)

@router.message(Command("inbox"))
async def cmd_inbox(message: types.Message, db: DatabaseService, bot: Bot):
    try: await message.delete()
    except: pass
    from handlers.inbox import render_inbox_list
    await render_inbox_list(bot, message.chat.id, message.from_user.id, db, page=0)

@router.message(Command("wallet"))
async def cmd_wallet(message: types.Message, db: DatabaseService, bot: Bot, state: FSMContext):
    try: await message.delete()
    except: pass
    from handlers.wallet import render_wallet_hub
    await render_wallet_hub(bot, message.chat.id, message.from_user.id, db, state)

@router.message(Command("account"))
async def cmd_account(message: types.Message, db: DatabaseService, bot: Bot, state: FSMContext):
    try: await message.delete()
    except: pass
    from handlers.account import render_account_hub
    await render_account_hub(bot, message.chat.id, message.from_user.id, db, state)

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    try: await message.delete()
    except: pass
    from handlers.help import cmd_help as help_handler
    await help_handler(message)

# ==========================================
# 4. CALLBACK ROUTER (Navigasi Inline)
# ==========================================
@router.callback_query(F.data == "check_join_start")
async def verify_join_start(callback: types.CallbackQuery, bot: Bot, db: DatabaseService, state: FSMContext):
    from handlers.registration import check_membership
    if await check_membership(bot, callback.from_user.id):
        try: await callback.message.delete()
        except: pass
        await render_dashboard_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, force_new=True)
    else:
        await callback.answer("❌ Kamu belum join Channel/Grup!", show_alert=True)

@router.callback_query(F.data == "back_to_dashboard")
async def back_to_dashboard_callback(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    await render_dashboard_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)

# Tangkap Klik Tombol Hub dari Dashboard
@router.callback_query(F.data == "menu_notifications")
async def cb_menu_notifications(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_notification_hub(callback, db, bot, callback.from_user.id)

@router.callback_query(F.data == "menu_account")
async def cb_menu_account(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_account_hub(callback, db, bot, callback.from_user.id)

@router.callback_query(F.data == "menu_finance")
async def cb_menu_finance(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_finance_hub(callback, db, bot, callback.from_user.id)

# Tambahkan di bagian CALLBACK ROUTER (setelah cb_menu_finance atau di akhir)
@router.callback_query(F.data == "menu_profile")
async def cb_menu_profile(callback: types.CallbackQuery, db: DatabaseService, bot: Bot, state: FSMContext):
    from handlers.account import render_full_profile_ui
    await render_full_profile_ui(bot, callback.message.chat.id, callback.from_user.id, db, state, callback.id)

@router.callback_query(F.data == "menu_status")
async def cb_menu_status(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    from handlers.status import render_status_ui   # Perbaikan: import dari status.py
    await render_status_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)

# Rute Langsung ke Modul (Feed, Discovery, dll)
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

# ==========================================
# TEMPORARY: RESET ALL USERS (TEST)
# ==========================================
@router.message(Command("restart_dashboard_history_all_user"))
async def temp_reset_all(message: types.Message, db: DatabaseService):
    await message.answer("🔧 Command diterima. Memproses...")
    
    # Hanya owner yang bisa
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    if message.from_user.id != OWNER_ID:
        await message.answer("❌ Anda bukan owner.")
        return
    
    try:
        async with db.session_factory() as session:
            from sqlalchemy import update
            from services.database import User
            await session.execute(update(User).values(anchor_msg_id=None, nav_stack=["dashboard"]))
            await session.commit()
        await message.answer("✅ Berhasil reset semua user.")
    except Exception as e:
        await message.answer(f"❌ Error: {e}")

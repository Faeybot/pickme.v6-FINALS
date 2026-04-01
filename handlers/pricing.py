import os
import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command 
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()

FINANCE_GROUP_ID = os.getenv("FINANCE_GROUP_ID") 
CATALOG_PHOTO_ID = os.getenv("BANNER_PHOTO_ID") # Disamakan dengan environment agar tidak hardcode

# ==========================================
# 1. CORE UI RENDERER: PRICING STORE
# ==========================================
async def render_pricing_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    user = await db.get_user(user_id)
    if not user: return False

    await db.push_nav(user_id, "pricing")

    text = (
        "🛒 <b>PICKME STORE - KATALOG RESMI</b>\n"
        f"<code>{'—' * 22}</code>\n"
        "Buka fitur sakti dan jadilah Sultan di PickMe!\n\n"
        "💡 <b>TRIAL GRATIS TERSEDIA:</b>\n"
        "Selama masa integrasi Payment Gateway, semua paket di bawah ini bisa kamu coba secara <b>GRATIS selama 7 Hari</b>!\n\n"
        "<i>Silakan pilih paket untuk melihat detail fitur.</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌟 PAKET VIP", callback_data="p_info_vip")],
        [InlineKeyboardButton(text="💎 PAKET VIP+ (Sultan Eksklusif)", callback_data="p_info_vipplus")],
        [
            InlineKeyboardButton(text="🎭 TALENT PREMIUM", callback_data="p_info_talent"),
            InlineKeyboardButton(text="🚀 TIKET BOOST", callback_data="p_info_boost")
        ]
    ])
    
    media = InputMediaPhoto(media=CATALOG_PHOTO_ID, caption=text, parse_mode="HTML")

    try: await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
    except Exception: pass
    
    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
    return True

@router.callback_query(F.data == "menu_pricing")
async def show_pricing_store(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_pricing_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)

# ==========================================
# 2. POP-UP INFO TRIAL & REQUEST KE ADMIN
# ==========================================
@router.callback_query(F.data.startswith("p_info_"))
async def show_trial_offer(callback: types.CallbackQuery, db: DatabaseService):
    package_type = callback.data.split("_")[2] # vip, vipplus, talent, boost
    
    # Teks disesuaikan berdasarkan paket yang diklik
    pkg_name = package_type.upper()
    text = (
        f"💎 <b>PROGRAM {pkg_name} JACKPOT (TRIAL)</b>\n"
        f"<code>{'—' * 22}</code>\n"
        f"Kabar gembira! Kami memberikan akses <b>{pkg_name} EKSKLUSIF</b> secara gratis untuk uji coba 7 Hari.\n\n"
        "🎁 <b>Ajukan akses sekarang juga! Tim Admin akan segera memproses permintaanmu.</b>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📩 AJUKAN TRIAL {pkg_name} (GRATIS)", callback_data=f"req_trial_{package_type}")]
    ])
    
    try: await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    except: pass
    await callback.answer()

@router.callback_query(F.data.startswith("req_trial_"))
async def send_to_admin_group(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    package_type = callback.data.split("_")[2]
    user_id = callback.from_user.id
    username = f"@{callback.from_user.username}" if callback.from_user.username else "No Username"
    
    text_success = (
        "✅ <b>PENGAJUAN BERHASIL!</b>\n\n"
        f"Permintaan akses <b>{package_type.upper()} Trial</b> kamu sudah masuk ke tim Finance.\n"
        "Mohon tunggu notifikasi selanjutnya. Akunmu akan aktif otomatis jika disetujui Admin.\n\n"
        "<i>Gunakan tombol navigasi di bawah untuk kembali.</i>"
    )
    
    try: await callback.message.edit_caption(caption=text_success, reply_markup=None, parse_mode="HTML")
    except: pass

    admin_text = (
        f"🎁 <b>REQUEST TRIAL (BETA)</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"User: <b>{callback.from_user.full_name}</b>\n"
        f"ID: <code>{user_id}</code>\n"
        f"Username: {username}\n"
        f"Paket: <b>{package_type.upper()} (7 HARI TRIAL)</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👇 Admin silakan berikan akses:"
    )

    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ SETUJUI {package_type.upper()}", callback_data=f"trial_apv_{user_id}_{package_type}")],
        [InlineKeyboardButton(text="❌ TOLAK", callback_data=f"trial_rej_{user_id}")]
    ])

    if FINANCE_GROUP_ID:
        try: await bot.send_message(FINANCE_GROUP_ID, admin_text, reply_markup=kb_admin, parse_mode="HTML")
        except Exception as e: logging.error(f"Gagal kirim ke finance: {e}")
            
    await callback.answer("Pengajuan Terkirim!", show_alert=True)

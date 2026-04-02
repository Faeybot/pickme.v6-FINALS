import os
import logging
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardRemove
from services.database import DatabaseService

router = Router()

FINANCE_GROUP_ID = os.getenv("FINANCE_GROUP_ID")

# Banner untuk setiap kategori
BANNER_STORE_MAIN = os.getenv("BANNER_STORE_MAIN", os.getenv("BANNER_PHOTO_ID"))
BANNER_PREMIUM = os.getenv("BANNER_PREMIUM", BANNER_STORE_MAIN)
BANNER_VIP = os.getenv("BANNER_VIP", BANNER_STORE_MAIN)
BANNER_VIPPLUS = os.getenv("BANNER_VIPPLUS", BANNER_STORE_MAIN)
BANNER_EXTRA = os.getenv("BANNER_EXTRA", BANNER_STORE_MAIN)


# ==========================================
# 1. RENDERER UTAMA: ETALASE (MENU AWAL)
# ==========================================
async def render_pricing_main_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    """Menu utama Pricing Store"""
    
    # Cleanup ReplyKeyboard
    try:
        temp_msg = await bot.send_message(chat_id, "🔄", reply_markup=ReplyKeyboardRemove())
        await bot.delete_message(chat_id, temp_msg.message_id)
    except:
        pass
    
    user = await db.get_user(user_id)
    if not user:
        return False
    
    await db.push_nav(user_id, "pricing_main")
    
    text = (
        "🛒 <b>PICKME STORE - PUSAT UPGRADE</b>\n"
        f"<code>{'—' * 30}</code>\n"
        "Tingkatkan pengalamanmu, temukan lebih banyak kecocokan, dan dapatkan penghasilan!\n\n"
        "👇 <i>Pilih paket yang ingin kamu lihat:</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 AKUN PREMIUM (Verifikasi WD)", callback_data="p_detail_premium")],
        [InlineKeyboardButton(text="🌟 PAKET VIP (Sultan Reguler)", callback_data="p_detail_vip")],
        [InlineKeyboardButton(text="💎 PAKET VIP+ (Sultan Eksklusif)", callback_data="p_detail_vipplus")],
        [InlineKeyboardButton(text="🚀 EXTRA KUOTA & TIKET BOOST", callback_data="p_detail_extra")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Dashboard", callback_data="back_to_dashboard")]
    ])
    
    media = InputMediaPhoto(media=BANNER_STORE_MAIN, caption=text, parse_mode="HTML")
    
    if callback_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
            await bot.answer_callback_query(callback_id)
        except:
            pass
    else:
        try:
            sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_STORE_MAIN, caption=text, reply_markup=kb, parse_mode="HTML")
            await db.update_anchor_msg(user_id, sent.message_id)
        except Exception as e:
            logging.error(f"Gagal render pricing main: {e}")
    
    return True


@router.callback_query(F.data == "menu_pricing")
async def show_pricing_store(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_pricing_main_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)


# ==========================================
# 2. DETAIL PAKET: PREMIUM
# ==========================================
@router.callback_query(F.data == "p_detail_premium")
async def show_premium_detail(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """Menampilkan detail paket Premium"""
    user = await db.get_user(callback.from_user.id)
    
    text = (
        "🎭 <b>AKUN PREMIUM (VERIFIKASI WITHDRAW)</b>\n"
        f"<code>{'—' * 30}</code>\n"
        "<b>Harga: Rp 10.000 (Sekali bayar - Seumur Hidup)</b>\n\n"
        
        "✨ <b>KEUNTUNGAN PREMIUM:</b>\n"
        "✅ <b>Bisa Cairkan Poin (Withdraw)</b>\n"
        "   - Syarat wajib untuk mencairkan poin ke e-wallet\n"
        "   - 10 Poin = Rp 1 (minimal WD Rp 20.000)\n\n"
        "✅ <b>Kenaikan Kuota Dasar:</b>\n"
        "   - Posting Teks Feed: 3x/hari (naik dari 2)\n"
        "   - Posting Foto Feed: 1x/hari (naik dari 0)\n"
        "   - Swipe Jodoh: 20x/hari (naik dari 10)\n\n"
        "✅ <b>Lencana Premium Eksklusif</b>\n"
        "   - Tampil lebih dipercaya di Discovery\n\n"
        "💡 <i>Premium adalah kunci untuk menguangkan poin hasil interaksimu!</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 BELI PREMIUM (Rp 10.000)", callback_data="buy_premium")],
        [InlineKeyboardButton(text="🎁 REQUEST TRIAL PREMIUM 7 HARI", callback_data="req_trial_premium")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]
    ])
    
    media = InputMediaPhoto(media=BANNER_PREMIUM, caption=text, parse_mode="HTML")
    
    try:
        await bot.edit_message_media(chat_id=callback.message.chat.id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
    except:
        pass
    await callback.answer()


# ==========================================
# 3. DETAIL PAKET: VIP
# ==========================================
@router.callback_query(F.data == "p_detail_vip")
async def show_vip_detail(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """Menampilkan detail paket VIP"""
    user = await db.get_user(callback.from_user.id)
    
    text = (
        "🌟 <b>PAKET VIP (SULTAN REGULER)</b>\n"
        f"<code>{'—' * 30}</code>\n"
        "<b>💳 PILIHAN DURASI:</b>\n"
        "• 7 Hari  → Rp 10.000\n"
        "• 30 Hari → Rp 30.000\n"
        "• 90 Hari → Rp 100.000\n\n"
        
        "✨ <b>KEUNTUNGAN VIP:</b>\n"
        "🔓 <b>Buka Profil (Unmask)</b>\n"
        "   - Bisa lihat profil orang yang like/view profilmu\n"
        "   - Kuota: 10x/hari\n\n"
        "💌 <b>Kirim Pesan (DM)</b>\n"
        "   - Kirim pesan langsung ke siapa saja\n"
        "   - Kuota: 10x/hari\n\n"
        "📸 <b>Kuota Feed Maksimal</b>\n"
        "   - Posting Teks: 10x/hari\n"
        "   - Posting Foto: 5x/hari\n\n"
        "🔍 <b>Swipe Jodoh</b>\n"
        "   - Kuota: 30x/hari\n\n"
        "🌟 <b>Lencana VIP Eksklusif</b>\n"
        "   - Sorotan profil khusus di Discovery\n\n"
        "💡 <i>50% dari pendapatan VIP akan dibagikan ke user aktif dalam bentuk Poin!</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 VIP 7 HARI (Rp 10.000)", callback_data="buy_vip_7")],
        [InlineKeyboardButton(text="🛒 VIP 30 HARI (Rp 30.000)", callback_data="buy_vip_30")],
        [InlineKeyboardButton(text="🛒 VIP 90 HARI (Rp 100.000)", callback_data="buy_vip_90")],
        [InlineKeyboardButton(text="🎁 REQUEST TRIAL VIP 7 HARI", callback_data="req_trial_vip")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]
    ])
    
    media = InputMediaPhoto(media=BANNER_VIP, caption=text, parse_mode="HTML")
    
    try:
        await bot.edit_message_media(chat_id=callback.message.chat.id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
    except:
        pass
    await callback.answer()


# ==========================================
# 4. DETAIL PAKET: VIP+
# ==========================================
@router.callback_query(F.data == "p_detail_vipplus")
async def show_vipplus_detail(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """Menampilkan detail paket VIP+"""
    user = await db.get_user(callback.from_user.id)
    
    text = (
        "💎 <b>PAKET VIP+ (SULTAN EKSKLUSIF)</b>\n"
        f"<code>{'—' * 30}</code>\n"
        "<b>💳 PILIHAN DURASI:</b>\n"
        "• 7 Hari  → Rp 30.000\n"
        "• 30 Hari → Rp 100.000\n"
        "• 90 Hari → Rp 250.000\n\n"
        
        "✨ <b>KEUNTUNGAN VIP+ (SEMUA KEUNTUNGAN VIP + FITUR EKSKLUSIF):</b>\n"
        "🎭 <b>BONGKAR IDENTITAS ANONIM (UNMASK)</b>\n"
        "   - Satu-satunya kasta yang bisa lihat identitas anonim!\n"
        "   - Kuota: 10x/hari\n"
        "   - Target dapat +500 Poin (kompensasi dibuka paksa)\n"
        "   - Target dapat +500 Poin lagi jika membalas\n\n"
        "💌 <b>Kirim Pesan (DM)</b>\n"
        "   - Kuota: 10x/hari (prioritas tinggi)\n\n"
        "🔍 <b>Swipe Jodoh</b>\n"
        "   - Kuota: 50x/hari (terbanyak!)\n\n"
        "🚀 <b>GRATIS TIKET BOOST</b>\n"
        "   - Dapat 1 Tiket Boost setiap hari Senin\n\n"
        "📸 <b>Kuota Feed Maksimal</b>\n"
        "   - Posting Teks: 10x/hari\n"
        "   - Posting Foto: 5x/hari\n\n"
        "💎 <b>Lencana VIP+ Eksklusif</b>\n"
        "   - Mahkota khusus di samping namamu\n\n"
        "💡 <i>50% dari pendapatan VIP+ akan dibagikan ke user aktif dalam bentuk Poin!</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 VIP+ 7 HARI (Rp 30.000)", callback_data="buy_vipplus_7")],
        [InlineKeyboardButton(text="🛒 VIP+ 30 HARI (Rp 100.000)", callback_data="buy_vipplus_30")],
        [InlineKeyboardButton(text="🛒 VIP+ 90 HARI (Rp 250.000)", callback_data="buy_vipplus_90")],
        [InlineKeyboardButton(text="🎁 REQUEST TRIAL VIP+ 7 HARI", callback_data="req_trial_vipplus")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]
    ])
    
    media = InputMediaPhoto(media=BANNER_VIPPLUS, caption=text, parse_mode="HTML")
    
    try:
        await bot.edit_message_media(chat_id=callback.message.chat.id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
    except:
        pass
    await callback.answer()


# ==========================================
# 5. DETAIL PAKET: EXTRA (BOOST & DM)
# ==========================================
@router.callback_query(F.data == "p_detail_extra")
async def show_extra_detail(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """Menampilkan detail paket Extra (Boost & DM)"""
    user = await db.get_user(callback.from_user.id)
    
    text = (
        "🚀 <b>EXTRA KUOTA & TIKET BOOST</b>\n"
        f"<code>{'—' * 30}</code>\n"
        "Butuh dorongan ekstra tanpa harus langganan? Ini solusinya!\n\n"
        
        "🎫 <b>TIKET BOOST (Prioritas Feed)</b>\n"
        "   - Buat profilmu tampil di puncak Channel Feed\n"
        "   - Otomatis muncul di Discovery semua orang\n"
        "   - 🛒 5 Boost  → Rp 10.000\n"
        "   - 🛒 10 Boost → Rp 15.000\n"
        "   - 🛒 20 Boost → Rp 25.000\n\n"
        
        "📦 <b>EXTRA KUOTA DM (Pesan Langsung)</b>\n"
        "   - Tambahan kuota kirim pesan (tidak hangus)\n"
        "   - 🛒 10 DM → Rp 10.000\n"
        "   - 🛒 20 DM → Rp 15.000\n"
        "   - 🛒 30 DM → Rp 20.000\n\n"
        
        "💡 <i>Kuota extra tidak akan hangus sampai kamu gunakan!</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 5 BOOST (Rp 10.000)", callback_data="buy_boost_5"),
         InlineKeyboardButton(text="🎫 10 BOOST (Rp 15.000)", callback_data="buy_boost_10"),
         InlineKeyboardButton(text="🎫 20 BOOST (Rp 25.000)", callback_data="buy_boost_20")],
        [InlineKeyboardButton(text="💬 10 DM (Rp 10.000)", callback_data="buy_dm_10"),
         InlineKeyboardButton(text="💬 20 DM (Rp 15.000)", callback_data="buy_dm_20"),
         InlineKeyboardButton(text="💬 30 DM (Rp 20.000)", callback_data="buy_dm_30")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]
    ])
    
    media = InputMediaPhoto(media=BANNER_EXTRA, caption=text, parse_mode="HTML")
    
    try:
        await bot.edit_message_media(chat_id=callback.message.chat.id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
    except:
        pass
    await callback.answer()


# ==========================================
# 6. HANDLER: REQUEST TRIAL (KIRIM KE ADMIN)
# ==========================================
@router.callback_query(F.data.startswith("req_trial_"))
async def send_trial_request(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """Mengirim request trial ke grup admin finance"""
    package_type = callback.data.split("_")[2]  # premium, vip, vipplus
    user_id = callback.from_user.id
    user = await db.get_user(user_id)
    username = f"@{callback.from_user.username}" if callback.from_user.username else "No Username"
    
    # Pesan sukses ke user
    text_success = (
        "✅ <b>PENGAJUAN TRIAL BERHASIL!</b>\n\n"
        f"Permintaan akses <b>{package_type.upper()} Trial 7 Hari</b> kamu sudah masuk ke tim Finance.\n"
        "Mohon tunggu notifikasi selanjutnya. Akunmu akan aktif otomatis jika disetujui Admin.\n\n"
        "<i>Gunakan tombol di bawah untuk kembali.</i>"
    )
    
    kb_back = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]
    ])
    
    try:
        await callback.message.edit_caption(caption=text_success, reply_markup=kb_back, parse_mode="HTML")
    except:
        pass
    
    # Kirim ke grup admin finance
    admin_text = (
        f"🎁 <b>REQUEST TRIAL</b>\n"
        f"<code>{'—' * 25}</code>\n"
        f"User: <b>{callback.from_user.full_name}</b>\n"
        f"ID: <code>{user_id}</code>\n"
        f"Username: {username}\n"
        f"Paket: <b>{package_type.upper()} (7 HARI TRIAL)</b>\n"
        f"<code>{'—' * 25}</code>\n"
        f"👇 Admin silakan berikan akses:"
    )
    
    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ SETUJUI {package_type.upper()}", callback_data=f"trial_apv_{user_id}_{package_type}")],
        [InlineKeyboardButton(text="❌ TOLAK", callback_data=f"trial_rej_{user_id}")]
    ])
    
    if FINANCE_GROUP_ID:
        try:
            await bot.send_message(FINANCE_GROUP_ID, admin_text, reply_markup=kb_admin, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Gagal kirim ke grup finance: {e}")
    
    await callback.answer("Pengajuan Terkirim!", show_alert=True)


# ==========================================
# 7. HANDLER: PEMBELIAN (DUMMY - MIDTRANS INTEGRASI NANTI)
# ==========================================
@router.callback_query(F.data.startswith("buy_"))
async def handle_purchase(callback: types.CallbackQuery):
    """Handler untuk pembelian (sementara dummy, nanti diintegrasi dengan Midtrans)"""
    item = callback.data.split("_")[1]  # premium, vip, vipplus, boost, dm
    
    text = (
        "🛒 <b>PEMBELAIAN SEDANG DALAM PENGEMBANGAN</b>\n\n"
        "Fitur pembayaran online sedang kami siapkan.\n"
        "Saat ini, kamu bisa mengajukan <b>Trial 7 Hari</b> terlebih dahulu.\n\n"
        f"Paket yang dipilih: <code>{callback.data}</code>\n\n"
        "<i>Kami akan segera mengaktifkan pembayaran melalui Midtrans.</i>"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Kembali", callback_data="menu_pricing")]
    ])
    
    await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

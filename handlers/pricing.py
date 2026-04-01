import os
import logging
from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from services.database import DatabaseService

router = Router()

FINANCE_GROUP_ID = os.getenv("FINANCE_GROUP_ID") 

# --- BANNER IMAGES (Bisa diatur di .env nanti) ---
BANNER_STORE_MAIN = os.getenv("BANNER_STORE_MAIN", os.getenv("BANNER_PHOTO_ID"))
BANNER_PREMIUM = os.getenv("BANNER_PREMIUM", BANNER_STORE_MAIN)
BANNER_VIP = os.getenv("BANNER_VIP", BANNER_STORE_MAIN)
BANNER_VIPPLUS = os.getenv("BANNER_VIPPLUS", BANNER_STORE_MAIN)
BANNER_EXTRA = os.getenv("BANNER_EXTRA", BANNER_STORE_MAIN)


# ==========================================
# 1. CORE RENDERER: MASTER MENU (ETALASE UTAMA)
# ==========================================
async def render_pricing_main_ui(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    user = await db.get_user(user_id)
    if not user: return False

    await db.push_nav(user_id, "pricing_main")

    text = (
        "🛒 <b>PICKME STORE - PUSAT UPGRADE</b>\n"
        f"<code>{'—' * 22}</code>\n"
        "Tingkatkan pengalamanmu, temukan lebih banyak kecocokan, dan cairkan penghasilanmu!\n\n"
        "👇 <i>Pilih layanan yang ingin kamu jelajahi:</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 UPGRADE AKUN PREMIUM (Verified)", callback_data="p_detail_premium")],
        [InlineKeyboardButton(text="🌟 UPGRADE LANGGANAN VIP", callback_data="p_detail_vip")],
        [InlineKeyboardButton(text="💎 UPGRADE LANGGANAN VIP+ (Sultan)", callback_data="p_detail_vipplus")],
        [InlineKeyboardButton(text="🚀 EXTRA KUOTA & TIKET BOOST", callback_data="p_detail_extra")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Akun", callback_data="menu_account")]
    ])
    
    media = InputMediaPhoto(media=BANNER_STORE_MAIN, caption=text, parse_mode="HTML")

    try: await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
    except Exception: pass
    
    if callback_id:
        try: await bot.answer_callback_query(callback_id)
        except: pass
    return True

@router.callback_query(F.data == "menu_pricing")
async def show_pricing_store(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    await render_pricing_main_ui(bot, callback.message.chat.id, callback.from_user.id, db, callback.id)


# ==========================================
# 2. RENDERER: DETAIL PAKET (SUB-MENU)
# ==========================================
@router.callback_query(F.data.startswith("p_detail_"))
async def show_package_detail(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    package_type = callback.data.split("_")[2] # premium, vip, vipplus, extra
    user = await db.get_user(callback.from_user.id)
    
    # 1. Konten Premium (Verifikasi & WD)
    if package_type == "premium":
        photo_id = BANNER_PREMIUM
        text = (
            "🎭 <b>AKUN PREMIUM (TALENT VERIFIED)</b>\n"
            f"<code>{'—' * 22}</code>\n"
            "Ubah waktu luangmu menjadi uang saku! Ini adalah syarat mutlak untuk mencairkan pendapatan Poinmu.\n\n"
            "✨ <b>Keuntungan Permanen:</b>\n"
            "✅ <b>Buka Fitur Withdraw (WD):</b> Cairkan poin ke DANA/OVO/Bank.\n"
            "✅ <b>Lencana Premium:</b> Tampil lebih dipercaya di Discovery.\n"
            "✅ <b>Kenaikan Kuota Dasar:</b> Jatah harian posting Feed meningkat.\n"
            "🎁 <b>Bonus Langsung:</b> Tambahan kuota posting foto Feed!\n\n"
            "<i>(Sekali bayar untuk seumur hidup)</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ AJUKAN TRIAL PREMIUM (7 HARI)", callback_data="req_trial_premium")],
            [InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]
        ])

    # 2. Konten VIP Reguler
    elif package_type == "vip":
        photo_id = BANNER_VIP
        text = (
            "🌟 <b>LANGGANAN VIP (SULTAN)</b>\n"
            f"<code>{'—' * 22}</code>\n"
            "Bebas batasan! Nikmati eksposur maksimal dan temukan jodoh tanpa hambatan kuota harian.\n\n"
            "✨ <b>Keuntungan VIP:</b>\n"
            "🔓 <b>Bongkar Identitas (Unmask):</b> 10x sehari bongkar siapa yang menyukaimu.\n"
            "💌 <b>Kirim Pesan Brutal:</b> 10x kuota DM harian.\n"
            "📸 <b>Feed Dominan:</b> 10 Teks & 5 Foto setiap hari.\n"
            "🌟 <b>Lencana VIP:</b> Sorotan profil khusus di Discovery.\n\n"
            "<i>(Berlaku per 30 Hari)</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ AJUKAN TRIAL VIP (7 HARI)", callback_data="req_trial_vip")],
            [InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]
        ])

    # 3. Konten VIP+ (Tertinggi)
    elif package_type == "vipplus":
        photo_id = BANNER_VIPPLUS
        text = (
            "💎 <b>LANGGANAN VIP+ (SULTAN EKSKLUSIF)</b>\n"
            f"<code>{'—' * 22}</code>\n"
            "Kasta tertinggi di PickMe. Didesain khusus untuk kamu yang tidak suka menunggu dan ingin hasil instan.\n\n"
            "✨ <b>Keuntungan Super VIP+:</b>\n"
            "🎭 <b>Bongkar Anonim:</b> Satu-satunya kasta yang bisa melihat siapa pengirim menfess rahasia!\n"
            "🚀 <b>Gratis Tiket Boost:</b> Dapat 1 Tiket Boost setiap hari Senin.\n"
            "💌 <b>Kuota Tertinggi:</b> Semua keuntungan VIP dengan prioritas trafik jaringan utama.\n"
            "💎 <b>Lencana VIP+:</b> Mahkota eksklusif di samping namamu.\n\n"
            "<i>(Berlaku per 30 Hari)</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ AJUKAN TRIAL VIP+ (7 HARI)", callback_data="req_trial_vipplus")],
            [InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]
        ])

    # 4. Konten Extra Kuota & Boost
    elif package_type == "extra":
        photo_id = BANNER_EXTRA
        text = (
            "🚀 <b>EXTRA KUOTA & TIKET BOOST</b>\n"
            f"<code>{'—' * 22}</code>\n"
            "Hanya butuh dorongan sedikit tanpa harus langganan bulanan? Ini solusinya!\n\n"
            "🎫 <b>Tiket Boost (Prioritas Feed):</b>\n"
            "Buat profilmu tampil di urutan paling atas di layar Discovery semua orang selama 30 menit. Auto banjir Match!\n\n"
            "📦 <b>Kuota Extra Permanen:</b>\n"
            "Kehabisan jatah DM hari ini? Beli kuota eceran yang tidak akan hangus sampai digunakan."
        )
        # Tombol ini bisa dihubungkan ke modul boost.py Anda nantinya
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 BELI TIKET BOOST", callback_data="dummy_buy_boost")],
            [InlineKeyboardButton(text="🛒 BELI KUOTA DM", callback_data="dummy_buy_quota")],
            [InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]
        ])

    else:
        return await callback.answer("Paket tidak ditemukan.", show_alert=True)

    # Eksekusi Render Detail
    media = InputMediaPhoto(media=photo_id, caption=text, parse_mode="HTML")
    try: await bot.edit_message_media(chat_id=callback.message.chat.id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
    except Exception: pass
    await callback.answer()


# ==========================================
# 3. KIRIM PENGAJUAN KE GRUP ADMIN FINANCE
# ==========================================
@router.callback_query(F.data.startswith("req_trial_"))
async def send_to_admin_group(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    package_type = callback.data.split("_")[2] # premium, vip, vipplus
    user_id = callback.from_user.id
    username = f"@{callback.from_user.username}" if callback.from_user.username else "No Username"
    
    text_success = (
        "✅ <b>PENGAJUAN BERHASIL!</b>\n\n"
        f"Permintaan akses <b>{package_type.upper()} Trial</b> kamu sudah masuk ke tim Finance.\n"
        "Mohon tunggu notifikasi selanjutnya. Akunmu akan aktif otomatis jika disetujui Admin.\n\n"
        "<i>Gunakan tombol navigasi di bawah untuk kembali.</i>"
    )
    
    kb_back = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Kembali ke Etalase", callback_data="menu_pricing")]])

    try: await callback.message.edit_caption(caption=text_success, reply_markup=kb_back, parse_mode="HTML")
    except: pass

    admin_text = (
        f"🎁 <b>REQUEST TRIAL (BETA)</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"User: <b>{callback.from_user.full_name}</b>\n"
        f"ID: <code>{user_id}</code>\n"
        f"Username: {username}\n"
        f"Paket Diajukan: <b>{package_type.upper()} (7 HARI TRIAL)</b>\n"
        f"<code>━━━━━━━━━━━━━━━━━━</code>\n"
        f"👇 Admin silakan berikan akses:"
    )

    kb_admin = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ SETUJUI {package_type.upper()}", callback_data=f"trial_apv_{user_id}_{package_type}")],
        [InlineKeyboardButton(text="❌ TOLAK", callback_data=f"trial_rej_{user_id}")]
    ])

    if FINANCE_GROUP_ID:
        try: await bot.send_message(FINANCE_GROUP_ID, admin_text, reply_markup=kb_admin, parse_mode="HTML")
        except Exception as e: logging.error(f"Gagal kirim ke grup finance: {e}")
            
    await callback.answer("Pengajuan Terkirim!", show_alert=True)

# (Dummy handler untuk tombol eceran)
@router.callback_query(F.data.startswith("dummy_buy_"))
async def dummy_retail_buy(callback: types.CallbackQuery):
    await callback.answer("Etalase Eceran sedang disiapkan oleh Developer...", show_alert=True)

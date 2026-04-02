"""
REGISTRASI USER BARU PICKME BOT
File ini mengatur alur pendaftaran user baru:
1. Cek keanggotaan grup/channel (Iron Gate)
2. Setujui aturan (Rules)
3. Input nama panggilan
4. Input tanggal lahir (perhitungan umur otomatis)
5. Pilih gender
6. Pilih minat (maksimal 3)
7. Pilih lokasi (manual atau GPS)
8. Upload foto utama (wajib) + foto tambahan (opsional)
9. Input bio
10. Simpan ke database + bonus referral jika ada
"""

import re
import asyncio
import os
import html
import logging
import datetime
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, 
    InlineKeyboardMarkup, InlineKeyboardButton
)
from geopy.geocoders import Nominatim
from services.database import DatabaseService, User, PointLog, ReferralTracking

# Inisialisasi router
router = Router()

# Inisialisasi geocoder untuk konversi GPS ke nama kota
geolocator = Nominatim(user_agent="pickme_bot_v6_final")


# ==========================================
# 1. KONFIGURASI DARI ENVIRONMENT VARIABLES
# ==========================================
def get_clean_id(key: str):
    """Membersihkan ID dari format yang mungkin mengandung quote atau @"""
    val = os.getenv(key)
    if not val:
        return None
    val = str(val).strip().replace("'", "").replace('"', '')
    if val.startswith("-") or val.isdigit():
        try:
            return int(val)
        except:
            return val
    if not val.startswith("@"):
        return f"@{val}"
    return val


# Ambil konfigurasi dari .env
ADMIN_LOG_CHANNEL = get_clean_id("ADMIN_LOG_CHANNEL")      # Channel untuk log user baru
REG_MODERATION_GROUP = get_clean_id("REG_MODERATION_GROUP") # Grup untuk moderasi foto
GROUP_ID = get_clean_id("GROUP_ID")                         # ID Grup wajib join
CHANNEL_ID = get_clean_id("CHANNEL_ID")                     # ID Channel wajib join

GROUP_LINK = os.getenv("GROUP_LINK", "").replace("@", "").replace("https://t.me/", "")
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "").replace("@", "").replace("https://t.me/", "")

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")              # Foto banner untuk tampilan
DEFAULT_ANON_PHOTO_ID = os.getenv("DEFAULT_ANON_PHOTO_ID", BANNER_PHOTO_ID)


# ==========================================
# 2. DATA KOTA (15 KOTA BESAR INDONESIA)
# ==========================================
CITY_DATA = {
    "city_medan": {"name": "Medan", "lat": 3.5952, "lng": 98.6722, "tag": "MEDAN"},
    "city_plm": {"name": "Palembang", "lat": -2.9761, "lng": 104.7754, "tag": "PALEMBANG"},
    "city_lamp": {"name": "Lampung", "lat": -5.3971, "lng": 105.2668, "tag": "LAMPUNG"},
    "city_btm": {"name": "Batam", "lat": 1.1301, "lng": 104.0529, "tag": "BATAM"},
    "city_jkt": {"name": "Jakarta", "lat": -6.2088, "lng": 106.8456, "tag": "JAKARTA"},
    "city_bks": {"name": "Bekasi", "lat": -6.2383, "lng": 106.9756, "tag": "BEKASI"},
    "city_bgr": {"name": "Bogor", "lat": -6.5971, "lng": 106.8060, "tag": "BOGOR"},
    "city_bdg": {"name": "Bandung", "lat": -6.9175, "lng": 107.6191, "tag": "BANDUNG"},
    "city_jgj": {"name": "Jogja", "lat": -7.7956, "lng": 110.3695, "tag": "JOGJA"},
    "city_smr": {"name": "Semarang", "lat": -6.9667, "lng": 110.4167, "tag": "SEMARANG"},
    "city_slo": {"name": "Solo", "lat": -7.5707, "lng": 110.8214, "tag": "SOLO"},
    "city_sby": {"name": "Surabaya", "lat": -7.2575, "lng": 112.7521, "tag": "SURABAYA"},
    "city_mlg": {"name": "Malang", "lat": -7.9666, "lng": 112.6326, "tag": "MALANG"},
    "city_dps": {"name": "Denpasar", "lat": -8.6705, "lng": 115.2126, "tag": "BALI"},
    "city_lmbk": {"name": "Lombok", "lat": -8.5833, "lng": 116.1167, "tag": "LOMBOK"},
}


# ==========================================
# 3. DATA MINAT (7 KATEGORI)
# ==========================================
INTERESTS = [
    ("🔞 Adult Content", "int_adult"),
    ("🔥 Flirt & Dirty Talk", "int_flirt"),
    ("❤️ Relationship", "int_rel"),
    ("🤝 Networking", "int_net"),
    ("🎮 Gaming", "int_game"),
    ("✈️ Traveling", "int_travel"),
    ("☕ Coffee & Chill", "int_coffee"),
]


# ==========================================
# 4. STATE MANAGEMENT (FSM)
# ==========================================
class RegState(StatesGroup):
    waiting_rules = State()        # Menunggu konfirmasi aturan
    waiting_nickname = State()     # Menunggu input nama panggilan
    waiting_birth_month = State()  # Menunggu pilih bulan lahir
    waiting_birth_day = State()    # Menunggu pilih tanggal lahir
    waiting_birth_year = State()   # Menunggu input tahun lahir
    waiting_gender = State()       # Menunggu pilih gender
    waiting_interests = State()    # Menunggu pilih minat
    waiting_location = State()     # Menunggu pilih lokasi
    waiting_photo_1 = State()      # Menunggu upload foto utama
    waiting_photo_2 = State()      # Menunggu upload foto ke-2 (opsional)
    waiting_photo_3 = State()      # Menunggu upload foto ke-3 (opsional)
    waiting_about = State()        # Menunggu input bio


# ==========================================
# 5. HELPER: KEYBOARD TANGGAL LAHIR
# ==========================================
def get_month_kb():
    """Keyboard untuk memilih bulan (Jan - Des)"""
    months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agt", "Sep", "Okt", "Nov", "Des"]
    kb, row = [], []
    for i in range(12):
        row.append(InlineKeyboardButton(text=months[i], callback_data=f"reg_month_{i+1}"))
        if len(row) == 3:
            kb.append(row)
            row = []
    return InlineKeyboardMarkup(inline_keyboard=kb)


def get_day_kb(month: int):
    """Keyboard untuk memilih tanggal berdasarkan bulan"""
    # Tentukan jumlah hari dalam bulan
    days_in_month = 31
    if month == 2:
        days_in_month = 29  # Biarkan user mengatur tahun nanti
    elif month in [4, 6, 9, 11]:
        days_in_month = 30

    kb, row = [], []
    for d in range(1, days_in_month + 1):
        row.append(InlineKeyboardButton(text=str(d), callback_data=f"reg_day_{d}"))
        if len(row) == 5:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ==========================================
# 6. HELPER: KEYBOARD MINAT
# ==========================================
async def show_interest_keyboard(message: types.Message, selected: list, edit: bool = False):
    """Menampilkan keyboard minat dengan status checklist"""
    kb_list = []
    for text, code in INTERESTS:
        prefix = "✅ " if code in selected else ""
        kb_list.append([InlineKeyboardButton(text=f"{prefix}{text}", callback_data=code)])
    
    # Tombol SIMPAN hanya muncul jika sudah memilih minimal 1 minat
    if len(selected) > 0:
        kb_list.append([InlineKeyboardButton(text="➡️ SIMPAN & LANJUT", callback_data="save_interests")])
    
    text = "Pilih <b>Minat & Keinginanmu</b> (Maksimal 3):"
    
    if edit:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list), parse_mode="HTML")
    else:
        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list), parse_mode="HTML")


# ==========================================
# 7. HELPER: KEYBOARD LOKASI
# ==========================================
def get_location_keyboard():
    """Membuat keyboard kota (15 kota) dengan 3 kolom"""
    kb_list, temp_row = [], []
    for code, info in CITY_DATA.items():
        temp_row.append(InlineKeyboardButton(text=info["name"], callback_data=code))
        if len(temp_row) == 3:
            kb_list.append(temp_row)
            temp_row = []
    if temp_row:
        kb_list.append(temp_row)
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# ==========================================
# 8. HELPER: CEK MEMBERSHIP (IRON GATE)
# ==========================================
async def check_membership(bot: Bot, user_id: int) -> bool:
    """
    Memeriksa apakah user sudah join channel dan grup wajib.
    Return True jika sudah join keduanya.
    """
    try:
        # Cek channel
        member_ch = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        stat_ch = getattr(member_ch.status, "value", str(member_ch.status)).lower()
        if stat_ch in ['left', 'kicked', 'banned']:
            return False
        
        # Cek grup
        member_gr = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        stat_gr = getattr(member_gr.status, "value", str(member_gr.status)).lower()
        if stat_gr in ['left', 'kicked', 'banned']:
            return False
        
        return True
    except Exception as e:
        logging.error(f"❌ Error check_membership: {e}")
        return False


# ==========================================
# 9. HELPER: TAMPILAN ATURAN
# ==========================================
async def show_rules_handler(message: types.Message):
    """Menampilkan aturan komunitas PickMe"""
    text_rules = (
        "📜 <b>PICKME COMMUNITY RULES</b>\n"
        f"<code>{'—' * 20}</code>\n"
        "1. Minimal usia pendaftaran adalah <b>18 Tahun</b>.\n"
        "2. Dilarang melakukan penipuan, spam, atau SARA.\n"
        "3. Konten 18+ 🔞 DIPERBOLEHKAN selama berlabel dan konsensual.\n"
        "4. PickMe tidak bertanggung jawab atas transaksi di luar bot.\n"
        "5. Pelanggaran aturan berakibat <b>Banned Permanen</b>.\n\n"
        "<b>DISCLAIMER:</b> Dengan melanjutkan, Anda menyatakan telah dewasa (18+)."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ SAYA SETUJU & LANJUT", callback_data="accept_rules")]])
    
    try:
        await message.answer_photo(photo=BANNER_PHOTO_ID, caption=text_rules, reply_markup=kb, parse_mode="HTML")
    except:
        await message.answer(text_rules, reply_markup=kb, parse_mode="HTML")


# ==========================================
# 10. START REGISTRASI (DIPANGGIL DARI START.PY)
# ==========================================
async def start_registration(message: types.Message, state: FSMContext):
    """Memulai proses registrasi user baru"""
    await show_rules_handler(message)
    await state.set_state(RegState.waiting_rules)


# ==========================================
# 11. HANDLER: KONFIRMASI ATURAN
# ==========================================
@router.callback_query(F.data == "accept_rules", RegState.waiting_rules)
async def rules_accepted(callback: types.CallbackQuery, state: FSMContext):
    """User menyetujui aturan, lanjut ke input nama"""
    await callback.message.answer(
        "Siapa <b>nama panggilanmu (username)</b>?\n"
        "<i>Minimal 3 karakter, maksimal 15 karakter.</i>",
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_nickname)
    await callback.answer()


# ==========================================
# 12. HANDLER: INPUT NAMA PANGGILAN
# ==========================================
@router.message(RegState.waiting_nickname)
async def process_name(message: types.Message, state: FSMContext):
    """Memproses input nama panggilan"""
    name = message.text.strip() if message.text else ""
    
    # Validasi panjang nama
    if not (3 <= len(name) <= 15):
        return await message.answer("⚠️ Nama harus 3-15 karakter. Coba lagi:")
    
    await state.update_data(nickname=name)
    
    text = (
        f"Halo {name}! Silakan pilih <b>Bulan Lahirmu</b>:\n\n"
        "<i>Data ulang tahun tidak akan ditampilkan ke publik, "
        "ini hanya digunakan untuk menghitung usiamu.</i>"
    )
    await message.answer(text, reply_markup=get_month_kb(), parse_mode="HTML")
    await state.set_state(RegState.waiting_birth_month)


# ==========================================
# 13. HANDLER: PILIH BULAN LAHIR
# ==========================================
@router.callback_query(F.data.startswith("reg_month_"), RegState.waiting_birth_month)
async def process_month(callback: types.CallbackQuery, state: FSMContext):
    """Memproses pilihan bulan lahir"""
    month = int(callback.data.split("_")[2])
    await state.update_data(birth_month=month)
    
    await callback.message.edit_text(
        "Pilih <b>Tanggal Lahirmu</b>:",
        reply_markup=get_day_kb(month),
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_birth_day)
    await callback.answer()


# ==========================================
# 14. HANDLER: PILIH TANGGAL LAHIR
# ==========================================
@router.callback_query(F.data.startswith("reg_day_"), RegState.waiting_birth_day)
async def process_day(callback: types.CallbackQuery, state: FSMContext):
    """Memproses pilihan tanggal lahir"""
    day = int(callback.data.split("_")[2])
    await state.update_data(birth_day=day)
    
    await callback.message.edit_text(
        "Terakhir, balas pesan ini dengan <b>Tahun Lahirmu</b> (4 angka).\n"
        "Contoh: <code>2002</code>",
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_birth_year)
    await callback.answer()


# ==========================================
# 15. HANDLER: INPUT TAHUN LAHIR & HITUNG UMUR
# ==========================================
@router.message(RegState.waiting_birth_year)
async def process_year(message: types.Message, state: FSMContext):
    """Memproses input tahun lahir dan menghitung umur"""
    year_str = message.text.strip()
    
    # Validasi format tahun
    if not year_str.isdigit() or len(year_str) != 4:
        return await message.answer("⚠️ Masukkan 4 angka tahun lahir. Contoh: 2002")
    
    year = int(year_str)
    data = await state.get_data()
    month = data['birth_month']
    day = data['birth_day']
    
    # Validasi tanggal (misal 31 Februari)
    try:
        dob = datetime.date(year, month, day)
    except ValueError:
        return await message.answer("⚠️ Tanggal lahir tidak valid. Silakan tekan /start untuk mengulang.")
    
    # Hitung umur
    today = datetime.date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    
    # Validasi umur minimal 18 tahun
    if age < 18:
        await state.clear()
        return await message.answer("❌ Maaf, PickMe hanya untuk user berusia 18 tahun ke atas.")
    
    # Validasi umur maksimal 60 tahun
    if age > 60:
        await state.clear()
        return await message.answer("⚠️ Usia maksimal pendaftaran adalah 60 tahun.")
    
    # Simpan data umur
    await state.update_data(age=age, dob_str=dob.strftime("%Y-%m-%d"))
    
    # Tampilkan keyboard gender (ReplyKeyboard sementara)
    kb_gender = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Pria"), KeyboardButton(text="Wanita")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"✅ Usiamu tercatat: <b>{age} Tahun</b>.\n\nApa jenis kelaminmu?",
        reply_markup=kb_gender,
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_gender)


# ==========================================
# 16. HANDLER: PILIH GENDER
# ==========================================
@router.message(RegState.waiting_gender, F.text.in_(["Pria", "Wanita"]))
async def process_gender(message: types.Message, state: FSMContext):
    """Memproses pilihan gender dan lanjut ke pemilihan minat"""
    # Hapus ReplyKeyboard gender
    await message.answer("🕒", reply_markup=ReplyKeyboardRemove())
    
    await state.update_data(gender=message.text, selected_interests=[])
    await show_interest_keyboard(message, [])
    await state.set_state(RegState.waiting_interests)


# ==========================================
# 17. HANDLER: PILIH MINAT (TOGGLE)
# ==========================================
@router.callback_query(F.data.startswith("int_"), RegState.waiting_interests)
async def handle_interest_click(callback: types.CallbackQuery, state: FSMContext):
    """Menangani klik tombol minat (toggle selection)"""
    data = await state.get_data()
    selected = data.get("selected_interests", [])
    code = callback.data
    
    if code in selected:
        selected.remove(code)
    elif len(selected) < 3:
        selected.append(code)
    else:
        return await callback.answer("Maksimal 3 pilihan!", show_alert=True)
    
    await state.update_data(selected_interests=selected)
    await show_interest_keyboard(callback.message, selected, edit=True)
    await callback.answer()


# ==========================================
# 18. HANDLER: SIMPAN MINAT & LANJUT KE LOKASI
# ==========================================
@router.callback_query(F.data == "save_interests", RegState.waiting_interests)
async def save_interests(callback: types.CallbackQuery, state: FSMContext):
    """Menyimpan pilihan minat dan lanjut ke pemilihan lokasi"""
    # Tampilkan keyboard kota
    location_kb = get_location_keyboard()
    
    # Tombol GPS di keyboard bawah (ReplyKeyboard)
    gps_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Kirim Lokasi (GPS)", request_location=True)]],
        resize_keyboard=True
    )
    
    text = (
        "📍 <b>PENGATURAN LOKASI</b>\n\n"
        "Pilih kota domisilimu dari menu di bawah,\n"
        "atau gunakan deteksi GPS otomatis dengan tombol di bawah layar."
    )
    
    await callback.message.answer(text, reply_markup=location_kb, parse_mode="HTML")
    await callback.message.answer(
        "Tombol GPS telah disiapkan di bawah layar 👇",
        reply_markup=gps_kb
    )
    await state.set_state(RegState.waiting_location)
    await callback.answer()


# ==========================================
# 19. HANDLER: PILIH KOTA MANUAL
# ==========================================
@router.callback_query(F.data.startswith("city_"), RegState.waiting_location)
async def handle_manual_city(callback: types.CallbackQuery, state: FSMContext):
    """Memproses pilihan kota dari keyboard inline"""
    city_info = CITY_DATA.get(callback.data)
    if not city_info:
        return await callback.answer("Gagal memilih lokasi.", show_alert=True)
    
    # Simpan data lokasi
    await state.update_data(
        latitude=city_info["lat"],
        longitude=city_info["lng"],
        city=city_info["name"],
        city_hashtag=f"#{city_info['tag']}"
    )
    
    # Hapus keyboard GPS
    try:
        temp_msg = await callback.message.answer("🔄", reply_markup=ReplyKeyboardRemove())
        await callback.bot.delete_message(callback.message.chat.id, temp_msg.message_id)
    except:
        pass
    
    await callback.message.answer(
        f"✅ Lokasi: <b>{city_info['name']}</b>\n\n"
        "Sekarang kirim <b>Foto Utama</b> (wajib):",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_photo_1)
    await callback.answer()


# ==========================================
# 20. HANDLER: KIRIM LOKASI GPS
# ==========================================
@router.message(RegState.waiting_location, F.location)
async def process_location(message: types.Message, state: FSMContext):
    """Memproses lokasi dari GPS user"""
    lat = message.location.latitude
    lon = message.location.longitude
    
    # Konversi GPS ke nama kota (opsional)
    city = "Unknown"
    try:
        loop = asyncio.get_event_loop()
        loc = await loop.run_in_executor(None, lambda: geolocator.reverse((lat, lon), timeout=10))
        if loc and loc.raw.get('address'):
            city = loc.raw['address'].get('city') or loc.raw['address'].get('town') or "Unknown"
    except:
        pass
    
    # Simpan data lokasi
    await state.update_data(
        latitude=lat,
        longitude=lon,
        city=city,
        city_hashtag=f"#{city.replace(' ', '').upper()}"
    )
    
    # Hapus keyboard GPS
    try:
        temp_msg = await message.answer("🔄", reply_markup=ReplyKeyboardRemove())
        await message.bot.delete_message(message.chat.id, temp_msg.message_id)
    except:
        pass
    
    await message.answer(
        f"📍 Kota: {city}\n\n"
        "Sekarang kirim <b>Foto Utama</b> (wajib):",
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_photo_1)


# ==========================================
# 21. HANDLER: UPLOAD FOTO UTAMA
# ==========================================
@router.message(RegState.waiting_photo_1, F.photo)
async def handle_photo_1(message: types.Message, state: FSMContext):
    """Menyimpan foto utama (wajib)"""
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_1=photo_id)
    
    # Tombol Skip untuk foto ke-2
    kb_skip = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Skip (Opsional)", callback_data="skip_photo")]
    ])
    
    await message.answer(
        "📸 Foto utama disimpan!\n\n"
        "Kirim <b>Foto ke-2</b> (opsional, maksimal 2 foto tambahan):",
        reply_markup=kb_skip,
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_photo_2)


# ==========================================
# 22. HANDLER: UPLOAD FOTO KE-2
# ==========================================
@router.message(RegState.waiting_photo_2, F.photo)
async def handle_photo_2(message: types.Message, state: FSMContext):
    """Menyimpan foto ke-2 (opsional)"""
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_2=photo_id)
    
    kb_skip = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Skip (Opsional)", callback_data="skip_photo")]
    ])
    
    await message.answer(
        "📸 Foto ke-2 disimpan!\n\n"
        "Kirim <b>Foto ke-3</b> (opsional, maksimal 2 foto tambahan):",
        reply_markup=kb_skip,
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_photo_3)


# ==========================================
# 23. HANDLER: UPLOAD FOTO KE-3
# ==========================================
@router.message(RegState.waiting_photo_3, F.photo)
async def handle_photo_3(message: types.Message, state: FSMContext):
    """Menyimpan foto ke-3 (opsional)"""
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_3=photo_id)
    
    await message.answer(
        "✅ Selesai!\n\n"
        "Terakhir, tulis <b>Bio singkatmu</b> (minimal 10 karakter):",
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_about)


# ==========================================
# 24. HANDLER: SKIP FOTO TAMBAHAN
# ==========================================
@router.callback_query(F.data == "skip_photo")
async def skip_photo(callback: types.CallbackQuery, state: FSMContext):
    """Melewati upload foto tambahan"""
    current_state = await state.get_state()
    
    if current_state == RegState.waiting_photo_2:
        await callback.message.answer("⏭️ Foto ke-2 dilewati.")
    elif current_state == RegState.waiting_photo_3:
        await callback.message.answer("⏭️ Foto ke-3 dilewati.")
    
    await callback.message.answer(
        "📝 Sekarang tulis <b>Bio singkatmu</b> (minimal 10 karakter):",
        parse_mode="HTML"
    )
    await state.set_state(RegState.waiting_about)
    await callback.answer()


# ==========================================
# 25. HANDLER: INPUT BIO & FINISH REGISTRASI
# ==========================================
@router.message(RegState.waiting_about)
async def finish_reg(message: types.Message, state: FSMContext, db: DatabaseService, bot: Bot):
    """Menyelesaikan registrasi dan menyimpan ke database"""
    bio = message.text.strip() if message.text else ""
    
    # Validasi bio minimal 10 karakter
    if len(bio) < 10:
        return await message.answer("⚠️ Bio minimal 10 karakter. Coba lagi:")
    
    # Ambil semua data dari state
    data = await state.get_data()
    user_id = message.from_user.id
    
    # Format data untuk database
    interests_str = ",".join(data['selected_interests'])
    extra_photos = []
    if 'photo_2' in data:
        extra_photos.append(data['photo_2'])
    if 'photo_3' in data:
        extra_photos.append(data['photo_3'])
    
    # Cek apakah ada referral
    referrer_id = data.get('referrer_id')
    poin_awal = 1000 if referrer_id else 0
    
    # Format tanggal lahir untuk database
    try:
        dob_db = datetime.datetime.strptime(data['dob_str'], "%Y-%m-%d")
    except:
        dob_db = None
    
    try:
        async with db.session_factory() as session:
            # Buat user baru
            new_user = User(
                id=user_id,
                full_name=data['nickname'],
                age=data['age'],
                birth_date=dob_db,
                gender=data['gender'],
                interests=interests_str,
                latitude=data['latitude'],
                longitude=data['longitude'],
                location_name=data['city'],
                city_hashtag=data['city_hashtag'],
                bio=bio,
                photo_id=data['photo_1'],
                extra_photos=extra_photos,
                
                # Saldo awal (bonus referral jika ada)
                poin_balance=poin_awal,
                
                # Kuota default untuk FREE user
                daily_feed_text_quota=2,
                daily_feed_photo_quota=0,
                daily_message_quota=0,
                daily_open_profile_quota=0,
                daily_unmask_quota=0,
                daily_swipe_quota=10,
                daily_swipe_count=0,
                
                # Navigation
                nav_stack=["dashboard"],
                
                # Timestamp
                last_active_at=datetime.datetime.utcnow()
            )
            session.add(new_user)
            
            # PROSES REFERRAL (jika ada)
            if referrer_id:
                referrer = await session.get(User, referrer_id)
                if referrer:
                    # Bonus untuk referrer (yang mengundang)
                    referrer.poin_balance += 1000
                    session.add(PointLog(
                        user_id=referrer.id,
                        amount=1000,
                        source=f"Referral Bonus (from {user_id})"
                    ))
                    
                    # Bonus untuk user baru (yang diundang)
                    session.add(PointLog(
                        user_id=user_id,
                        amount=1000,
                        source=f"Welcome Bonus (referred by {referrer.id})"
                    ))
                    
                    # Catat tracking referral
                    session.add(ReferralTracking(
                        referrer_id=referrer.id,
                        referred_id=user_id
                    ))
                    
                    # Kirim notifikasi ke referrer
                    try:
                        await bot.send_message(
                            referrer.id,
                            f"🎉 <b>TEMAN BARU BERGABUNG!</b>\n\n"
                            f"💰 Kamu dapat: <b>+1.000 Poin</b> dari undangan!\n"
                            f"👤 Yang bergabung: {data['nickname']}",
                            parse_mode="HTML"
                        )
                    except:
                        pass
            
            await session.commit()
        
        # ========== LOG KE CHANNEL ADMIN ==========
        try:
            if ADMIN_LOG_CHANNEL:
                log_txt = (
                    f"🆕 <b>USER BARU REGISTRASI</b>\n"
                    f"👤 {data['nickname']} ({data['age']}th)\n"
                    f"👫 {data['gender']}\n"
                    f"🔥 {interests_str or '-'}\n"
                    f"📍 {data['city']}"
                )
                await bot.send_photo(
                    ADMIN_LOG_CHANNEL,
                    data['photo_1'],
                    caption=log_txt,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💬 PESAN", url=f"tg://user?id={user_id}")]
                    ]),
                    parse_mode="HTML"
                )
        except Exception as e:
            logging.error(f"Gagal kirim log ke admin channel: {e}")
        
        # ========== LOG KE GRUP MODERASI (UNTUK CEK FOTO) ==========
        try:
            if REG_MODERATION_GROUP:
                mod_kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ APPROVE", callback_data=f"mod_approve_{user_id}"),
                     InlineKeyboardButton(text="❌ REJECT PHOTO", callback_data=f"mod_reject_{user_id}")]
                ])
                mod_txt = (
                    f"🛡️ <b>MODERASI FOTO PROFIL BARU</b>\n"
                    f"👤 {data['nickname']} ({data['age']}th)\n"
                    f"👫 {data['gender']}\n"
                    f"📝 {bio[:50]}...\n\n"
                    f"<i>Mohon cek kelayakan foto profil ini.</i>"
                )
                await bot.send_photo(
                    REG_MODERATION_GROUP,
                    data['photo_1'],
                    caption=mod_txt,
                    reply_markup=mod_kb,
                    parse_mode="HTML"
                )
        except Exception as e:
            logging.error(f"Gagal kirim ke grup moderasi: {e}")
        
        # ========== SELESAI, BERSIHKAN STATE ==========
        await state.clear()
        
        # Hapus semua keyboard yang mungkin tersisa
        try:
            temp_msg = await message.answer("🔄", reply_markup=ReplyKeyboardRemove())
            await message.bot.delete_message(message.chat.id, temp_msg.message_id)
        except:
            pass
        
        # Beri tahu user bahwa registrasi berhasil
        await message.answer(
            "🎉 <b>SELAMAT! PENDAFTARAN BERHASIL</b>\n\n"
            "Profil kamu sudah siap. Sekarang kamu bisa:\n"
            "• 📸 Posting di Feed\n"
            "• 🔍 Swipe jodoh di Discovery\n"
            "• 💬 Chat dengan teman baru\n\n"
            "Silakan gunakan menu di bawah untuk mulai berpetualang!",
            parse_mode="HTML"
        )
        
        # Arahkan ke dashboard
        from handlers.start import command_start_handler
        from collections import namedtuple
        dummy_command = namedtuple('CommandObject', ['args'])(args=None)
        await command_start_handler(message, dummy_command, db, bot, state)
        
    except Exception as e:
        logging.error(f"❌ DB Error saat registrasi: {e}")
        await message.answer(
            "⚠️ <b>GAGAL MENDAFTAR</b>\n\n"
            "Terjadi kesalahan sistem. Silakan coba lagi dengan mengetik /start.\n"
            "Jika masalah berlanjut, hubungi admin.",
            parse_mode="HTML"
        )


# ==========================================
# 26. HANDLER: MODERASI FOTO (APPROVE/REJECT)
# ==========================================
@router.callback_query(F.data.startswith("mod_approve_"))
async def handle_mod_approve(callback: types.CallbackQuery):
    """Admin menyetujui foto profil"""
    admin_name = callback.from_user.first_name
    new_caption = f"{callback.message.caption}\n\n✅ <b>APPROVED</b> oleh {admin_name}"
    await callback.message.edit_caption(caption=new_caption, parse_mode="HTML")
    await callback.answer("Foto disetujui!", show_alert=False)


@router.callback_query(F.data.startswith("mod_reject_"))
async def handle_mod_reject(callback: types.CallbackQuery, db: DatabaseService, bot: Bot):
    """Admin menolak foto profil, reset ke foto default"""
    user_id = int(callback.data.split("_")[2])
    admin_name = callback.from_user.first_name
    
    # Reset foto profil user ke default anonim
    async with db.session_factory() as session:
        user = await session.get(User, user_id)
        if user:
            user.photo_id = DEFAULT_ANON_PHOTO_ID
            await session.commit()
    
    # Kirim peringatan ke user
    warn_msg = (
        "⚠️ <b>PERINGATAN KOMUNITAS</b>\n\n"
        "Foto profil kamu telah <b>ditolak/dihapus</b> oleh Admin karena melanggar aturan "
        "(tampil vulgar, memakai seragam sekolah, atau pose tidak pantas).\n\n"
        "Profilmu saat ini direset menggunakan logo anonim. Silakan perbarui fotomu "
        "melalui menu <b>Akun Saya > Kelola Galeri Foto</b>."
    )
    try:
        await bot.send_message(user_id, warn_msg, parse_mode="HTML")
    except:
        pass
    
    # Update pesan di grup moderasi
    new_caption = f"{callback.message.caption}\n\n❌ <b>REJECTED & RESET</b> oleh {admin_name}"
    await callback.message.edit_caption(caption=new_caption, parse_mode="HTML")
    await callback.answer("Foto ditolak dan profil direset!", show_alert=True)


# ==========================================
# 27. HANDLER: VERIFIKASI JOIN (DARI IRON GATE)
# ==========================================
@router.callback_query(F.data == "check_join_reg")
async def verify_join_reg(callback: types.CallbackQuery, bot: Bot, db: DatabaseService, state: FSMContext):
    """Memeriksa apakah user sudah join channel/grup setelah menekan tombol 'SUDAH JOIN'"""
    if await check_membership(bot, callback.from_user.id):
        # Cek apakah user sudah terdaftar (mungkin sudah pernah registrasi)
        user = await db.get_user(callback.from_user.id)
        if user:
            # User sudah ada, arahkan ke dashboard
            from handlers.start import command_start_handler
            from collections import namedtuple
            await callback.message.delete()
            dummy_command = namedtuple('CommandObject', ['args'])(args=None)
            return await command_start_handler(callback.message, dummy_command, db, bot, state)
        
        # User baru, hapus pesan join gate dan mulai registrasi
        await callback.message.delete()
        await start_registration(callback.message, state)
    else:
        await callback.answer("❌ Kamu belum join Channel/Grup!", show_alert=True)

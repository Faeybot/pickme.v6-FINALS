import os
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove

router = Router()

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")


def get_help_keyboard() -> InlineKeyboardMarkup:
    """Keyboard navigasi untuk menu Bantuan"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Hubungi Admin", url="https://t.me/UsernameAdminAnda")],
        [InlineKeyboardButton(text="⬅️ Kembali ke Dashboard", callback_data="back_to_dashboard")]
    ])


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Menampilkan menu bantuan"""
    
    # Cleanup ReplyKeyboard
    try:
        temp_msg = await message.answer("🔄", reply_markup=ReplyKeyboardRemove())
        await message.bot.delete_message(message.chat.id, temp_msg.message_id)
    except:
        pass
    
    help_text = (
        "📚 <b>PANDUAN LENGKAP PICKME BOT</b>\n"
        "<code>━━━━━━━━━━━━━━━━━━</code>\n"
        "Selamat datang di <b>PickMe</b>! Aplikasi <i>dating</i> dan komunitas anonim revolusioner di Telegram. "
        "Di sini, kamu tidak hanya bisa menemukan teman atau pasangan, tapi juga <b>mendapatkan penghasilan nyata</b> "
        "dari interaksimu!\n\n"
        
        "Berikut adalah fungsi & keunggulan menu utama kami:\n\n"
        
        "🎭 <b>1. FEED/CHANNEL</b>\n"
        "• <b>Fungsi:</b> Tempat kamu membagikan status, cerita, atau foto.\n"
        "• <b>Keunggulan:</b> Kamu bisa memposting secara <b>Anonim</b> (rahasia) atau menggunakan identitas profilmu. Semua kiriman akan masuk ke Channel Utama PickMe.\n\n"
        
        "🌎 <b>2. SWIPE JODOH (Discovery)</b>\n"
        "• <b>Fungsi:</b> Cari teman atau pasangan impianmu di sini.\n"
        "• <b>Keunggulan:</b> Geser profil (Like/Skip) yang difilter berdasarkan usia dan lokasimu. Jika sama-sama <i>Like</i>, kalian akan Match dan bisa langsung mengobrol!\n\n"
        
        "🔔 <b>3. NOTIFIKASI (Pusat Interaksi)</b>\n"
        "• <b>Fungsi:</b> Cek Inbox Pesan, Request Unmask, siapa yang Match, dan siapa yang diam-diam menyukai atau melihat profilmu.\n"
        "• <b>Keunggulan:</b> Terpusat! Kamu tidak akan ketinggalan satupun obrolan atau penggemar rahasiamu.\n\n"
        
        "⚙️ <b>4. AKUN SAYA</b>\n"
        "• <b>Fungsi:</b> Atur foto profil, edit bio, dan cek sisa kuota harianmu.\n"
        "• <b>Keunggulan:</b> Kamu memegang kendali penuh atas privasi dan bagaimana orang lain melihatmu di <i>Discovery</i>.\n\n"
        
        "💎 <b>5. UPGRADE/TOPUP</b>\n"
        "• <b>Fungsi:</b> Tingkatkan kasta akunmu menjadi Premium, VIP, atau VIP+.\n"
        "• <b>Keunggulan VIP/VIP+:</b> Kuota posting lebih banyak, bisa kirim DM langsung, buka topeng anonim (Unmask), dan bebas <i>chat</i>.\n"
        "• <b>Keunggulan PREMIUM:</b> Sekali bayar seumur hidup, dapat lencana khusus, dan menjadi <b>syarat wajib</b> untuk bisa melakukan pencairan dana (Withdraw).\n\n"
        
        "💳 <b>6. DOMPET/REWARD (Penghasil Uang)</b>\n"
        "• <b>Fungsi:</b> Cek kode Referral-mu dan lakukan <i>Withdraw</i> (Pencairan Poin).\n"
        "• <b>Keunggulan:</b> Undang teman untuk bergabung dan dapatkan <b>Poin Reward</b>! Poin yang terkumpul bisa dicairkan menjadi saldo e-Wallet/Uang Tunai (Eksklusif hanya untuk member <b>Premium</b>).\n\n"
        
        "<code>━━━━━━━━━━━━━━━━━━</code>\n"
        "<i>Gunakan Menu Biru (Kiri Bawah) jika kamu tersesat untuk kembali ke menu utama.</i>\n"
        "Punya kendala atau pertanyaan? Silakan hubungi Admin kami."
    )
    
    try:
        # Hapus pesan /help dari user agar chat tetap bersih
        await message.delete()
    except Exception:
        pass
    
    if BANNER_PHOTO_ID:
        try:
            await message.answer_photo(
                photo=BANNER_PHOTO_ID,
                caption=help_text,
                reply_markup=get_help_keyboard(),
                parse_mode="HTML"
            )
            return
        except Exception:
            pass
    
    # Fallback jika tidak ada foto
    await message.answer(
        text=help_text,
        reply_markup=get_help_keyboard(),
        parse_mode="HTML"
    )

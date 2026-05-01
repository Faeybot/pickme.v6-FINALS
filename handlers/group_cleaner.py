import os
import logging
from typing import Optional

from aiogram import Router, Bot, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

router = Router()


def _get_main_group_id() -> Optional[int]:
    """
    Mengambil GROUP_ID dari .env lama.
    Tidak memakai ENV baru agar aman untuk Railway yang sudah berjalan.
    """
    raw_group_id = os.getenv("GROUP_ID")
    if not raw_group_id:
        return None

    try:
        return int(raw_group_id)
    except ValueError:
        logging.warning(f"GROUP_ID tidak valid: {raw_group_id}")
        return None


def _is_main_group(message: Message) -> bool:
    """
    Cleaner hanya aktif di grup publik utama PickMe.
    Ini mencegah bot menghapus pesan di grup admin/moderator/finance.
    """
    main_group_id = _get_main_group_id()
    if not main_group_id:
        return False

    return message.chat and message.chat.id == main_group_id


def _clean_username(raw_username: Optional[str]) -> Optional[str]:
    if not raw_username:
        return None

    username = raw_username.strip()
    if username.startswith("@"):
        username = username[1:]

    return username or None


async def _build_bot_link(bot: Bot) -> str:
    """
    Link bot dibuat otomatis dari username bot aktif,
    jadi tidak perlu ENV BOT_USERNAME tambahan.
    """
    me = await bot.get_me()

    if me.username:
        return f"https://t.me/{me.username}?start=from_group"

    return "https://t.me/"


def _display_name(message_user) -> str:
    """
    Nama user untuk sapaan.
    """
    if not message_user:
        return "teman baru"

    full_name = (message_user.full_name or "").strip()
    if full_name:
        return full_name

    if message_user.username:
        return f"@{message_user.username}"

    return "teman baru"


@router.message(F.new_chat_members)
async def clean_join_log_and_welcome(message: Message, bot: Bot):
    """
    Saat user baru join:
    1. Hapus log join bawaan Telegram.
    2. Kirim sapaan yang lebih rapi.
    3. Tambahkan tombol buka bot.
    """
    if not _is_main_group(message):
        return

    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Gagal hapus log join: {e}")

    bot_link = await _build_bot_link(bot)

    group_username = _clean_username(os.getenv("GROUP_LINK"))
    group_text = f"@{group_username}" if group_username else "grup PickMe"

    new_members = message.new_chat_members or []

    # Jangan sambut bot lain agar grup tidak terlihat spam.
    human_members = [member for member in new_members if not member.is_bot]

    if not human_members:
        return

    names = ", ".join(_display_name(member) for member in human_members[:3])

    if len(human_members) > 3:
        names += f" dan {len(human_members) - 3} lainnya"

    text = (
        f"👋 Hai <b>{names}</b>, selamat datang di <b>PickMe Indonesia</b>!\n\n"
        f"Di {group_text}, kamu bisa ngobrol, kenalan, dan lihat update komunitas.\n\n"
        f"Untuk mulai pakai fitur PickMe seperti dating, feed, inbox, wallet, dan akun, "
        f"silakan buka bot melalui tombol di bawah ini."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Buka Bot PickMe",
                    url=bot_link,
                )
            ]
        ]
    )

    try:
        await message.answer(
            text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
    except Exception as e:
        logging.warning(f"Gagal kirim sapaan user baru: {e}")


@router.message(F.left_chat_member)
async def clean_left_log(message: Message):
    """
    Hapus log user keluar grup agar grup tetap bersih.
    """
    if not _is_main_group(message):
        return

    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Gagal hapus log keluar grup: {e}")


@router.message(F.pinned_message)
async def clean_pin_notification(message: Message, bot: Bot):
    """
    Hapus notifikasi pin di grup.

    Jika yang ter-pin adalah postingan otomatis dari channel diskusi,
    bot akan mencoba unpin agar postingan channel tidak terus tampil sebagai pin grup.

    Catatan:
    - Bot harus admin.
    - Bot perlu izin delete messages.
    - Untuk unpin, bot perlu izin pin/manage messages.
    """
    if not _is_main_group(message):
        return

    pinned = message.pinned_message

    should_unpin = False

    if pinned:
        # Postingan dari linked discussion channel biasanya automatic_forward.
        if getattr(pinned, "is_automatic_forward", False):
            should_unpin = True

        # Tambahan pengaman: pesan yang dikirim atas nama channel/sender_chat.
        if getattr(pinned, "sender_chat", None):
            should_unpin = True

    if should_unpin and pinned:
        try:
            await bot.unpin_chat_message(
                chat_id=message.chat.id,
                message_id=pinned.message_id,
            )
        except Exception as e:
            logging.warning(f"Gagal unpin postingan channel: {e}")

    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Gagal hapus notifikasi pin: {e}")


@router.message(F.text.startswith("/"))
async def delete_group_commands(message: Message):
    """
    Hapus command bot di grup agar user tidak menjalankan menu dari grup.

    User tetap bisa membuka bot dari:
    - tombol sapaan
    - profil bot di grup
    - mention bot
    - link t.me bot
    """
    if not _is_main_group(message):
        return

    try:
        await message.delete()
    except Exception as e:
        logging.warning(f"Gagal hapus command grup: {e}")

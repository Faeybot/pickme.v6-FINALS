import asyncio
import os
import logging
from typing import Optional

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

router = Router()


def _get_main_group_id() -> Optional[int]:
    raw_group_id = os.getenv("GROUP_ID")

    if not raw_group_id:
        logging.warning("[GROUP CLEANER] GROUP_ID belum ada di ENV.")
        return None

    try:
        return int(str(raw_group_id).strip())
    except ValueError:
        logging.warning(f"[GROUP CLEANER] GROUP_ID tidak valid: {raw_group_id}")
        return None


def _is_group_message(message: Message) -> bool:
    """
    Pastikan handler ini hanya bekerja di group/supergroup.
    Jangan sentuh private chat.
    """
    if not message.chat:
        return False

    return message.chat.type in {"group", "supergroup"}


def _is_main_group(message: Message) -> bool:
    """
    Cleaner hanya aktif di GROUP_ID utama.
    """
    if not _is_group_message(message):
        return False

    main_group_id = _get_main_group_id()

    if not main_group_id:
        return False

    return int(message.chat.id) == int(main_group_id)


def _clean_username(raw_username: Optional[str]) -> Optional[str]:
    if not raw_username:
        return None

    username = raw_username.strip()

    if username.startswith("@"):
        username = username[1:]

    return username or None


async def _build_bot_link(bot: Bot) -> str:
    me = await bot.get_me()

    if me.username:
        return f"https://t.me/{me.username}?start=from_group"

    return "https://t.me/"


def _display_name(user) -> str:
    if not user:
        return "teman baru"

    full_name = (user.full_name or "").strip()

    if full_name:
        return full_name

    if user.username:
        return f"@{user.username}"

    return "teman baru"


async def _send_welcome_message(
    bot: Bot,
    chat_id: int,
    users: list,
):
    human_users = [user for user in users if not getattr(user, "is_bot", False)]

    if not human_users:
        return

    bot_link = await _build_bot_link(bot)

    group_username = _clean_username(os.getenv("GROUP_LINK"))
    group_text = f"@{group_username}" if group_username else "grup PickMe"

    names = ", ".join(_display_name(user) for user in human_users[:3])

    if len(human_users) > 3:
        names += f" dan {len(human_users) - 3} lainnya"

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

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@router.message(Command("cekgrup"))
async def debug_group_id(message: Message):
    """
    Debug sementara.
    Hanya aktif di grup, tidak di private chat.
    """
    if not _is_group_message(message):
        return

    env_group_id = os.getenv("GROUP_ID")
    chat_id = message.chat.id if message.chat else None

    try:
        await message.delete()
    except Exception:
        pass

    await message.answer(
        "🔎 <b>Debug Grup PickMe</b>\n\n"
        f"Chat ID grup ini:\n<code>{chat_id}</code>\n\n"
        f"GROUP_ID dari ENV:\n<code>{env_group_id}</code>\n\n"
        "Jika dua angka di atas tidak sama, group cleaner tidak akan jalan."
    )


@router.message(F.new_chat_members)
async def clean_join_log_and_welcome(message: Message, bot: Bot):
    """
    Hapus log join dan kirim sapaan.
    Hanya aktif di GROUP_ID utama.
    """
    if not _is_main_group(message):
        return

    logging.info(
        f"[GROUP CLEANER] User join terdeteksi. chat_id={message.chat.id}"
    )

    try:
        await message.delete()
        logging.info("[GROUP CLEANER] Log join berhasil dihapus.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal hapus log join: {e}")

    try:
        await _send_welcome_message(
            bot=bot,
            chat_id=message.chat.id,
            users=message.new_chat_members or [],
        )
        logging.info("[GROUP CLEANER] Sapaan user baru berhasil dikirim.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal kirim sapaan user baru: {e}")


@router.message(F.left_chat_member)
async def clean_left_log(message: Message):
    """
    Hapus log user keluar grup.
    """
    if not _is_main_group(message):
        return

    try:
        await message.delete()
        logging.info("[GROUP CLEANER] Log user keluar berhasil dihapus.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal hapus log keluar grup: {e}")


@router.message(F.is_automatic_forward == True)
async def auto_unpin_channel_post(message: Message, bot: Bot):
    """
    Auto-unpin postingan channel yang otomatis masuk ke discussion group.
    Tetap membiarkan postingan muncul, hanya melepas pin.
    """
    if not _is_main_group(message):
        return

    logging.info(
        f"[GROUP CLEANER] Postingan channel otomatis terdeteksi. "
        f"chat_id={message.chat.id}, message_id={message.message_id}"
    )

    delays = [1, 2, 3]

    for delay in delays:
        try:
            await asyncio.sleep(delay)

            await bot.unpin_chat_message(
                chat_id=message.chat.id,
                message_id=message.message_id,
            )

            logging.info(
                f"[GROUP CLEANER] Postingan channel berhasil di-unpin setelah {delay} detik."
            )
            return

        except Exception as e:
            logging.warning(
                f"[GROUP CLEANER] Percobaan unpin setelah {delay} detik gagal: {e}"
            )


@router.message(F.pinned_message)
async def clean_pin_notification(message: Message, bot: Bot):
    """
    Hapus notifikasi pin.
    Jika yang dipin adalah postingan channel, coba unpin juga.
    """
    if not _is_main_group(message):
        return

    pinned = message.pinned_message

    if pinned:
        try:
            await bot.unpin_chat_message(
                chat_id=message.chat.id,
                message_id=pinned.message_id,
            )
            logging.info("[GROUP CLEANER] Pinned message berhasil di-unpin.")
        except Exception as e:
            logging.warning(f"[GROUP CLEANER] Gagal unpin pinned message: {e}")

    try:
        await message.delete()
        logging.info("[GROUP CLEANER] Notifikasi pin berhasil dihapus.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal hapus notifikasi pin: {e}")


@router.message(F.text.startswith("/"))
async def delete_group_commands(message: Message):
    """
    Hapus command di grup utama.
    Tidak aktif di private chat.
    """
    if not _is_main_group(message):
        return

    # Jangan hapus /cekgrup sebelum handler debug memprosesnya.
    if message.text and message.text.startswith("/cekgrup"):
        return

    try:
        await message.delete()
        logging.info("[GROUP CLEANER] Command grup berhasil dihapus.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal hapus command grup: {e}")

import os
import logging
from typing import Optional

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    ChatJoinRequest,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

router = Router()


def _get_main_group_id() -> Optional[int]:
    """
    Mengambil GROUP_ID dari ENV lama.
    Tidak memakai ENV baru agar tidak perlu input ulang di Railway.
    """
    raw_group_id = os.getenv("GROUP_ID")

    if not raw_group_id:
        logging.warning("[GROUP CLEANER] GROUP_ID belum ada di ENV.")
        return None

    try:
        return int(str(raw_group_id).strip())
    except ValueError:
        logging.warning(f"[GROUP CLEANER] GROUP_ID tidak valid: {raw_group_id}")
        return None


def _is_main_group(chat_id: Optional[int]) -> bool:
    """
    Cleaner hanya aktif di grup utama yang ID-nya sama dengan GROUP_ID.
    """
    if not chat_id:
        return False

    main_group_id = _get_main_group_id()

    if not main_group_id:
        return False

    return int(chat_id) == int(main_group_id)


def _clean_username(raw_username: Optional[str]) -> Optional[str]:
    if not raw_username:
        return None

    username = raw_username.strip()

    if username.startswith("@"):
        username = username[1:]

    return username or None


async def _build_bot_link(bot: Bot) -> str:
    """
    Link bot otomatis dari username bot aktif.
    Tidak perlu ENV BOT_USERNAME.
    """
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
    """
    Kirim sapaan user baru + inline button ke bot.
    """
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
    Command debug sementara.

    Kirim /cekgrup di grup.
    Bot akan menampilkan ID grup asli dan GROUP_ID dari ENV.

    Setelah sudah cocok, command ini boleh dihapus.
    """
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
    Saat user baru join:
    1. Hapus log join bawaan Telegram.
    2. Kirim sapaan yang lebih rapi.
    3. Tambahkan tombol buka bot.
    """
    chat_id = message.chat.id if message.chat else None

    logging.info(
        f"[GROUP CLEANER] new_chat_members event diterima. "
        f"chat_id={chat_id}, env_GROUP_ID={os.getenv('GROUP_ID')}"
    )

    if not _is_main_group(chat_id):
        logging.info("[GROUP CLEANER] Event join diabaikan karena bukan GROUP_ID utama.")
        return

    try:
        await message.delete()
        logging.info("[GROUP CLEANER] Log join berhasil dihapus.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal hapus log join: {e}")

    try:
        await _send_welcome_message(
            bot=bot,
            chat_id=chat_id,
            users=message.new_chat_members or [],
        )
        logging.info("[GROUP CLEANER] Sapaan user baru berhasil dikirim.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal kirim sapaan user baru: {e}")


@router.chat_join_request()
async def handle_join_request(join_request: ChatJoinRequest, bot: Bot):
    """
    Handler tambahan jika grup memakai fitur join request / approval.

    Catatan:
    Event ini terjadi saat user meminta join, bukan selalu setelah user benar-benar masuk.
    Jadi ini hanya untuk logging/debug.
    Sapaan utama tetap memakai F.new_chat_members setelah user benar-benar masuk.
    """
    chat_id = join_request.chat.id if join_request.chat else None

    logging.info(
        f"[GROUP CLEANER] chat_join_request diterima. "
        f"chat_id={chat_id}, user_id={join_request.from_user.id}, env_GROUP_ID={os.getenv('GROUP_ID')}"
    )


@router.message(F.left_chat_member)
async def clean_left_log(message: Message):
    """
    Hapus log user keluar grup agar grup tetap bersih.
    """
    chat_id = message.chat.id if message.chat else None

    if not _is_main_group(chat_id):
        return

    try:
        await message.delete()
        logging.info("[GROUP CLEANER] Log user keluar berhasil dihapus.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal hapus log keluar grup: {e}")


@router.message(F.pinned_message)
async def clean_pin_notification(message: Message, bot: Bot):
    """
    Hapus notifikasi pin di grup.

    Jika yang ter-pin adalah postingan otomatis dari channel diskusi,
    bot akan mencoba unpin.
    """
    chat_id = message.chat.id if message.chat else None

    if not _is_main_group(chat_id):
        return

    pinned = message.pinned_message
    should_unpin = False

    if pinned:
        if getattr(pinned, "is_automatic_forward", False):
            should_unpin = True

        if getattr(pinned, "sender_chat", None):
            should_unpin = True

    if should_unpin and pinned:
        try:
            await bot.unpin_chat_message(
                chat_id=message.chat.id,
                message_id=pinned.message_id,
            )
            logging.info("[GROUP CLEANER] Postingan channel berhasil di-unpin.")
        except Exception as e:
            logging.warning(f"[GROUP CLEANER] Gagal unpin postingan channel: {e}")

    try:
        await message.delete()
        logging.info("[GROUP CLEANER] Notifikasi pin berhasil dihapus.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal hapus notifikasi pin: {e}")


@router.message(F.text.startswith("/"))
async def delete_group_commands(message: Message):
    """
    Hapus command bot di grup agar user tidak menjalankan menu dari grup.

    Command /cekgrup tidak ikut dihapus di sini karena sudah ditangani handler debug di atas.
    """
    chat_id = message.chat.id if message.chat else None

    if not _is_main_group(chat_id):
        return

    try:
        await message.delete()
        logging.info("[GROUP CLEANER] Command grup berhasil dihapus.")
    except Exception as e:
        logging.warning(f"[GROUP CLEANER] Gagal hapus command grup: {e}")

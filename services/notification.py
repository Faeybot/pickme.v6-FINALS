import os
import logging
import datetime
import asyncio
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from services.database import DatabaseService, UserNotification, User

BANNER_PHOTO_ID = os.getenv("BANNER_PHOTO_ID")


class NotificationService:
    def __init__(self, bot: Bot, db: DatabaseService = None):
        self.bot = bot
        self.db = db

    async def _silent_log(self, user_id: int, notif_type: str, sender_id: int = None, content: str = ""):
        if not self.db:
            return logging.error("DatabaseService missing!")
        async with self.db.session_factory() as session:
            session.add(UserNotification(
                user_id=user_id, type=notif_type, sender_id=sender_id, content=content, is_read=False
            ))
            await session.commit()

    async def _is_user_active(self, user_id: int) -> bool:
        user = await self.db.get_user(user_id)
        if not user or not user.last_active_at:
            return False
        now = datetime.datetime.utcnow()
        diff = (now - user.last_active_at).total_seconds()
        return diff < 180

    async def _is_user_in_chat_room(self, user_id: int) -> bool:
        user = await self.db.get_user(user_id)
        if user and user.nav_stack:
            last = user.nav_stack[-1]
            if last.startswith("chat_room_"):
                return True
        return False

    async def _send_temp_message(self, chat_id: int, text: str, reply_markup=None, delay: float = 1.0):
        """Kirim pesan lalu hapus setelah delay detik (cukup untuk push notification)"""
        try:
            msg = await self.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
            await asyncio.sleep(delay)
            await msg.delete()
        except:
            pass

    # ==========================================
    # TRIGGER UNMASK
    # ==========================================
    async def trigger_unmask(self, target_id: int, sender_id: int):
        await self._silent_log(target_id, "UNMASK_CHAT", sender_id, "Seseorang Unmask profilmu")
        if await self._is_user_in_chat_room(target_id):
            return  # tidak kirim pesan, hanya simpan notifikasi
        if await self._is_user_active(target_id):
            return
        text = "🔓 <b>Seseorang membongkar identitas anonimmu!</b>\nSesi chat 48 jam telah terbuka."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Lihat Siapa", callback_data="notif_unmask")],
            [InlineKeyboardButton(text="🏠 Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])
        await self._send_temp_message(target_id, text, reply_markup=kb)

    # ==========================================
    # TRIGGER NEW MESSAGE
    # ==========================================
    async def trigger_new_message(self, target_id: int, sender_id: int, sender_name: str, is_reply: bool = False):
        await self._silent_log(target_id, "CHAT", sender_id, f"Pesan dari {sender_name}")
        if await self._is_user_in_chat_room(target_id):
            return
        user = await self.db.get_user(target_id)
        if user and user.nav_stack and user.nav_stack[-1] == "inbox":
            return
        if await self._is_user_active(target_id):
            return
        unreads = await self.db.get_all_unread_counts(target_id)
        count_n = unreads.get('inbox', 1)
        if is_reply:
            text = f"💬 <b>{sender_name} membalas pesanmu!</b>"
        else:
            text = f"📩 <b>Kamu memiliki ({count_n}) pesan masuk baru!</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Buka Pesan", callback_data="notif_inbox")],
            [InlineKeyboardButton(text="🏠 Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])
        await self._send_temp_message(target_id, text, reply_markup=kb)

    # ==========================================
    # TRIGGER LIKE
    # ==========================================
    async def trigger_like(self, target_id: int, sender_id: int):
        await self._silent_log(target_id, "LIKE", sender_id, "Seseorang telah menyukaimu")
        if await self._is_user_in_chat_room(target_id):
            return
        if await self._is_user_active(target_id):
            return
        text = "❤️ <b>Seseorang baru saja menyukaimu!</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Lihat Siapa", callback_data="notif_like")],
            [InlineKeyboardButton(text="🏠 Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])
        await self._send_temp_message(target_id, text, reply_markup=kb)

    # ==========================================
    # TRIGGER VIEW
    # ==========================================
    async def trigger_view(self, target_id: int, sender_id: int):
        await self._silent_log(target_id, "VIEW", sender_id, "Seseorang telah melihat profilmu")
        if await self._is_user_in_chat_room(target_id):
            return
        if await self._is_user_active(target_id):
            return
        text = "👀 <b>Seseorang sedang mengintip profilmu!</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👀 Lihat Siapa", callback_data="notif_view")],
            [InlineKeyboardButton(text="🏠 Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])
        await self._send_temp_message(target_id, text, reply_markup=kb)

    async def send_push_alert(self, target_id: int, alert_type: str):
        if alert_type == "LIKE":
            await self.trigger_like(target_id, None)


# ==========================================
# GERBANG NOTIFIKASI (DIPANGGIL DARI START.PY)
# ==========================================
async def render_notification_hub(bot: Bot, chat_id: int, user_id: int, db: DatabaseService, callback_id: str = None):
    from utils.ui_manager import UIManager
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
    media = InputMediaPhoto(media=BANNER_PHOTO_ID, caption=text, parse_mode="HTML")
    if callback_id:
        try:
            await bot.edit_message_media(chat_id=chat_id, message_id=user.anchor_msg_id, media=media, reply_markup=kb)
            await bot.answer_callback_query(callback_id)
        except:
            pass
    else:
        sent = await bot.send_photo(chat_id=chat_id, photo=BANNER_PHOTO_ID, caption=text, reply_markup=kb, parse_mode="HTML")
        await db.update_anchor_msg(user_id, sent.message_id)

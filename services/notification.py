import logging
import datetime
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from services.database import DatabaseService, UserNotification, User

class NotificationService:
    def __init__(self, bot: Bot, db: DatabaseService = None):
        self.bot = bot
        self.db = db

    async def _silent_log(self, user_id: int, notif_type: str, sender_id: int = None, content: str = ""):
        if not self.db: return logging.error("DatabaseService missing!")
        async with self.db.session_factory() as session:
            session.add(UserNotification(
                user_id=user_id, type=notif_type, sender_id=sender_id, content=content, is_read=False
            ))
            await session.commit()

    async def _is_user_active(self, user_id: int) -> bool:
        """Mengecek apakah user sedang aktif bermain bot (interaksi dalam 3 menit terakhir)"""
        user = await self.db.get_user(user_id)
        if not user or not user.last_active_at: return False
        
        now = datetime.datetime.utcnow()
        diff = (now - user.last_active_at).total_seconds()
        return diff < 180 # 180 detik = 3 menit

    # --- 1. NOTIFIKASI UNMASK ---
    async def trigger_unmask(self, target_id: int, sender_id: int):
        await self._silent_log(target_id, "UNMASK_CHAT", sender_id, "Seseorang Unmask profilmu")
        
        # STOP DISINI jika user sedang aktif di dalam bot (Hanya Silent Log)
        if await self._is_user_active(target_id): return
        
        text = "🔓 <b>Seseorang membongkar identitas anonimmu!</b>\nSesi chat 48 jam telah terbuka."
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Lihat Siapa", callback_data="notif_unmask")],
            [InlineKeyboardButton(text="🏠 Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])
        try: await self.bot.send_message(target_id, text, reply_markup=kb, parse_mode="HTML")
        except: pass

    # --- 2. NOTIFIKASI INBOX PESAN & BALASAN ---
    async def trigger_new_message(self, target_id: int, sender_id: int, sender_name: str, is_reply: bool = False):
        await self._silent_log(target_id, "CHAT", sender_id, f"Pesan dari {sender_name}")
        
        user = await self.db.get_user(target_id)
        if user and user.nav_stack:
            if user.nav_stack[-1] == f"chat_room_{sender_id}": return # Sedang di room chat yg sama
            if user.nav_stack[-1] == "inbox": return # Sedang melihat list inbox
            
        if await self._is_user_active(target_id): return

        unreads = await self.db.get_all_unread_counts(target_id)
        count_n = unreads.get('inbox', 1)
        
        if is_reply: text = f"💬 <b>{sender_name} membalas pesanmu!</b>"
        else: text = f"📩 <b>Kamu memiliki ({count_n}) pesan masuk baru!</b>"
            
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Buka Pesan", callback_data="notif_inbox")],
            [InlineKeyboardButton(text="🏠 Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])
        try: await self.bot.send_message(target_id, text, reply_markup=kb, parse_mode="HTML")
        except: pass

    # --- 3. NOTIFIKASI SUKA / LIKE ---
    async def trigger_like(self, target_id: int, sender_id: int):
        await self._silent_log(target_id, "LIKE", sender_id, "Seseorang telah menyukaimu")
        if await self._is_user_active(target_id): return

        text = "❤️ <b>Seseorang baru saja menyukaimu!</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❤️ Lihat Siapa", callback_data="notif_like")],
            [InlineKeyboardButton(text="🏠 Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])
        try: await self.bot.send_message(target_id, text, reply_markup=kb, parse_mode="HTML")
        except: pass

    # --- 4. NOTIFIKASI MELIHAT PROFIL ---
    async def trigger_view(self, target_id: int, sender_id: int):
        await self._silent_log(target_id, "VIEW", sender_id, "Seseorang telah melihat profilmu")
        if await self._is_user_active(target_id): return

        text = "👀 <b>Seseorang sedang mengintip profilmu!</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👀 Lihat Siapa", callback_data="notif_view")],
            [InlineKeyboardButton(text="🏠 Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])
        try: await self.bot.send_message(target_id, text, reply_markup=kb, parse_mode="HTML")
        except: pass

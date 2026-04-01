import os
import logging
import json
import datetime
from sqlalchemy import (
    Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey, 
    Float, JSON, Text, select, update, and_, or_, not_, delete, text, func
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

Base = declarative_base()

# ==========================================
# 1. MODEL TABEL DATABASE
# ==========================================

class User(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True)
    full_name = Column(String)
    age = Column(Integer)
    birth_date = Column(DateTime, nullable=True) 
    gender = Column(String)
    bio = Column(Text)
    interests = Column(String, nullable=True) 
    photo_id = Column(String)
    extra_photos = Column(JSON, default=list) 
    latitude = Column(Float)
    longitude = Column(Float)
    location_name = Column(String)
    city_hashtag = Column(String)
    filter_age_min = Column(Integer, default=18)
    filter_age_max = Column(Integer, default=60)
    
    # Tier Status
    is_premium = Column(Boolean, default=False) 
    is_vip = Column(Boolean, default=False)      
    is_vip_plus = Column(Boolean, default=False) 
    is_talent = Column(Boolean, default=False)
    talent_bonus_claimed = Column(Boolean, default=False)
    vip_expires_at = Column(DateTime, nullable=True) 
    
    # Navigation & UI State
    anchor_msg_id = Column(BigInteger, nullable=True)
    nav_stack = Column(JSON, default=list)
    
    # Wallet & Financial
    poin_balance = Column(BigInteger, default=0)
    has_withdrawn_before = Column(Boolean, default=False) 
    last_active_at = Column(DateTime, nullable=True) 
    
    # Quotas & Limits
    daily_feed_text_quota = Column(Integer, default=2)
    daily_feed_photo_quota = Column(Integer, default=0)
    daily_open_profile_quota = Column(Integer, default=0) 
    daily_unmask_quota = Column(Integer, default=0)       
    daily_message_quota = Column(Integer, default=0)      
    daily_swipe_quota = Column(Integer, default=10)
    daily_swipe_count = Column(Integer, default=0) 
    
    extra_feed_text_quota = Column(Integer, default=0)
    extra_feed_photo_quota = Column(Integer, default=0)
    extra_message_quota = Column(Integer, default=0)
    
    # Timestamps & Boosts
    last_swipe_at = Column(DateTime, default=datetime.datetime.utcnow)
    weekly_free_boost = Column(Integer, default=0) 
    paid_boost_balance = Column(Integer, default=0) 
    last_boost_date = Column(String, nullable=True) 

class PointLog(Base):
    __tablename__ = "point_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    amount = Column(Integer)
    source = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class UserNotification(Base):
    __tablename__ = "user_notifications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    type = Column(String) 
    sender_id = Column(BigInteger, nullable=True)
    content = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SwipeHistory(Base):
    __tablename__ = "swipe_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    target_id = Column(BigInteger)
    action = Column(String) 
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ReferralTracking(Base):
    __tablename__ = "referral_tracking"
    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(BigInteger, ForeignKey("users.id"))
    referred_id = Column(BigInteger, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    is_completed = Column(Boolean, default=False)
    week_1_done = Column(Boolean, default=False)
    week_2_done = Column(Boolean, default=False)
    week_3_done = Column(Boolean, default=False)
    week_4_done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class WithdrawRequest(Base):
    __tablename__ = "withdraw_requests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    amount_poin = Column(Integer)
    amount_rp = Column(Integer)
    wallet_type = Column(String)
    wallet_number = Column(String)
    wallet_name = Column(String)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DailyInteraction(Base):
    __tablename__ = "daily_interactions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"))
    target_id = Column(BigInteger)
    action = Column(String) 
    date_str = Column(String) 

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), index=True)
    target_id = Column(BigInteger, index=True)
    thread_id = Column(BigInteger, nullable=True)
    origin = Column(String(20), default="public")
    last_message = Column(Text, nullable=True) 
    chat_history = Column(JSON, default=list)
    last_updated = Column(BigInteger, default=0) 
    expires_at = Column(BigInteger) 
    is_active = Column(Boolean, default=True)
    channel_msg_ids = Column(JSON, default=list)


# ==========================================
# 2. DATABASE SERVICE
# ==========================================
class DatabaseService:
    def __init__(self, url: str):
        if url.startswith("postgres://"): 
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url: 
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            
        self.engine = create_async_engine(url, echo=False, pool_pre_ping=True)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init_db(self):
        """Membuat tabel dan menjalankan ALTER TABLE otomatis"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
            alter_queries = [
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_swipe_quota INTEGER DEFAULT 10;",
                "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS chat_history JSON DEFAULT '[]';",
                "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
                "ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS origin VARCHAR(20) DEFAULT 'public';",
            ]
            for query in alter_queries:
                try:
                    await conn.execute(text(query))
                except Exception:
                    pass

    # ========== NAVIGATION & SPA ==========
    async def update_anchor_msg(self, user_id: int, msg_id: int):
        async with self.session_factory() as session:
            await session.execute(update(User).where(User.id == user_id).values(anchor_msg_id=msg_id))
            await session.commit()

    async def push_nav(self, user_id: int, menu_name: str):
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if user:
                stack = list(user.nav_stack) if user.nav_stack else []
                if not stack or stack[-1] != menu_name:
                    stack.append(menu_name)
                    user.nav_stack = stack
                    await session.commit()

    async def pop_nav(self, user_id: int) -> str:
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if user and user.nav_stack:
                stack = list(user.nav_stack)
                if len(stack) > 1:
                    stack.pop()
                last_menu = stack[-1] if stack else "dashboard"
                user.nav_stack = stack
                await session.commit()
                return last_menu
            return "dashboard"

    # ========== CORE USER ==========
    async def get_user(self, user_id: int):
        async with self.session_factory() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            return result.scalar_one_or_none()

    async def update_user_location(self, user_id: int, lat: float, lng: float, loc_name: str, hashtag: str):
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if user:
                user.latitude, user.longitude = lat, lng
                user.location_name, user.city_hashtag = loc_name, hashtag
                await session.commit()

    async def update_main_photo(self, user_id: int, photo_id: str):
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if user:
                user.photo_id = photo_id
                await session.commit()

    async def manage_extra_photo(self, user_id: int, photo_id: str, action: str):
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if user:
                current_photos = list(user.extra_photos) if user.extra_photos else []
                if action == 'add' and len(current_photos) < 2:
                    current_photos.append(photo_id)
                elif action == 'remove' and photo_id in current_photos:
                    current_photos.remove(photo_id)
                user.extra_photos = current_photos
                await session.commit()

    # ========== QUOTAS & RESET ==========
    async def reset_daily_quotas(self):
        """Reset kuota sesuai aturan kasta"""
        async with self.session_factory() as session:
            # VIP+
            await session.execute(update(User).where(User.is_vip_plus == True).values(
                daily_feed_text_quota=10, daily_feed_photo_quota=5,
                daily_message_quota=10, daily_open_profile_quota=10,
                daily_unmask_quota=10, daily_swipe_quota=50, daily_swipe_count=0
            ))
            # VIP
            await session.execute(update(User).where(and_(User.is_vip == True, User.is_vip_plus == False)).values(
                daily_feed_text_quota=10, daily_feed_photo_quota=5,
                daily_message_quota=10, daily_open_profile_quota=10,
                daily_unmask_quota=0, daily_swipe_quota=30, daily_swipe_count=0
            ))
            # Premium
            await session.execute(update(User).where(and_(User.is_premium == True, User.is_vip == False, User.is_vip_plus == False)).values(
                daily_feed_text_quota=3, daily_feed_photo_quota=1,
                daily_message_quota=0, daily_open_profile_quota=0,
                daily_unmask_quota=0, daily_swipe_quota=20, daily_swipe_count=0
            ))
            # Free
            await session.execute(update(User).where(and_(User.is_premium == False, User.is_vip == False, User.is_vip_plus == False)).values(
                daily_feed_text_quota=2, daily_feed_photo_quota=0,
                daily_message_quota=0, daily_open_profile_quota=0,
                daily_unmask_quota=0, daily_swipe_quota=10, daily_swipe_count=0
            ))
            await session.commit()

    async def reset_weekly_quotas(self):
        async with self.session_factory() as session:
            await session.execute(update(User).where(User.is_vip_plus == True).values(weekly_free_boost=1))
            await session.commit()

    async def check_expired_vip(self):
        async with self.session_factory() as session:
            now = datetime.datetime.utcnow()
            await session.execute(update(User).where(and_(User.vip_expires_at != None, User.vip_expires_at < now)).values(
                is_vip=False, is_vip_plus=False, vip_expires_at=None
            ))
            await session.commit()

    async def use_message_quota(self, user_id: int) -> bool:
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if not user:
                return False
            if user.daily_message_quota > 0:
                user.daily_message_quota -= 1
            elif user.extra_message_quota > 0:
                user.extra_message_quota -= 1
            else:
                return False
            await session.commit()
            return True

    async def use_unmask_anon_quota(self, user_id: int) -> bool:
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if user and user.is_vip_plus and user.daily_unmask_quota > 0:
                user.daily_unmask_quota -= 1
                await session.commit()
                return True
            return False

    async def use_unmask_quota(self, user_id: int) -> bool:
        """Gunakan kuota buka profil (untuk VIP/VIP+)"""
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if user and (user.is_vip or user.is_vip_plus) and user.daily_open_profile_quota > 0:
                user.daily_open_profile_quota -= 1
                await session.commit()
                return True
            return False

    # ========== POINTS & REWARDS ==========
    async def add_points_with_log(self, user_id: int, amount: int, source: str) -> bool:
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if not user:
                return False
            user.poin_balance += amount
            session.add(PointLog(user_id=user_id, amount=amount, source=source))
            await session.commit()
            return True

    async def check_bonus_exists(self, source_key: str) -> bool:
        """Cek apakah bonus sudah pernah diklaim"""
        async with self.session_factory() as session:
            res = await session.execute(select(PointLog).where(PointLog.source == source_key))
            return res.scalar_one_or_none() is not None

    async def log_and_check_daily_reward(self, user_id: int, target_id: int, action: str) -> bool:
        """Log daily reward dan cek apakah sudah ada"""
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        async with self.session_factory() as session:
            res = await session.execute(select(DailyInteraction).where(
                and_(DailyInteraction.user_id == user_id,
                     DailyInteraction.target_id == target_id,
                     DailyInteraction.action == action,
                     DailyInteraction.date_str == today_str)
            ))
            if res.scalar_one_or_none():
                return False
            session.add(DailyInteraction(user_id=user_id, target_id=target_id, action=action, date_str=today_str))
            await session.commit()
            return True

    async def award_reply_points(self, user_id: int, target_id: int, context: str):
        amount = 500 if context == "unmask" else 200
        bonus_key = f"REWARD_{context.upper()}_{target_id}"
        async with self.session_factory() as session:
            check = await session.execute(select(PointLog).where(and_(PointLog.user_id == user_id, PointLog.source == bonus_key)))
            if not check.scalar_one_or_none():
                user = await session.get(User, user_id)
                user.poin_balance += amount
                session.add(PointLog(user_id=user_id, amount=amount, source=bonus_key))
                await session.commit()
                return amount
        return 0

    # ========== CHAT SESSION & HISTORY ==========
    async def get_active_chat_session(self, user_id: int, target_id: int):
        async with self.session_factory() as session:
            res = await session.execute(select(ChatSession).where(
                ((ChatSession.user_id == user_id) & (ChatSession.target_id == target_id)) |
                ((ChatSession.user_id == target_id) & (ChatSession.target_id == user_id))
            ))
            return res.scalar_one_or_none()

    async def upsert_chat_session(self, user_id: int, target_id: int, expires_at: int, thread_id: int = None, origin: str = "public"):
        now_ts = int(datetime.datetime.now().timestamp())
        async with self.session_factory() as session:
            res = await session.execute(select(ChatSession).where(
                ((ChatSession.user_id == user_id) & (ChatSession.target_id == target_id)) |
                ((ChatSession.user_id == target_id) & (ChatSession.target_id == user_id))
            ))
            session_data = res.scalar_one_or_none()
            
            if session_data:
                session_data.expires_at = expires_at
                session_data.last_updated = now_ts
                session_data.origin = origin
                if thread_id is not None:
                    session_data.thread_id = thread_id
            else:
                session.add(ChatSession(
                    user_id=user_id, target_id=target_id, expires_at=expires_at,
                    thread_id=thread_id, last_updated=now_ts, origin=origin
                ))
            await session.commit()

    async def add_chat_history(self, user_id: int, target_id: int, sender_name: str, message_text: str):
        """Menambahkan history chat dengan rolling buffer 50 pesan"""
        async with self.session_factory() as session:
            stmt = select(ChatSession).where(
                ((ChatSession.user_id == user_id) & (ChatSession.target_id == target_id)) |
                ((ChatSession.user_id == target_id) & (ChatSession.target_id == user_id))
            )
            result = await session.execute(stmt)
            chat_sess = result.scalar_one_or_none()

            if chat_sess:
                history = list(chat_sess.chat_history or [])
                new_entry = {
                    "s": sender_name[:15],
                    "t": message_text[:250],
                    "ts": datetime.datetime.now().strftime("%H:%M")
                }
                history.append(new_entry)
                
                if len(history) > 50:
                    history.pop(0)
                
                chat_sess.chat_history = history
                chat_sess.last_message = message_text
                chat_sess.last_updated = int(datetime.datetime.now().timestamp())
                await session.commit()
                return chat_sess
        return None

    async def get_chat_history(self, user_id: int, target_id: int, limit: int = 20):
        """Mengambil history chat untuk ditampilkan di UI"""
        async with self.session_factory() as session:
            stmt = select(ChatSession).where(
                ((ChatSession.user_id == user_id) & (ChatSession.target_id == target_id)) |
                ((ChatSession.user_id == target_id) & (ChatSession.target_id == user_id))
            )
            result = await session.execute(stmt)
            chat_sess = result.scalar_one_or_none()
            
            if chat_sess and chat_sess.chat_history:
                return chat_sess.chat_history[-limit:]
        return []

    async def get_inbox_sessions(self, user_id: int):
        async with self.session_factory() as session:
            query = select(ChatSession).where(
                (ChatSession.user_id == user_id) | (ChatSession.target_id == user_id)
            ).order_by(ChatSession.last_updated.desc())
            
            result = await session.execute(query)
            return result.scalars().all()

    # ========== SWIPE & MATCH ==========
    async def record_swipe(self, user_id: int, target_id: int, action: str):
        async with self.session_factory() as session:
            user = await session.get(User, user_id)
            if user:
                user.daily_swipe_count += 1
                session.add(SwipeHistory(user_id=user_id, target_id=target_id, action=action))
                await session.commit()

    async def process_match_logic(self, user_id: int, target_id: int):
        async with self.session_factory() as session:
            check = await session.execute(select(UserNotification).where(
                and_(UserNotification.user_id == user_id, UserNotification.sender_id == target_id, UserNotification.type == "LIKE")
            ))
            like_entry = check.scalar_one_or_none()
            
            if like_entry:
                await session.delete(like_entry)
                session.add(UserNotification(user_id=user_id, sender_id=target_id, type="MATCH"))
                session.add(UserNotification(user_id=target_id, sender_id=user_id, type="MATCH"))
                await session.commit()
                return True
            return False

    # ========== NOTIFICATIONS ==========
    async def get_all_unread_counts(self, user_id: int) -> dict:
        async with self.session_factory() as session:
            query = select(UserNotification.type, func.count(UserNotification.id)).where(
                and_(UserNotification.user_id == user_id, UserNotification.is_read == False)
            ).group_by(UserNotification.type)
            
            result = await session.execute(query)
            counts = {'unmask': 0, 'inbox': 0, 'match': 0, 'like': 0, 'view': 0}
            
            for row in result.all():
                notif_type = row[0].upper()
                count_val = row[1]
                if notif_type == 'UNMASK_CHAT':
                    counts['unmask'] = count_val
                elif notif_type == 'CHAT':
                    counts['inbox'] = count_val
                elif notif_type == 'MATCH':
                    counts['match'] = count_val
                elif notif_type == 'LIKE':
                    counts['like'] = count_val
                elif notif_type == 'VIEW':
                    counts['view'] = count_val
            return counts

    async def get_interaction_list(self, user_id: int, notif_type: str, limit=10):
        async with self.session_factory() as session:
            user_db = await session.get(User, user_id)
            expiry_hours = 48 if (user_db and user_db.is_vip_plus) else 24
            time_limit = datetime.datetime.utcnow() - datetime.timedelta(hours=expiry_hours)
            
            if notif_type == "CHAT":
                type_filter = UserNotification.type == "CHAT"
            elif notif_type == "UNMASK_CHAT":
                type_filter = UserNotification.type == "UNMASK_CHAT"
            else:
                type_filter = UserNotification.type.ilike(f"%{notif_type}%")

            query = select(User, UserNotification.created_at).join(
                UserNotification, UserNotification.sender_id == User.id
            ).where(
                and_(
                    UserNotification.user_id == user_id, type_filter,
                    or_(not_(UserNotification.type.in_(["CHAT", "UNMASK_CHAT"])), UserNotification.created_at > time_limit)
                )
            ).order_by(UserNotification.created_at.desc())
            
            result = await session.execute(query)
            unique_users = []
            seen_ids = set()
            for row in result.all():
                u = row[0]
                if u.id not in seen_ids:
                    seen_ids.add(u.id)
                    u.notif_date = row[1]
                    unique_users.append(u)
                    if len(unique_users) >= limit:
                        break
            return unique_users

    async def mark_notif_read(self, user_id: int, sender_id: int, notif_type: str):
        async with self.session_factory() as session:
            await session.execute(
                update(UserNotification).where(
                    and_(UserNotification.user_id == user_id, UserNotification.sender_id == sender_id, UserNotification.type == notif_type)
                ).values(is_read=True)
            )
            await session.commit()

    async def remove_interaction(self, user_id: int, target_id: int, notif_type: str):
        async with self.session_factory() as session:
            await session.execute(delete(UserNotification).where(
                and_(UserNotification.user_id == user_id, UserNotification.sender_id == target_id, UserNotification.type.ilike(f"%{notif_type}%"))
            ))
            await session.commit()

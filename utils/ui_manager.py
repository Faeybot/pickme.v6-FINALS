ehfrom aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class UIManager:
    @staticmethod
    def get_dashboard_inline_kb(notif_count: int = 0) -> InlineKeyboardMarkup:
        """ Inline keyboard utama untuk menu Dashboard """
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎭 FEED/CHANNEL", callback_data="menu_feed"),
             InlineKeyboardButton(text="🌎 SWIPE JODOH", callback_data="menu_discovery")],
             
            [InlineKeyboardButton(text=f"🔔 NOTIFIKASI ({notif_count})", callback_data="menu_notifications"),
             InlineKeyboardButton(text="⚙️ AKUN SAYA", callback_data="menu_account")],
             
            [InlineKeyboardButton(text="💎 UPGRADE/TOPUP", callback_data="menu_pricing"),
             InlineKeyboardButton(text="💳 DOMPET/REWARD", callback_data="menu_finance")]
        ])

    @staticmethod
    def get_notification_center_kb(counts: dict) -> InlineKeyboardMarkup:
        """ Sub-menu untuk Pusat Notifikasi """
        inbox = counts.get('inbox', 0)
        unmask = counts.get('unmask', 0)
        match = counts.get('match', 0)
        like = counts.get('like', 0)
        view = counts.get('view', 0)
        
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"📥 Inbox Pesan ({inbox})", callback_data="notif_inbox")],
            [InlineKeyboardButton(text=f"🎭 Request Unmask ({unmask})", callback_data="notif_unmask")],
            [InlineKeyboardButton(text=f"💖 Match Baru ({match})", callback_data="notif_match")],
            [InlineKeyboardButton(text=f"❤️ Siapa Suka Saya ({like})", callback_data="notif_like")],
            [InlineKeyboardButton(text=f"👀 Siapa Lihat Profil ({view})", callback_data="notif_view")],
            [InlineKeyboardButton(text="⬅️ Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])

    @staticmethod
    def get_account_center_kb() -> InlineKeyboardMarkup:
        """ Sub-menu untuk Pusat Akun (Profil & Status) """
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Lihat & Edit Profil", callback_data="menu_profile")],
            [InlineKeyboardButton(text="📊 Cek Status & Kuota", callback_data="menu_status")],
            [InlineKeyboardButton(text="⬅️ Kembali ke Dashboard", callback_data="back_to_dashboard")]
        ])

    @staticmethod
    def get_finance_center_kb() -> InlineKeyboardMarkup:
        """ Sub-menu untuk Keuangan (WD & Referral) """
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Withdraw Poin", callback_data="wallet_withdraw")],  # ← UBAH
            [InlineKeyboardButton(text="🎁 Cek Referral", callback_data="wallet_referral")],   # ← UBAH
            [InlineKeyboardButton(text="⬅️ Kembali ke Dashboard", callback_data="back_to_dashboard")]

        ])

    @staticmethod
    def get_join_gate_kb(channel_link: str, group_link: str) -> InlineKeyboardMarkup:
        """ Keyboard untuk layar Wajib Join """
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Join Channel Feed PickMe", url=f"https://t.me/{channel_link}")],
            [InlineKeyboardButton(text="👥 Join Grup PickMe", url=f"https://t.me/{group_link}")],
            [InlineKeyboardButton(text="✅ SAYA SUDAH JOIN", callback_data="check_join_start")]
        ])

    @staticmethod
    def get_back_button_kb(callback_data: str = "back_to_dashboard") -> InlineKeyboardMarkup:
        """ Tombol kembali universal berbasis Inline """
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Kembali", callback_data=callback_data)]
        ])
      

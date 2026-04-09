import asyncio
from aiogram import Bot

async def send_temp_message(bot: Bot, chat_id: int, text: str, delay: float = 1.5):
    """Kirim pesan lalu hapus setelah delay detik."""
    try:
        msg = await bot.send_message(chat_id, text, parse_mode="HTML")
        await asyncio.sleep(delay)
        await msg.delete()
    except:
        pass

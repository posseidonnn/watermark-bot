import asyncio
import logging
import socket

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_IDS
from handlers.post import router as post_router


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Force IPv4: the VPS resolves api.telegram.org to IPv6 first
    session = AiohttpSession()
    session._connector_init["family"] = socket.AF_INET

    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher(storage=MemoryStorage())

    post_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
    post_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))
    dp.include_router(post_router)

    try:
        while True:
            try:
                await dp.start_polling(bot)
                break
            except TelegramNetworkError as e:
                logging.warning("Network error on startup, retrying in 5s: %s", e)
                await asyncio.sleep(5)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

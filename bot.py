import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from config import ADMIN_IDS
from handlers.post import router as post_router


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    post_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
    post_router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))
    dp.include_router(post_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

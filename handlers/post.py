import logging
import os
from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
)
from services.watermark import process_watermark
from config import CHANNEL_ID, CHANNEL_USERNAME, WATERMARK_TEXT

logger = logging.getLogger(__name__)
router = Router()


class PostStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_caption = State()


@router.message(Command("post"))
async def start_post(message: Message, state: FSMContext):
    await state.set_state(PostStates.waiting_for_photo)
    await message.answer("Send the photo you want to post.")


@router.message(PostStates.waiting_for_photo, F.photo)
async def got_photo(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(PostStates.waiting_for_caption)
    await message.answer("Now send the caption.")


@router.message(PostStates.waiting_for_photo)
async def wrong_photo_input(message: Message):
    await message.answer("That's not a photo. Please send a photo, or /cancel.")


@router.message(PostStates.waiting_for_caption, F.text)
async def got_caption(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    caption = message.text

    try:
        file = await bot.get_file(data["photo_file_id"])
        watermarked_path = await process_watermark(bot, file, WATERMARK_TEXT, file.file_unique_id)
    except Exception as e:
        logger.error("Watermark processing failed: %s", e)
        await message.answer("Failed to process the image. Please try again with /post.")
        await state.clear()
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Posting on channel", callback_data="post_to_channel")
    ]])
    preview_msg = await message.answer_photo(FSInputFile(watermarked_path), caption=caption, reply_markup=kb)
    await state.update_data(watermarked_path=watermarked_path, caption=caption, preview_msg_id=preview_msg.message_id)
    await state.set_state(None)


@router.message(PostStates.waiting_for_caption)
async def wrong_caption_input(message: Message):
    await message.answer("Please send a text caption, or /cancel.")


@router.callback_query(F.data == "post_to_channel")
async def publish_to_channel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if "watermarked_path" not in data:
        await callback.answer("Nothing to post — start again with /post.", show_alert=True)
        return

    try:
        sent = await bot.send_photo(CHANNEL_ID, FSInputFile(data["watermarked_path"]), caption=data["caption"])
    except Exception as e:
        logger.error("Failed to post to channel: %s", e)
        await callback.answer("Failed to post to channel. Check bot permissions.", show_alert=True)
        return

    if CHANNEL_USERNAME:
        posted_button = InlineKeyboardButton(text="Posted ✅", url=f"https://t.me/{CHANNEL_USERNAME}/{sent.message_id}")
    else:
        posted_button = InlineKeyboardButton(text="Posted ✅", callback_data="posted_noop")
    new_kb = InlineKeyboardMarkup(inline_keyboard=[[posted_button]])
    await callback.message.edit_reply_markup(reply_markup=new_kb)
    await callback.answer("Posted!")

    for path in (data["watermarked_path"], data["watermarked_path"].replace("_wm.jpg", ".jpg")):
        try:
            os.remove(path)
        except OSError:
            pass

    await state.clear()


@router.callback_query(F.data == "posted_noop")
async def posted_noop(callback: CallbackQuery):
    await callback.answer()


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.")

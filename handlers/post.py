import logging
import os
from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, InputMediaPhoto,
)
from services.watermark import process_watermark
from config import CHANNEL_ID, CHANNEL_USERNAME, WATERMARK_TEXT

logger = logging.getLogger(__name__)
router = Router()

MAX_PHOTOS = 10


class PostStates(StatesGroup):
    collecting_photos = State()
    waiting_for_caption = State()


def _collection_kb(count: int) -> InlineKeyboardMarkup:
    buttons = []
    if count < MAX_PHOTOS:
        buttons.append(InlineKeyboardButton(text="➕ Add photo", callback_data="add_photo"))
    buttons.append(InlineKeyboardButton(text="✅ Done", callback_data="done_collecting"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


# photo sent with no active state -> start the flow
@router.message(StateFilter(None), F.photo)
async def got_first_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(photo_file_ids=[file_id])
    await state.set_state(PostStates.collecting_photos)
    ctrl = await message.answer("1 photo added.", reply_markup=_collection_kb(1))
    await state.update_data(ctrl_msg_id=ctrl.message_id)


# additional photos while collecting
@router.message(PostStates.collecting_photos, F.photo)
async def got_extra_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ids: list = data["photo_file_ids"]
    if len(ids) >= MAX_PHOTOS:
        await message.answer(f"Maximum {MAX_PHOTOS} photos reached.")
        return
    ids.append(message.photo[-1].file_id)
    await state.update_data(photo_file_ids=ids)
    await bot.edit_message_text(
        f"{len(ids)} photo(s) added.",
        chat_id=message.chat.id,
        message_id=data["ctrl_msg_id"],
        reply_markup=_collection_kb(len(ids)),
    )


@router.message(PostStates.collecting_photos)
async def wrong_input_collecting(message: Message):
    await message.answer("Send a photo, tap ➕ to add more, or ✅ Done when finished.")


@router.callback_query(F.data == "add_photo", PostStates.collecting_photos)
async def prompt_add_photo(callback: CallbackQuery):
    await callback.answer("Send the next photo.")


@router.callback_query(F.data == "done_collecting", PostStates.collecting_photos)
async def done_collecting(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PostStates.waiting_for_caption)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Now send the caption.")


@router.message(PostStates.waiting_for_caption, F.text)
async def got_caption(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    caption = message.text
    ids: list = data["photo_file_ids"]

    # watermark all photos
    watermarked_paths = []
    try:
        for file_id in ids:
            file = await bot.get_file(file_id)
            path = await process_watermark(bot, file, WATERMARK_TEXT, file.file_unique_id)
            watermarked_paths.append(path)
    except Exception as e:
        logger.error("Watermark processing failed: %s", e)
        await message.answer("Failed to process images. Please try again by sending a photo.")
        await state.clear()
        return

    # send preview album
    media = [InputMediaPhoto(media=FSInputFile(p)) for p in watermarked_paths]
    media[-1] = InputMediaPhoto(media=FSInputFile(watermarked_paths[-1]), caption=caption)
    await message.answer_media_group(media=media)

    # separate control message
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Post to channel", callback_data="post_to_channel")
    ]])
    ctrl = await message.answer("Ready to post.", reply_markup=kb)
    await state.update_data(watermarked_paths=watermarked_paths, caption=caption, ctrl_msg_id=ctrl.message_id)
    await state.set_state(None)


@router.message(PostStates.waiting_for_caption)
async def wrong_caption_input(message: Message):
    await message.answer("Please send a text caption, or /cancel.")


@router.callback_query(F.data == "post_to_channel")
async def publish_to_channel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if "watermarked_paths" not in data:
        await callback.answer("Nothing to post — send a photo to start again.", show_alert=True)
        return

    paths: list = data["watermarked_paths"]
    caption: str = data["caption"]

    try:
        media = [InputMediaPhoto(media=FSInputFile(p)) for p in paths]
        media[-1] = InputMediaPhoto(media=FSInputFile(paths[-1]), caption=caption)
        sent = await bot.send_media_group(CHANNEL_ID, media=media)
    except Exception as e:
        logger.error("Failed to post to channel: %s", e)
        await callback.answer("Failed to post to channel. Check bot permissions.", show_alert=True)
        return

    # sent is a list of messages; link to the first one
    first_msg_id = sent[0].message_id
    if CHANNEL_USERNAME:
        posted_button = InlineKeyboardButton(text="Posted ✅", url=f"https://t.me/{CHANNEL_USERNAME}/{first_msg_id}")
    else:
        posted_button = InlineKeyboardButton(text="Posted ✅", callback_data="posted_noop")
    await callback.message.edit_text("Posted.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[posted_button]]))
    await callback.answer("Posted!")

    for p in paths:
        for path in (p, p.replace("_wm.jpg", ".jpg")):
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

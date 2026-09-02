import logging
import os
import asyncio
from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, InputMediaPhoto, MessageEntity,
)
from services.watermark import process_watermark
from config import CHANNEL_ID, CHANNEL_USERNAME, WATERMARK_TEXT

logger = logging.getLogger(__name__)
router = Router()

MAX_PHOTOS = 10
BURST_TIMEOUT = 1.0  # seconds to wait for more photos in a burst
PROGRESS_STEPS = ["⬜⬜⬜⬜⬜", "⬛⬜⬜⬜⬜", "⬛⬛⬜⬜⬜", "⬛⬛⬛⬜⬜", "⬛⬛⬛⬛⬜", "⬛⬛⬛⬛⬛"]

# per-user burst timer tasks
_burst_tasks: dict[int, asyncio.Task] = {}


class PostStates(StatesGroup):
    collecting_photos = State()
    waiting_for_caption = State()


def _collection_kb(count: int) -> InlineKeyboardMarkup:
    buttons = []
    if count < MAX_PHOTOS:
        buttons.append(InlineKeyboardButton(text="➕ Add photo", callback_data="add_photo"))
    buttons.append(InlineKeyboardButton(text="✅ Done", callback_data="done_collecting"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


async def _refresh_ctrl(bot: Bot, chat_id: int, state: FSMContext, text: str, kb: InlineKeyboardMarkup | None):
    """Delete the old control message and send a new one at the bottom."""
    data = await state.get_data()
    old_id = data.get("ctrl_msg_id")
    if old_id:
        try:
            await bot.delete_message(chat_id, old_id)
        except Exception:
            pass
    ctrl = await bot.send_message(chat_id, text, reply_markup=kb)
    await state.update_data(ctrl_msg_id=ctrl.message_id)
    return ctrl


async def _flush_burst(user_id: int, chat_id: int, bot: Bot, state: FSMContext):
    """Called after BURST_TIMEOUT — update the control message with final count."""
    await asyncio.sleep(BURST_TIMEOUT)
    data = await state.get_data()
    ids: list = data.get("photo_file_ids", [])
    await _refresh_ctrl(bot, chat_id, state, f"{len(ids)} photo(s) added.", _collection_kb(len(ids)))
    _burst_tasks.pop(user_id, None)


def _schedule_burst(user_id: int, chat_id: int, bot: Bot, state: FSMContext):
    """Cancel any existing burst timer and start a fresh one."""
    existing = _burst_tasks.pop(user_id, None)
    if existing:
        existing.cancel()
    _burst_tasks[user_id] = asyncio.create_task(_flush_burst(user_id, chat_id, bot, state))


# photo sent with no active state -> start the flow
@router.message(StateFilter(None), F.photo)
async def got_first_photo(message: Message, state: FSMContext, bot: Bot):
    await state.set_state(PostStates.collecting_photos)
    await state.update_data(photo_file_ids=[message.photo[-1].file_id])
    _schedule_burst(message.from_user.id, message.chat.id, bot, state)


# additional photos while collecting
@router.message(PostStates.collecting_photos, F.photo)
async def got_extra_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ids: list = data.get("photo_file_ids", [])
    if len(ids) >= MAX_PHOTOS:
        await message.answer(f"Maximum {MAX_PHOTOS} photos reached.")
        return
    ids.append(message.photo[-1].file_id)
    await state.update_data(photo_file_ids=ids)
    _schedule_burst(message.from_user.id, message.chat.id, bot, state)


@router.message(PostStates.collecting_photos)
async def wrong_input_collecting(message: Message):
    await message.answer("Send a photo, tap ➕ to add more, or ✅ Done when finished.")


@router.callback_query(F.data == "add_photo", PostStates.collecting_photos)
async def prompt_add_photo(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    count = len(data["photo_file_ids"])
    await callback.message.edit_text(
        f"{count} photo(s) added. Send the new photo(s) you want to add.",
        reply_markup=_collection_kb(count),
    )


@router.callback_query(F.data == "done_collecting", PostStates.collecting_photos)
async def done_collecting(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(PostStates.waiting_for_caption)
    await callback.message.answer("Now send the caption.")


@router.message(PostStates.waiting_for_caption, F.text)
async def got_caption(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    caption = message.text
    entities = message.entities  # preserve formatting
    ids: list = data["photo_file_ids"]

    # show loading indicator
    progress_msg = await message.answer(PROGRESS_STEPS[0])

    watermarked_paths = []
    try:
        for i, file_id in enumerate(ids):
            step = min(1 + i, len(PROGRESS_STEPS) - 1)
            await progress_msg.edit_text(PROGRESS_STEPS[step])
            file = await bot.get_file(file_id)
            path = await process_watermark(bot, file, WATERMARK_TEXT, file.file_unique_id)
            watermarked_paths.append(path)
    except Exception as e:
        logger.error("Watermark processing failed: %s", e)
        await progress_msg.edit_text("Failed to process images. Please try again by sending a photo.")
        await state.clear()
        return

    await progress_msg.edit_text(PROGRESS_STEPS[-1])

    # send preview album
    media = [InputMediaPhoto(media=FSInputFile(p)) for p in watermarked_paths]
    media[-1] = InputMediaPhoto(media=FSInputFile(watermarked_paths[-1]), caption=caption, caption_entities=entities)
    await message.answer_media_group(media=media)

    await progress_msg.delete()

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Post to channel", callback_data="post_to_channel")
    ]])
    ctrl = await message.answer("Ready to post.", reply_markup=kb)
    await state.update_data(watermarked_paths=watermarked_paths, caption=caption, caption_entities=entities, ctrl_msg_id=ctrl.message_id)
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
    entities: list[MessageEntity] | None = data.get("caption_entities")

    await callback.answer()
    await callback.message.edit_text(PROGRESS_STEPS[0], reply_markup=None)

    try:
        media = [InputMediaPhoto(media=FSInputFile(p)) for p in paths]
        media[-1] = InputMediaPhoto(media=FSInputFile(paths[-1]), caption=caption, caption_entities=entities)
        await callback.message.edit_text(PROGRESS_STEPS[3])
        sent = await bot.send_media_group(CHANNEL_ID, media=media)
    except Exception as e:
        logger.error("Failed to post to channel: %s", e)
        await callback.message.edit_text("Failed to post to channel. Check bot permissions.")
        return

    await callback.message.edit_text(PROGRESS_STEPS[-1])

    first_msg_id = sent[0].message_id
    if CHANNEL_USERNAME:
        posted_button = InlineKeyboardButton(text="Posted ✅", url=f"https://t.me/{CHANNEL_USERNAME}/{first_msg_id}")
    else:
        posted_button = InlineKeyboardButton(text="Posted ✅", callback_data="posted_noop")
    await callback.message.edit_text("Posted.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[posted_button]]))

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
    task = _burst_tasks.pop(message.from_user.id, None)
    if task:
        task.cancel()
    await state.clear()
    await message.answer("Cancelled.")

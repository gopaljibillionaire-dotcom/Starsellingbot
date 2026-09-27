import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime, timezone

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

import config

# Logging setup
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Image URLs
WELCOME_IMG = (
    "https://i.ibb.co/My1BkdpV/file-0000000064bc81fa8bb2f564b659595c.png"
)
PROFILE_IMG = (
    "https://i.ibb.co/v676k8DR/file-00000000203c81fa91ce6bf539ba341e.png"
)
WALLET_IMG = (
    "https://i.ibb.co/5W2WG0sJ/file-00000000d33481f588663976b70e3955.png"
)
SETTINGS_IMG = (
    "https://i.ibb.co/27qkfwJB/file-0000000091a881fa820cc7d0a6196bc9.png"
)
BUY_STARS_IMG = (
    "https://i.ibb.co/v6XtXbCm/file-00000000e2e4820b81dc1c9bfa29fe93.png"
)

# Initialize Bot, DB, and Router
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

mongo_client = AsyncIOMotorClient(config.MONGO_URI)
db = mongo_client[config.DATABASE_NAME]

# Collections
users_col = db["users"]
packs_col = db["packs"]
orders_col = db["orders"]
deposits_col = db["deposits"]

# Price Cache Setup (Reduces Latency)
PRICE_CACHE = {}
CACHE_TTL = 60  # seconds

# --- Translations Dictionary ---
I18N = {
    "en": {
        "welcome": (
            "<b>Welcome to our Telegram Stars Shop!</b> ⭐\n\n"
            "Use our service to buy Telegram Stars at the cheapest prices on the market.\n\n"
            "<blockquote>Best Telegram bot for buying stars at cheap!</blockquote>\n\n"
            "Choose an option below to get started:"
        ),
        "buy_stars": "⭐ Buy Stars",
        "topup": "💰 Top Up Wallet",
        "profile": "👤 Profile",
        "settings": "⚙️ Settings",
        "admin_panel": "👑 Admin Panel",
        "back": "⬅️ Back",
        "lang_select": "<b>Choose your language / Select your language:</b>",
        "lang_changed": "✅ Language changed to English!",
        "profile_text": (
            "<b>👤 User Profile</b>\n\n"
            "<b>Name:</b> {first_name}\n"
            "<b>Username:</b> @{username}\n"
            "<b>User ID:</b> <code>{user_id}</code>\n"
            "<b>Wallet Balance:</b> ${balance:.2f} USD\n"
            "<b>Total Spend:</b> ${total_purchases:.2f} USD\n"
            "<b>Total Stars Bought:</b> {total_stars} ⭐\n"
            "<b>Total Orders:</b> {total_orders}"
        ),
        "my_orders": "📦 My Orders",
        "wallet": "💳 Wallet Details",
        "wallet_info": (
            "<b>💳 Wallet Summary</b>\n\n"
            "<b>Available Balance:</b> ${balance:.2f} USD\n"
            "<b>Total Deposited:</b> ${total_deposits:.2f} USD"
        ),
        "enter_deposit_amount": (
            f"Enter the deposit amount in USD (${config.MIN_DEPOSIT} -"
            f" ${config.MAX_DEPOSIT}):"
        ),
        "invalid_amount": (
            "❌ Invalid amount. Please enter a valid number within limits."
        ),
        "select_crypto": "Select the cryptocurrency you want to pay with:",
        "deposit_instruction": (
            "<b>💰 Payment Invoice</b>\n\n"
            "<b>Deposit Amount:</b> ${usd_amount:.2f} USD\n"
            "<b>Pay Amount:</b> <code>{crypto_amount:.6f}</code> {symbol}\n"
            "<b>Exchange Rate:</b> 1 {symbol} = ${rate:.2f} USD\n"
            "<b>Network:</b> {crypto}\n\n"
            "<b>Deposit Address:</b>\n<code>{address}</code>\n\n"
            "<b>Deposit ID:</b> <code>{deposit_id}</code>\n\n"
            "⚠️ Send the EXACT amount to the address above before submitting"
            " payment proof."
        ),
        "i_have_paid": "✅ I Have Paid",
        "enter_tx_id": (
            "Please send your **Transaction ID / TX Hash** for verification:"
        ),
        "upload_proof": (
            "Please upload a clear screenshot of your **Payment Proof**:"
        ),
        "proof_submitted": (
            "✅ <b>Payment Proof Submitted!</b>\n\n"
            "Your payment has been forwarded to the administration team for"
            " verification.\n\n"
            "<b>Deposit ID:</b> <code>{deposit_id}</code>\n"
            "<b>TX ID:</b> <code>{tx_id}</code>\n\n"
            "After verification by the owner, you will be able to receive your"
            " Stars or Wallet balance credited.\n\n"
            "📩 <b>Send receipt to @exesiners to claim your Stars!</b>"
        ),
        "insufficient_balance": (
            "❌ <b>Insufficient balance!</b>\n\nPlease top up your wallet"
            " before purchasing stars."
        ),
        "order_success": (
            "✅ <b>You are all set!</b>\n\n"
            "Your order has been successfully placed.\n\n"
            "Now DM the owner @exesiners to claim your Stars. Send them the"
            " receipt below after approval."
        ),
        "contact_owner": "💬 Contact Owner",
        "receipt": (
            "🧾 <b>Order Receipt</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "<b>Order ID:</b> <code>{order_id}</code>\n"
            "<b>User ID:</b> <code>{user_id}</code>\n"
            "<b>Stars:</b> {stars} ⭐\n"
            "<b>Paid:</b> ${price:.2f} USD\n"
            "<b>Payment Method:</b> Wallet Balance\n"
            "<b>Status:</b> {status}\n"
            "<b>Date:</b> {date}\n"
            "━━━━━━━━━━━━━━━━━━"
        ),
    },
    "ru": {
        "welcome": (
            "<b>Добро пожаловать в магазин Telegram Stars!</b> ⭐\n\n"
            "Используйте наш сервис для покупки Звезд Telegram по самым"
            " выгодным ценам.\n\n"
            "<blockquote>Best Telegram bot for buying stars at cheap!</blockquote>\n\n"
            "Выберите опцию ниже, чтобы начать:"
        ),
        "buy_stars": "⭐ Купить Звезды",
        "topup": "💰 Пополнить Баланс",
        "profile": "👤 Профиль",
        "settings": "⚙️ Настройки",
        "admin_panel": "👑 Админ Панель",
        "back": "⬅️ Назад",
        "lang_select": "<b>Выберите язык / Select your language:</b>",
        "lang_changed": "✅ Язык успешно изменен на Русский!",
        "profile_text": (
            "<b>👤 Профиль Пользователя</b>\n\n"
            "<b>Имя:</b> {first_name}\n"
            "<b>Юзернейм:</b> @{username}\n"
            "<b>ID Пользователя:</b> <code>{user_id}</code>\n"
            "<b>Баланс Кошелька:</b> ${balance:.2f} USD\n"
            "<b>Всего Потрачено:</b> ${total_purchases:.2f} USD\n"
            "<b>Куплено Звезд:</b> {total_stars} ⭐\n"
            "<b>Всего Заказов:</b> {total_orders}"
        ),
        "my_orders": "📦 Мои Заказы",
        "wallet": "💳 Кошелек",
        "wallet_info": (
            "<b>💳 Информация о Кошельке</b>\n\n"
            "<b>Доступный Баланс:</b> ${balance:.2f} USD\n"
            "<b>Всего Пополнено:</b> ${total_deposits:.2f} USD"
        ),
        "enter_deposit_amount": (
            f"Введите сумму пополнения в USD (${config.MIN_DEPOSIT} -"
            f" ${config.MAX_DEPOSIT}):"
        ),
        "invalid_amount": (
            "❌ Некорректная сумма. Введите число в пределах допустимого лимита."
        ),
        "select_crypto": "Выберите криптовалюту для оплаты:",
        "deposit_instruction": (
            "<b>💰 Счет на Оплату</b>\n\n"
            "<b>Сумма пополнения:</b> ${usd_amount:.2f} USD\n"
            "<b>К оплате:</b> <code>{crypto_amount:.6f}</code> {symbol}\n"
            "<b>Курс обмена:</b> 1 {symbol} = ${rate:.2f} USD\n"
            "<b>Сеть:</b> {crypto}\n\n"
            "<b>Адрес Пополнения:</b>\n<code>{address}</code>\n\n"
            "<b>ID Депозита:</b> <code>{deposit_id}</code>\n\n"
            "⚠️ Отправьте ТОЧНУЮ сумму на указанный адрес."
        ),
        "i_have_paid": "✅ Я оплатил",
        "enter_tx_id": (
            "Пожалуйста, отправьте ваш **Transaction ID / TX Hash** для"
            " проверки:"
        ),
        "upload_proof": (
            "Пожалуйста, загрузите скриншот **Подтверждения Оплаты**:"
        ),
        "proof_submitted": (
            "✅ <b>Payment Proof Submitted!</b>\n\n"
            "Your payment has been forwarded to the administration team for"
            " verification.\n\n"
            "<b>Deposit ID:</b> <code>{deposit_id}</code>\n"
            "<b>TX ID:</b> <code>{tx_id}</code>\n\n"
            "After verification by the owner, you will be able to receive your"
            " Stars or Wallet balance credited.\n\n"
            "📩 <b>Send receipt to @exesiners to claim your Stars!</b>"
        ),
        "insufficient_balance": (
            "❌ <b>Недостаточно средств!</b>\n\nПожалуйста, пополните ваш"
            " кошелек."
        ),
        "order_success": (
            "✅ <b>Заказ успешно оформлен!</b>\n\n"
            "Напишите владельцу @exesiners, чтобы получить Stars. Отправьте чек"
            " ниже для подтверждения."
        ),
        "contact_owner": "💬 Написать Владельцу",
        "receipt": (
            "🧾 <b>Чек Заказа</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "<b>ID Заказа:</b> <code>{order_id}</code>\n"
            "<b>ID Пользователя:</b> <code>{user_id}</code>\n"
            "<b>Звезды:</b> {stars} ⭐\n"
            "<b>Оплачено:</b> ${price:.2f} USD\n"
            "<b>Способ:</b> Баланс кошелька\n"
            "<b>Статус:</b> {status}\n"
            "<b>Дата:</b> {date}\n"
            "━━━━━━━━━━━━━━━━━━"
        ),
    },
}


# --- Safe Button Helper ---
def create_button(
    text: str, callback_data: str, style: str = "primary"
) -> InlineKeyboardButton:
    try:
        return InlineKeyboardButton(
            text=text, callback_data=callback_data, style=style
        )
    except TypeError:
        return InlineKeyboardButton(text=text, callback_data=callback_data)


# --- FSM States ---
class TopUpStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_tx_id = State()
    waiting_for_proof_photo = State()


class AdminPackStates(StatesGroup):
    waiting_for_stars = State()
    waiting_for_price = State()


class AdminBroadcastStates(StatesGroup):
    waiting_for_content = State()
    confirm_broadcast = State()


# --- Helper Utilities ---
async def get_user_lang(user_id: int) -> str:
    user = await users_col.find_one({"user_id": user_id}, {"language": 1})
    return (
        user.get("language", config.DEFAULT_LANGUAGE)
        if user
        else config.DEFAULT_LANGUAGE
    )


async def get_crypto_price(symbol: str) -> float:
    now = time.time()
    if symbol in PRICE_CACHE and (now - PRICE_CACHE[symbol]["time"] < CACHE_TTL):
        return PRICE_CACHE[symbol]["price"]

    symbol_map = {
        "BTC": "BTC",
        "ETH": "ETH",
        "LTC": "LTC",
        "SOL": "SOL",
        "BNB": "BNB",
    }
    ticker = symbol_map.get(symbol, symbol)
    url = f"https://api.coinbase.com/v2/prices/{ticker}-USD/spot"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=3) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    val = float(data["data"]["amount"])
                    PRICE_CACHE[symbol] = {"price": val, "time": now}
                    return val
    except Exception as e:
        logger.error(f"Price fetch failed: {e}")

    defaults = {
        "BTC": 65000.0,
        "ETH": 3500.0,
        "LTC": 85.0,
        "SOL": 140.0,
        "BNB": 580.0,
    }
    return defaults.get(symbol, 1.0)


def main_menu_keyboard(lang: str, is_admin: bool) -> InlineKeyboardMarkup:
    kb = [
        [create_button(I18N[lang]["buy_stars"], "user_buy_stars", "success")],
        [
            create_button(I18N[lang]["topup"], "user_topup", "primary"),
            create_button(I18N[lang]["profile"], "user_profile", "primary"),
        ],
        [create_button(I18N[lang]["settings"], "user_settings", "primary")],
    ]
    if is_admin:
        kb.append(
            [create_button(I18N[lang]["admin_panel"], "admin_main", "danger")]
        )
    return InlineKeyboardMarkup(inline_keyboard=kb)


# --- Command Handlers ---
@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "N/A"
    first_name = message.from_user.first_name or "User"

    await users_col.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "balance": 0.0,
                "total_deposits": 0.0,
                "total_purchases": 0.0,
                "total_stars": 0,
                "language": config.DEFAULT_LANGUAGE,
                "joined_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )

    lang = await get_user_lang(user_id)
    is_admin = user_id in config.ADMIN_IDS
    await message.answer_photo(
        photo=WELCOME_IMG,
        caption=I18N[lang]["welcome"],
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(lang, is_admin),
    )


# --- Settings & Language Management ---
@router.callback_query(F.data == "user_settings")
async def cb_settings(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                create_button("🇬🇧 English", "set_lang_en", "primary"),
                create_button("🇷🇺 Русский", "set_lang_ru", "primary"),
            ],
            [create_button(I18N[lang]["back"], "main_menu", "primary")],
        ]
    )
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=SETTINGS_IMG,
            caption=I18N[lang]["lang_select"],
            parse_mode="HTML",
        ),
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("set_lang_"))
async def cb_set_language(callback: CallbackQuery):
    new_lang = callback.data.split("_")[-1]
    await users_col.update_one(
        {"user_id": callback.from_user.id}, {"$set": {"language": new_lang}}
    )
    is_admin = callback.from_user.id in config.ADMIN_IDS
    await callback.answer(I18N[new_lang]["lang_changed"], show_alert=True)
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=WELCOME_IMG,
            caption=I18N[new_lang]["welcome"],
            parse_mode="HTML",
        ),
        reply_markup=main_menu_keyboard(new_lang, is_admin),
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    await callback.answer()
    lang = await get_user_lang(callback.from_user.id)
    is_admin = callback.from_user.id in config.ADMIN_IDS
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=WELCOME_IMG,
            caption=I18N[lang]["welcome"],
            parse_mode="HTML",
        ),
        reply_markup=main_menu_keyboard(lang, is_admin),
    )


# --- Profile Section ---
@router.callback_query(F.data == "user_profile")
async def cb_profile(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await users_col.find_one({"user_id": user_id})
    lang = await get_user_lang(user_id)

    order_count = await orders_col.count_documents({"user_id": user_id})

    text = I18N[lang]["profile_text"].format(
        first_name=user.get("first_name", "User") if user else "User",
        username=user.get("username", "N/A") if user else "N/A",
        user_id=user_id,
        balance=user.get("balance", 0.0) if user else 0.0,
        total_purchases=user.get("total_purchases", 0.0) if user else 0.0,
        total_stars=user.get("total_stars", 0) if user else 0,
        total_orders=order_count,
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                create_button(I18N[lang]["wallet"], "user_wallet", "primary"),
                create_button(
                    I18N[lang]["my_orders"], "my_orders_0", "primary"
                ),
            ],
            [create_button(I18N[lang]["back"], "main_menu", "primary")],
        ]
    )
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=PROFILE_IMG, caption=text, parse_mode="HTML"
        ),
        reply_markup=kb,
    )


# --- My Orders Pagination ---
@router.callback_query(F.data.startswith("my_orders_"))
async def cb_my_orders(callback: CallbackQuery):
    page = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)

    limit = 5
    skip = page * limit
    cursor = (
        orders_col.find({"user_id": user_id})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )
    orders = await cursor.to_list(length=limit)
    total_orders = await orders_col.count_documents({"user_id": user_id})

    if not orders:
        await callback.answer("No orders found.", show_alert=True)
        return

    text = "<b>📦 Purchase History:</b>\n\n"
    for o in orders:
        created_date = (
            o["created_at"].strftime("%Y-%m-%d")
            if isinstance(o["created_at"], datetime)
            else "N/A"
        )
        text += (
            f"• <b>Order #{o['order_id']}</b>\n"
            f"  Stars: {o['stars']} ⭐ | Price: ${o['price']:.2f}\n"
            f"  Status: <code>{o['status']}</code> | Date: {created_date}\n\n"
        )

    nav_btns = []
    if page > 0:
        nav_btns.append(
            create_button("⬅️ Prev", f"my_orders_{page-1}", "primary")
        )
    if skip + limit < total_orders:
        nav_btns.append(
            create_button("Next ➡️", f"my_orders_{page+1}", "primary")
        )

    kb = []
    if nav_btns:
        kb.append(nav_btns)
    kb.append([create_button(I18N[lang]["back"], "user_profile", "primary")])

    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=PROFILE_IMG, caption=text, parse_mode="HTML"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )


# --- Wallet & Deposit Flow ---
@router.callback_query(F.data == "user_wallet")
async def cb_wallet(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    user = await users_col.find_one({"user_id": user_id})
    lang = await get_user_lang(user_id)

    text = I18N[lang]["wallet_info"].format(
        balance=user.get("balance", 0.0) if user else 0.0,
        total_deposits=user.get("total_deposits", 0.0) if user else 0.0,
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [create_button(I18N[lang]["topup"], "user_topup", "success")],
            [create_button(I18N[lang]["back"], "user_profile", "primary")],
        ]
    )
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=WALLET_IMG, caption=text, parse_mode="HTML"
        ),
        reply_markup=kb,
    )


@router.callback_query(F.data == "user_topup")
async def cb_topup_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    lang = await get_user_lang(callback.from_user.id)
    await state.set_state(TopUpStates.waiting_for_amount)
    await callback.message.answer(I18N[lang]["enter_deposit_amount"])


@router.message(TopUpStates.waiting_for_amount)
async def process_deposit_amount(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    try:
        amount = float(message.text.replace("$", "").strip())
        if amount < config.MIN_DEPOSIT or amount > config.MAX_DEPOSIT:
            raise ValueError()
    except ValueError:
        await message.answer(I18N[lang]["invalid_amount"])
        return

    await state.update_data(deposit_usd=amount)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                create_button("BTC (Bitcoin)", "pay_BTC", "primary"),
                create_button("ETH (Ethereum)", "pay_ETH", "primary"),
            ],
            [
                create_button("LTC (Litecoin)", "pay_LTC", "primary"),
                create_button("SOL (Solana)", "pay_SOL", "primary"),
            ],
            [create_button("BNB (Binance Coin)", "pay_BNB", "primary")],
            [create_button(I18N[lang]["back"], "main_menu", "danger")],
        ]
    )
    await message.answer_photo(
        photo=WALLET_IMG, caption=I18N[lang]["select_crypto"], reply_markup=kb
    )


@router.callback_query(F.data.startswith("pay_"))
async def process_crypto_payment(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    symbol = callback.data.split("_")[1]
    data = await state.get_data()
    usd_amount = data.get("deposit_usd", 10.0)
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)

    rate = await get_crypto_price(symbol)
    crypto_amount = usd_amount / rate
    deposit_id = f"DEP-{uuid.uuid4().hex[:8].upper()}"
    address = config.CRYPTO_ADDRESSES.get(symbol, "Address Not Configured")

    await deposits_col.insert_one(
        {
            "deposit_id": deposit_id,
            "user_id": user_id,
            "usd_amount": usd_amount,
            "crypto": symbol,
            "crypto_amount": crypto_amount,
            "address": address,
            "status": "pending_proof",
            "created_at": datetime.now(timezone.utc),
        }
    )

    text = I18N[lang]["deposit_instruction"].format(
        usd_amount=usd_amount,
        crypto_amount=crypto_amount,
        symbol=symbol,
        rate=rate,
        crypto=symbol,
        address=address,
        deposit_id=deposit_id,
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                create_button(
                    I18N[lang]["i_have_paid"],
                    f"ihavepaid_{deposit_id}",
                    "success",
                )
            ],
            [create_button(I18N[lang]["back"], "main_menu", "primary")],
        ]
    )
    await state.clear()

    if callback.message.photo:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=WALLET_IMG, caption=text, parse_mode="HTML"
            ),
            reply_markup=kb,
        )
    else:
        await callback.message.answer_photo(
            photo=WALLET_IMG, caption=text, parse_mode="HTML", reply_markup=kb
        )


# --- Payment Proof Upload Flow ---
@router.callback_query(F.data.startswith("ihavepaid_"))
async def process_i_have_paid(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    deposit_id = callback.data.split("ihavepaid_")[1]
    lang = await get_user_lang(callback.from_user.id)
    await state.update_data(current_dep_id=deposit_id)
    await state.set_state(TopUpStates.waiting_for_tx_id)
    await callback.message.answer(
        I18N[lang]["enter_tx_id"], parse_mode="Markdown"
    )


@router.message(TopUpStates.waiting_for_tx_id)
async def process_tx_id_input(message: Message, state: FSMContext):
    lang = await get_user_lang(message.from_user.id)
    tx_id = message.text.strip()
    await state.update_data(tx_id=tx_id)
    await state.set_state(TopUpStates.waiting_for_proof_photo)
    await message.answer(I18N[lang]["upload_proof"], parse_mode="Markdown")


@router.message(TopUpStates.waiting_for_proof_photo, F.photo)
async def process_proof_photo_upload(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await get_user_lang(user_id)
    data = await state.get_data()

    deposit_id = data.get("current_dep_id")
    tx_id = data.get("tx_id")
    photo_file_id = message.photo[-1].file_id

    # Update deposit status in DB
    deposit = await deposits_col.find_one_and_update(
        {"deposit_id": deposit_id},
        {
            "$set": {
                "status": "pending_approval",
                "tx_id": tx_id,
                "photo_id": photo_file_id,
            }
        },
    )

    await state.clear()

    # Dynamic Confirmation Receipt Message
    msg = I18N[lang]["proof_submitted"].format(
        deposit_id=deposit_id, tx_id=tx_id
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Contact Owner", url="https://t.me/exesiners"
                )
            ],
            [create_button(I18N[lang]["back"], "main_menu", "primary")],
        ]
    )
    await message.answer(msg, parse_mode="HTML", reply_markup=kb)

    # Forward Proof directly to Admins for manual review
    usd_val = deposit.get("usd_amount", 0.0) if deposit else 0.0
    crypto_val = deposit.get("crypto_amount", 0.0) if deposit else 0.0
    crypto_sym = deposit.get("crypto", "CRYPTO") if deposit else "CRYPTO"

    admin_caption = (
        f"🚨 <b>NEW DEPOSIT VERIFICATION REQUEST</b>\n\n"
        f"<b>Deposit ID:</b> <code>{deposit_id}</code>\n"
        f"<b>User ID:</b> <code>{user_id}</code>"
        f" (@{message.from_user.username or 'N/A'})\n"
        f"<b>Amount:</b> ${usd_val:.2f} USD\n"
        f"<b>Crypto:</b> {crypto_val:.6f} {crypto_sym}\n"
        f"<b>TX ID:</b> <code>{tx_id}</code>"
    )

    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                create_button(
                    "✅ Approve Deposit",
                    f"adm_app_dep_{deposit_id}",
                    "success",
                ),
                create_button(
                    "❌ Reject Deposit", f"adm_rej_dep_{deposit_id}", "danger"
                ),
            ]
        ]
    )

    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                photo=photo_file_id,
                caption=admin_caption,
                parse_mode="HTML",
                reply_markup=admin_kb,
            )
        except Exception as e:
            logger.error(f"Failed sending admin alert to {admin_id}: {e}")


# Admin Deposit Approval / Rejection Handlers
@router.callback_query(F.data.startswith("adm_app_dep_"))
async def cb_approve_deposit(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
    deposit_id = callback.data.split("adm_app_dep_")[1]

    deposit = await deposits_col.find_one_and_update(
        {"deposit_id": deposit_id, "status": "pending_approval"},
        {
            "$set": {
                "status": "completed",
                "approved_at": datetime.now(timezone.utc),
            }
        },
    )

    if deposit:
        usd_amount = deposit["usd_amount"]
        user_id = deposit["user_id"]

        # Credit user balance
        await users_col.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": usd_amount, "total_deposits": usd_amount}},
        )

        await callback.answer("Deposit Approved & Credited!", show_alert=True)
        await callback.message.edit_caption(
            caption=(callback.message.caption or "")
            + "\n\n🟢 <b>APPROVED BY ADMIN</b>",
            parse_mode="HTML",
        )

        try:
            await bot.send_message(
                user_id,
                f"🎉 <b>Deposit Approved!</b>\n\nYour deposit"
                f" <code>{deposit_id}</code> for ${usd_amount:.2f} USD has been"
                " approved! Balance credited to your wallet.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to alert user: {e}")
    else:
        await callback.answer("Deposit already processed.", show_alert=True)


@router.callback_query(F.data.startswith("adm_rej_dep_"))
async def cb_reject_deposit(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        return
    deposit_id = callback.data.split("adm_rej_dep_")[1]

    deposit = await deposits_col.find_one_and_update(
        {"deposit_id": deposit_id, "status": "pending_approval"},
        {
            "$set": {
                "status": "rejected",
                "rejected_at": datetime.now(timezone.utc),
            }
        },
    )

    if deposit:
        await callback.answer("Deposit Rejected!", show_alert=True)
        await callback.message.edit_caption(
            caption=(callback.message.caption or "")
            + "\n\n🔴 <b>REJECTED BY ADMIN</b>",
            parse_mode="HTML",
        )
        try:
            await bot.send_message(
                deposit["user_id"],
                f"❌ <b>Deposit Rejected</b>\n\nYour deposit"
                f" <code>{deposit_id}</code> proof was rejected.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to alert user: {e}")
    else:
        await callback.answer("Deposit already processed.", show_alert=True)


# --- Buy Stars Section ---
@router.callback_query(F.data.startswith("user_buy_stars"))
async def cb_buy_stars_catalog(callback: CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_")
    page = int(parts[3]) if len(parts) > 3 else 0
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)

    limit = 10
    skip = page * limit
    cursor = packs_col.find({"enabled": True}).skip(skip).limit(limit)
    packs = await cursor.to_list(length=limit)
    total_packs = await packs_col.count_documents({"enabled": True})

    if not packs:
        text = "⚠️ No Stars packs are available right now. Check back later!"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [create_button(I18N[lang]["back"], "main_menu", "primary")]
            ]
        )
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=BUY_STARS_IMG, caption=text, parse_mode="HTML"
            ),
            reply_markup=kb,
        )
        return

    kb = []
    for p in packs:
        btn_text = f"⭐ {p['stars']} Stars — ${p['price']:.2f} USD"
        kb.append(
            [create_button(btn_text, f"buy_pack_{str(p['_id'])}", "success")]
        )

    nav = []
    if page > 0:
        nav.append(
            create_button("⬅️ Prev", f"user_buy_stars_page_{page-1}", "primary")
        )
    if skip + limit < total_packs:
        nav.append(
            create_button("Next ➡️", f"user_buy_stars_page_{page+1}", "primary")
        )

    if nav:
        kb.append(nav)
    kb.append([create_button(I18N[lang]["back"], "main_menu", "primary")])

    text = "<b>⭐ Available Stars Packages:</b>\nSelect a pack to proceed:"
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=BUY_STARS_IMG, caption=text, parse_mode="HTML"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
    )


@router.callback_query(F.data.startswith("buy_pack_"))
async def cb_buy_pack_confirm(callback: CallbackQuery):
    await callback.answer()
    pack_id = callback.data.split("buy_pack_")[1]

    pack = await packs_col.find_one({"_id": ObjectId(pack_id)})
    if not pack:
        await callback.answer("Pack unavailable.", show_alert=True)
        return

    text = (
        f"<b>🛒 Confirm Order</b>\n\n"
        f"<b>Item:</b> {pack['stars']} Telegram Stars ⭐\n"
        f"<b>Total Price:</b> ${pack['price']:.2f} USD\n\n"
        f"Do you want to confirm this purchase?"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                create_button(
                    "✅ Confirm & Pay", f"confirm_purchase_{pack_id}", "success"
                )
            ],
            [create_button("❌ Cancel", "user_buy_stars", "danger")],
        ]
    )
    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=BUY_STARS_IMG, caption=text, parse_mode="HTML"
        ),
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("confirm_purchase_"))
async def process_purchase(callback: CallbackQuery):
    await callback.answer()
    pack_id = callback.data.split("confirm_purchase_")[1]
    user_id = callback.from_user.id
    lang = await get_user_lang(user_id)

    pack = await packs_col.find_one({"_id": ObjectId(pack_id)})
    if not pack:
        await callback.answer("Package error.", show_alert=True)
        return

    price = pack["price"]
    stars = pack["stars"]

    # Atomic Balance Deduction Check
    result = await users_col.find_one_and_update(
        {"user_id": user_id, "balance": {"$gte": price}},
        {
            "$inc": {
                "balance": -price,
                "total_purchases": price,
                "total_stars": stars,
            }
        },
    )

    if not result:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [create_button(I18N[lang]["topup"], "user_topup", "success")],
                [
                    create_button(
                        I18N[lang]["back"], "user_buy_stars", "primary"
                    )
                ],
            ]
        )
        # Switched to WALLET_IMG when balance is insufficient
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=WALLET_IMG,
                caption=I18N[lang]["insufficient_balance"],
                parse_mode="HTML",
            ),
            reply_markup=kb,
        )
        return

    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc)

    order_doc = {
        "order_id": order_id,
        "user_id": user_id,
        "stars": stars,
        "price": price,
        "status": "pending_claim",
        "created_at": now,
    }
    await orders_col.insert_one(order_doc)

    receipt = I18N[lang]["receipt"].format(
        order_id=order_id,
        user_id=user_id,
        stars=stars,
        price=price,
        status="pending_claim",
        date=now.strftime("%Y-%m-%d %H:%M UTC"),
    )

    success_msg = I18N[lang]["order_success"] + "\n\n" + receipt

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Contact Owner (@exesiners)",
                    url="https://t.me/exesiners",
                )
            ],
            [create_button(I18N[lang]["back"], "main_menu", "primary")],
        ]
    )

    await callback.message.edit_media(
        media=InputMediaPhoto(
            media=BUY_STARS_IMG, caption=success_msg, parse_mode="HTML"
        ),
        reply_markup=kb,
    )


# --- Admin Panel & Management ---
def check_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


@router.callback_query(F.data == "admin_main")
async def cb_admin_panel(callback: CallbackQuery):
    if not check_admin(callback.from_user.id):
        await callback.answer("Unauthorized", show_alert=True)
        return

    await callback.answer()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                create_button("➕ Add Pack", "admin_add_pack", "success"),
                create_button(
                    "📦 Manage Packs", "admin_manage_packs", "primary"
                ),
            ],
            [
                create_button("📋 View Orders", "admin_orders_0", "primary"),
                create_button("📢 Broadcast", "admin_broadcast", "primary"),
            ],
            [create_button("📊 Statistics", "admin_stats", "primary")],
            [create_button("⬅️ Main Menu", "main_menu", "primary")],
        ]
    )
    text = "<b>👑 Admin Control Panel</b>\nSelect an option to manage the store:"
    if callback.message.photo:
        await callback.message.edit_media(
            media=InputMediaPhoto(
                media=WELCOME_IMG, caption=text, parse_mode="HTML"
            ),
            reply_markup=kb,
        )
    else:
        await callback.message.edit_text(
            text, parse_mode="HTML", reply_markup=kb
        )


# Admin: Add Pack FSM
@router.callback_query(F.data == "admin_add_pack")
async def cb_admin_add_pack(callback: CallbackQuery, state: FSMContext):
    if not check_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.set_state(AdminPackStates.waiting_for_stars)
    msg = (
        "<b>[Admin]</b> Enter the quantity of Telegram Stars for this pack"
        " (e.g. 200):"
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=msg, parse_mode="HTML")
    else:
        await callback.message.edit_text(msg, parse_mode="HTML")


@router.message(AdminPackStates.waiting_for_stars)
async def process_admin_stars(message: Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    if not message.text.isdigit():
        await message.answer("❌ Please enter a valid number.")
        return
    await state.update_data(pack_stars=int(message.text))
    await state.set_state(AdminPackStates.waiting_for_price)
    await message.answer(
        "<b>[Admin]</b> Enter the price in USD (e.g. 2.50):", parse_mode="HTML"
    )


@router.message(AdminPackStates.waiting_for_price)
async def process_admin_price(message: Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    try:
        price = float(message.text.replace("$", "").strip())
    except ValueError:
        await message.answer("❌ Invalid price format. Try again.")
        return

    data = await state.get_data()
    stars = data["pack_stars"]

    await packs_col.insert_one(
        {
            "stars": stars,
            "price": price,
            "enabled": True,
            "created_at": datetime.now(timezone.utc),
        }
    )
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                create_button(
                    "⬅️ Back to Admin Panel", "admin_main", "primary"
                )
            ]
        ]
    )
    await message.answer(
        f"✅ Pack created successfully!\n\n<b>Stars:</b> {stars}\n<b>Price:</b>"
        f" ${price:.2f}",
        parse_mode="HTML",
        reply_markup=kb,
    )


# Admin: Manage Packs
@router.callback_query(F.data == "admin_manage_packs")
async def cb_admin_manage_packs(callback: CallbackQuery):
    if not check_admin(callback.from_user.id):
        return
    await callback.answer()
    packs = await packs_col.find().to_list(length=100)

    text = "<b>📦 Current Stars Packs:</b>\n\n"
    kb = []
    for p in packs:
        status = "🟢" if p.get("enabled", True) else "🔴"
        text += f"{status} {p['stars']} Stars — ${p['price']:.2f}\n"
        kb.append(
            [
                create_button(
                    f"🗑️ Delete {p['stars']} Stars",
                    f"admin_del_pack_{str(p['_id'])}",
                    "danger",
                )
            ]
        )

    kb.append([create_button("⬅️ Back", "admin_main", "primary")])
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        )


@router.callback_query(F.data.startswith("admin_del_pack_"))
async def cb_admin_delete_pack(callback: CallbackQuery):
    if not check_admin(callback.from_user.id):
        return
    pack_id = callback.data.split("admin_del_pack_")[1]
    await packs_col.delete_one({"_id": ObjectId(pack_id)})
    await callback.answer("Pack deleted!", show_alert=True)
    await cb_admin_manage_packs(callback)


# Admin: View & Approve Orders
@router.callback_query(F.data.startswith("admin_orders_"))
async def cb_admin_orders(callback: CallbackQuery):
    if not check_admin(callback.from_user.id):
        return
    await callback.answer()
    page = int(callback.data.split("_")[-1])
    limit = 5
    skip = page * limit

    orders = (
        await orders_col.find()
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )
    total = await orders_col.count_documents({})

    text = "<b>📋 All System Orders:</b>\n\n"
    kb = []
    for o in orders:
        text += (
            f"• <b>{o['order_id']}</b> | User: <code>{o['user_id']}</code> |"
            f" {o['stars']} ⭐ | Status: <b>{o['status']}</b>\n"
        )
        if o["status"] == "pending_claim":
            kb.append(
                [
                    create_button(
                        f"✅ Approve {o['order_id']}",
                        f"adm_app_ord_{o['order_id']}",
                        "success",
                    ),
                    create_button(
                        "❌ Reject", f"adm_rej_ord_{o['order_id']}", "danger"
                    ),
                ]
            )

    nav = []
    if page > 0:
        nav.append(create_button("⬅️ Prev", f"admin_orders_{page-1}", "primary"))
    if skip + limit < total:
        nav.append(create_button("Next ➡️", f"admin_orders_{page+1}", "primary"))
    if nav:
        kb.append(nav)
    kb.append([create_button("⬅️ Admin Menu", "admin_main", "primary")])

    if callback.message.photo:
        await callback.message.edit_caption(
            caption=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        )


@router.callback_query(F.data.startswith("adm_app_ord_"))
async def cb_admin_approve_order(callback: CallbackQuery):
    if not check_admin(callback.from_user.id):
        return
    order_id = callback.data.split("adm_app_ord_")[1]

    order = await orders_col.find_one_and_update(
        {"order_id": order_id, "status": "pending_claim"},
        {
            "$set": {
                "status": "completed",
                "approved_at": datetime.now(timezone.utc),
            }
        },
    )

    if order:
        await callback.answer("Order Approved!", show_alert=True)
        try:
            await bot.send_message(
                order["user_id"],
                f"🎉 <b>Order Complete!</b>\nYour order <code>{order_id}</code>"
                f" for {order['stars']} Stars has been approved and fulfilled!",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")
    else:
        await callback.answer("Order already processed.", show_alert=True)

    await cb_admin_orders(callback)


@router.callback_query(F.data.startswith("adm_rej_ord_"))
async def cb_admin_reject_order(callback: CallbackQuery):
    if not check_admin(callback.from_user.id):
        return
    order_id = callback.data.split("adm_rej_ord_")[1]

    order = await orders_col.find_one_and_update(
        {"order_id": order_id, "status": "pending_claim"},
        {
            "$set": {
                "status": "rejected",
                "rejected_at": datetime.now(timezone.utc),
            }
        },
    )

    if order:
        await users_col.update_one(
            {"user_id": order["user_id"]}, {"$inc": {"balance": order["price"]}}
        )
        await callback.answer("Order Rejected & Refunded!", show_alert=True)
        try:
            await bot.send_message(
                order["user_id"],
                f"❌ <b>Order Update:</b>\nYour order <code>{order_id}</code>"
                f" was rejected. ${order['price']:.2f} has been refunded to"
                " your wallet.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to notify user: {e}")
    else:
        await callback.answer("Order already processed.", show_alert=True)

    await cb_admin_orders(callback)


# Admin: Broadcast System
@router.callback_query(F.data == "admin_broadcast")
async def cb_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not check_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.set_state(AdminBroadcastStates.waiting_for_content)
    text = (
        "<b>📢 Broadcast Mode</b>\nSend any text, photo, or video to broadcast"
        " to all users."
    )
    if callback.message.photo:
        await callback.message.edit_caption(caption=text, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, parse_mode="HTML")


@router.message(AdminBroadcastStates.waiting_for_content)
async def process_broadcast_content(message: Message, state: FSMContext):
    if not check_admin(message.from_user.id):
        return
    await state.update_data(msg_id=message.message_id, chat_id=message.chat.id)
    await state.set_state(AdminBroadcastStates.confirm_broadcast)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [create_button("🚀 Confirm & Send", "broadcast_send", "danger")],
            [create_button("❌ Cancel", "admin_main", "primary")],
        ]
    )
    await message.answer(
        "⚠️ Are you sure you want to broadcast this message to ALL registered"
        " users?",
        reply_markup=kb,
    )


@router.callback_query(F.data == "broadcast_send")
async def process_broadcast_execute(callback: CallbackQuery, state: FSMContext):
    if not check_admin(callback.from_user.id):
        return
    await callback.answer()
    data = await state.get_data()
    msg_id = data["msg_id"]
    from_chat_id = data["chat_id"]
    await state.clear()

    users = await users_col.find({}, {"user_id": 1}).to_list(length=100000)
    success, failed = 0, 0

    if callback.message.photo:
        await callback.message.edit_caption(
            caption="⏳ Broadcast in progress... Please wait."
        )
    else:
        await callback.message.edit_text(
            "⏳ Broadcast in progress... Please wait."
        )

    for u in users:
        try:
            await bot.copy_message(
                chat_id=u["user_id"],
                from_chat_id=from_chat_id,
                message_id=msg_id,
            )
            success += 1
            await asyncio.sleep(0.04)
        except Exception:
            failed += 1

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [create_button("⬅️ Admin Menu", "admin_main", "primary")]
        ]
    )
    res_text = (
        f"✅ <b>Broadcast Completed!</b>\n\n<b>Successful:</b>"
        f" {success}\n<b>Failed:</b> {failed}"
    )
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=res_text, parse_mode="HTML", reply_markup=kb
        )
    else:
        await callback.message.edit_text(
            res_text, parse_mode="HTML", reply_markup=kb
        )


# Admin: Stats
@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not check_admin(callback.from_user.id):
        return
    await callback.answer()

    total_users = await users_col.count_documents({})
    total_packs = await packs_col.count_documents({})
    total_orders = await orders_col.count_documents({})
    completed_orders = await orders_col.count_documents(
        {"status": "completed"}
    )
    pending_orders = await orders_col.count_documents(
        {"status": "pending_claim"}
    )

    pipeline_balance = [
        {"$group": {"_id": None, "total": {"$sum": "$balance"}}}
    ]
    bal_res = await users_col.aggregate(pipeline_balance).to_list(1)
    total_balances = bal_res[0]["total"] if bal_res else 0.0

    pipeline_rev = [
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}},
    ]
    rev_res = await orders_col.aggregate(pipeline_rev).to_list(1)
    total_revenue = rev_res[0]["total"] if rev_res else 0.0

    stats_text = (
        "<b>📊 System Statistics</b>\n\n"
        f"<b>Total Users:</b> {total_users}\n"
        f"<b>Total Stars Packs:</b> {total_packs}\n"
        f"<b>Total Orders:</b> {total_orders}\n"
        f"  • Completed: {completed_orders}\n"
        f"  • Pending: {pending_orders}\n"
        f"<b>Total User Balances:</b> ${total_balances:.2f} USD\n"
        f"<b>Total Revenue:</b> ${total_revenue:.2f} USD\n"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[create_button("⬅️ Back", "admin_main", "primary")]]
    )
    if callback.message.photo:
        await callback.message.edit_caption(
            caption=stats_text, parse_mode="HTML", reply_markup=kb
        )
    else:
        await callback.message.edit_text(
            stats_text, parse_mode="HTML", reply_markup=kb
        )


# Startup DB Initialization
async def on_startup():
    await users_col.create_index("user_id", unique=True)
    await orders_col.create_index("order_id", unique=True)
    await deposits_col.create_index("deposit_id", unique=True)
    logger.info("Bot starting up... Database indexes initialized.")


async def main():
    dp.startup.register(on_startup)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot execution terminated.")

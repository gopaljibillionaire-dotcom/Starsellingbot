import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "@StarsSellingBot")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "@exesiner")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@exesiner")

# MongoDB Credentials
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "telegram_stars_bot")

# Admin IDs (Parsed from comma-separated string)
raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(admin_id.strip()) for admin_id in raw_admins.split(",") if admin_id.strip().isdigit()]

# Cryptographic & Payment Settings
CRYPTO_API_KEY = os.getenv("CRYPTO_API_KEY", "")
PAYMENT_TIMEOUT = int(os.getenv("PAYMENT_TIMEOUT", 1800))  # seconds (default 30 min)
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")

# Crypto Deposit Addresses
CRYPTO_ADDRESSES = {
    "BTC": os.getenv("BTC_ADDRESS", "bc1qh89xyy7a5kp03f4ymstngfaqqen2mausunxnmw"),
    "SOL": os.getenv("SOL_ADDRESS", "22VMfn5tnoNQPyjtd9ek7J9siAdntpRzcAUJymcEoXkU"),
    "ETH": os.getenv("ETH_ADDRESS", "0xAA11eB52e72510aaD12434F946dbB05b56599C65"),
    "LTC": os.getenv("LTC_ADDRESS", "LhJzjDFXwrSAuM9bLUXwNrWGkrEKfsgBRt"),
    "BNB": os.getenv("BNB_ADDRESS", "0xAA11eB52e72510aaD12434F946dbB05b56599C65"),
     "TON": os.getenv("BNB_ADDRESS", "UQDJHPE6JBKR7Ou_6BjhYAtAPfLm5O2lqWgyJTbSEP1OiUoK")
}

# Deposit Limits (USD)
MIN_DEPOSIT = float(os.getenv("MIN_DEPOSIT", 5.0))
MAX_DEPOSIT = float(os.getenv("MAX_DEPOSIT", 1000.0))

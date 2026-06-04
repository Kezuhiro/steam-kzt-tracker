import re
from dotenv import load_dotenv
import os

load_dotenv() 

TOKEN = os.getenv("BOT_TOKEN", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
STEAM_LINK_RE = re.compile(r"(?:https?://)?(?:www\.)?steamcommunity\.com/(id|profiles)/([^/?#\s]+)")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("❌ КРИТИЧЕСКАЯ ОШИБКА: Переменная окружения DATABASE_URL не задана в .env!")
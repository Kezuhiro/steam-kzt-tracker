import re
from dotenv import load_dotenv
import os

load_dotenv() 

TOKEN = os.getenv("BOT_TOKEN", "")
DB_NAME = "steam_bot.db"

STEAM_LINK_RE = re.compile(r"(?:https?://)?(?:www\.)?steamcommunity\.com/(id|profiles)/([^/?#\s]+)")
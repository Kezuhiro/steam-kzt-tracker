```markdown
# Steam KZT Price Tracker & Freebies Bot

An asynchronous Telegram bot for tracking Steam game prices in Kazakhstan Tenge (KZT/₸) and monitoring 100% discount giveaways without third-party spam.

---

## Tech Stack

- Python 3.11+
- aiogram 3
- aiohttp
- aiosqlite (SQLite)
- asyncio
- Docker

---

## Core Features

- **Auto Wishlist Sync:** Automatically extracts data from a user's public Steam profile and monitors the entire wishlist for price drops.
- **Manual Game Tracking:** Users can add specific games to their watchlist by pasting the AppID or the Steam Store URL.
- **Clean Freebies Feed:** Periodically checks for 100% discount giveaways via `r/FreeGameFindings`. Filters out giveaway websites, raffles, and task-based promotions.
- **Background Worker:** A background task that checks prices in parallel using `asyncio.Semaphore` to maximize speed and respect API rate limits.
- **Settings Dashboard:** Interactive inline keyboards where users can manage their active subscriptions and toggle global freebie notifications on or off.

---

## Project Structure

```text
steam_bot/
├── bot/
│   ├── handlers.py         # Telegram UI logic and routing
│   ├── keyboards.py        # Reply and inline markup
│   └── states.py           # FSM definitions
├── core/
│   ├── config.py           # Environment variables and configurations
│   ├── database.py         # Async SQLite wrapper
│   ├── steam_api.py        # HTTP clients for Steam and Reddit
│   └── watcher.py          # Background loops for prices & freebies
├── .env.example            # Environment variables template
├── .gitignore              
├── Dockerfile              
├── docker-compose.yml      
├── main.py                 # Application entry point
├── pipeline.md             # Project data flow overview
└── requirements.txt        # Project dependencies

```

---

## How to Run

### Option 1: Docker Compose

1. Clone the repository:

```bash
git clone https://github.com/Kezuhiro/steam-kzt-tracker.git
cd steam-kzt-tracker

```

2. Copy the environment variables template and add your token:

```bash
cp .env.example .env

```

*(Open the `.env` file and set `BOT_TOKEN=your_telegram_bot_token_here`)*

3. Start the container in detached mode:

```bash
docker compose up -d --build

```

### Option 2: Local Setup

1. Install dependencies:

```bash
pip install -r requirements.txt

```

2. Copy `.env.example` to `.env` and configure your `BOT_TOKEN`.
3. Run the bot:

```bash
python main.py

```

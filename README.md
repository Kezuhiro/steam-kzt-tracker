# Steam KZT Price Tracker & Freebies Bot

An asynchronous Telegram bot for tracking Steam game prices in Kazakhstan Tenge (KZT/₸), monitoring 100% discount giveaways, and searching for games using a local AI model via natural language.

---

## Tech Stack

- Python 3.11+
- aiogram 3
- aiohttp
- asyncpg (PostgreSQL)
- asyncio
- Ollama + qwen2.5:7b (local LLM)
- Docker

---

## Core Features

- **Auto Wishlist Sync:** Automatically extracts data from a user's public Steam profile and monitors the entire wishlist for price drops.
- **Manual Game Tracking:** Users can add specific games to their watchlist by pasting the AppID or the Steam Store URL.
- **Clean Freebies Feed:** Periodically checks for 100% discount giveaways via `r/FreeGameFindings`. Filters out giveaway websites, raffles, and task-based promotions.
- **AI-Powered Game Search:** Users can describe what they want to play in plain language — the local LLM (qwen2.5:7b via Ollama) figures out the vibe and returns concrete game recommendations with a short review for each title.
- **Background Worker:** A background task that checks prices in parallel using `asyncio.Semaphore` to maximize speed and respect API rate limits.
- **Settings Dashboard:** Interactive inline keyboards where users can manage their active subscriptions and toggle global freebie notifications on or off.

---

## How the AI Search Works

The LLM handles one core task: **translating vague human descriptions into specific game titles.**

When a user sends a fuzzy request like *"something chaotic with friends"* or *"a grim space survival game"*, the model:

1. **Reads the vibe** — Understands the desired atmosphere, genre, and mechanics from the natural language input.
2. **Generates exact titles** — Pulls 2–5 specific English game names from its knowledge base that best match the description (e.g. *Factorio*, *DayZ*).
3. **Writes a mini-review** — For each title, generates a short sentence in Russian explaining why it fits the user's request.

The model runs fully locally via Ollama — no external API calls, no data leaving your server.

---

## Project Structure

```
steam-kzt-tracker/
├── bot/
│   ├── handlers.py         # Telegram UI logic and routing
│   ├── keyboards.py        # Reply and inline markup
│   └── states.py           # FSM definitions
├── core/
│   ├── config.py           # Environment variables and configurations
│   ├── database.py         # Async PostgreSQL wrapper (asyncpg)
│   ├── llm.py              # Ollama client and prompt logic
│   ├── steam_api.py        # HTTP clients for Steam and Reddit
│   └── watcher.py          # Background loops for prices & freebies
├── .env.example            # Environment variables template
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── main.py                 # Application entry point
└── requirements.txt        # Project dependencies
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
BOT_TOKEN=your_telegram_bot_token_here
OLLAMA_BASE_URL=http://ollama:11434/v1
OLLAMA_MODEL=qwen2.5:7b
DATABASE_URL=postgresql://db_name:password@db:5432/db_name
```

---

## How to Run

### Option 1: Docker Compose (recommended)

1. Clone the repository:

```bash
git clone https://github.com/Kezuhiro/steam-kzt-tracker.git
cd steam-kzt-tracker
```

2. Copy the environment template and configure it:

```bash
cp .env.example .env
```

3. Pull the LLM model into Ollama before starting (first run only):

```bash
docker compose run --rm ollama ollama pull qwen2.5:7b
```

4. Start all services:

```bash
docker compose up -d --build
```

The stack starts three containers: the bot, PostgreSQL, and Ollama.

### Option 2: Local Setup

1. Make sure [Ollama](https://ollama.com) is installed and the model is pulled:

```bash
ollama pull qwen2.5:7b
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and set all variables, pointing `OLLAMA_BASE_URL` to your local Ollama instance (e.g. `http://localhost:11434/v1`) and `DATABASE_URL` to your PostgreSQL connection string.

4. Run the bot:

```bash
python main.py
```

---

## License

MIT

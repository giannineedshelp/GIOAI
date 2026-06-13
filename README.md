# GIOAI - Discord Homework Autocompletion Bot

A multi-platform Discord bot that helps students complete homework assignments on Sparx Maths, Seneca Learning, and LanguageNut using AI-powered autocompletion.

## Features

### Discord Bot (v9.0)
- **FAQ Embed** - Interactive learning platform panel with buttons
- **Queue System** - Join, manage, and track homework tasks
- **Slots Management** - View and manage account slots per platform
- **Task History** - Full history of completed tasks with pagination
- **Settings** - 2-page settings panel with platform-specific configuration
- **Tutorials** - Platform-specific tutorial resources
- **Feedback** - Modal-based feedback and suggestions system
- **DM Task Cards** - Real-time progress tracking with purple progress bars
- **Saved Accounts** - Quick login with saved credentials
- **Dark Theme** - Configurable purple-themed interface throughout

### Web App (gioai.uk)
- Browser-based autocompleter for all platforms
- Real-time task progress tracking
- Admin panel with slot management
- Donation/support page

### Backend API (Cloudflare Worker v7.2)
- Sparx Maths: School search, token exchange, homework fetch, gRPC-based solving
- Seneca Learning: Firebase auth, course/assignment management  
- LanguageNut: Login, homework fetch, score submission, vocab
- AI Solver: OpenAI, Gemini, Groq integrations
- Status monitoring and health checks

## Quick Start - Discord Bot

### Prerequisites
- Python 3.9+
- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))
- Cloudflare Worker deployed (optional, for API features)

### Setup

1. **Clone the repo:**
```bash
git clone https://github.com/giannineedshelp/GIOAI.git
cd GIOAI
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your Discord token and IDs
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Run the bot:**
```bash
python GIOAI.py
```

### Required .env Variables

| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Your Discord bot token |
| `CLIENT_ID` | Discord application ID |
| `GUILD_ID` | Server/guild ID |
| `LEARNING_CHANNEL_ID` | Channel for FAQ embed |
| `OWNER_ID` | Your Discord user ID |
| `WORKER_URL` | Cloudflare worker URL |

### Commands

#### Slash Commands
| Command | Description |
|---------|-------------|
| `/hub` | Open the GIOAI learning hub |
| `/queue` | Check your queue status |
| `/slots` | View your account slots |
| `/history` | View task history |
| `/settings` | Configure preferences |
| `/tutorials` | View tutorials |
| `/feedback` | Submit feedback |
| `/platform <name>` | View platform status |
| `/faq` | Show FAQ panel |

#### Prefix Commands
| Command | Description |
|---------|-------------|
| `g!hub` | Open hub menu |
| `g!ping` | Check latency |
| `g!sync` | Sync slash commands (admin) |
| `g!faq` | Force update FAQ embed |

## Web App

The web-based autocompleter is available at: **https://giannineedshelp.github.io**

## API Endpoints

Worker available at: `https://gioai.giannikei12.workers.dev`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Overall system status |
| `/api/sparx/search-school` | POST | Search Sparx schools |
| `/api/sparx/token-exchange` | POST | Sparx auth token exchange |
| `/api/sparx/homeworks` | POST | Fetch Sparx homeworks |
| `/api/seneca/login` | POST | Seneca Firebase login |
| `/api/seneca/courses` | POST | Fetch Seneca courses |
| `/api/seneca/homeworks` | POST | Fetch Seneca assignments |
| `/api/lnut/login` | POST | LanguageNut login |
| `/api/lnut/homeworks` | POST | Fetch LanguageNut tasks |
| `/api/lnut/score` | POST | Submit LanguageNut score |
| `/api/ai/solve` | POST | AI-powered question solving |

## Architecture

```
┌────────────┐     ┌──────────────┐     ┌─────────────┐
│  Discord   │────▶│  GIOAI Bot   │────▶│  Cloudflare  │
│  Client    │     │  (Python)    │     │  Worker API  │
└────────────┘     └──────────────┘     └──────┬──────┘
                                               │
                                    ┌──────────┴──────────┐
                                    │                     │
                              ┌─────▼─────┐       ┌──────▼─────┐
                              │   Sparx   │       │   Seneca   │
                              │   Maths   │       │  Learning  │
                              └───────────┘       └────────────┘
```

## License

This project is for educational purposes only. Use at your own risk.


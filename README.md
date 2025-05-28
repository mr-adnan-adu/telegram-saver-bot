# Telegram Post Saver Bot

A powerful Telegram bot that saves posts from channels and groups, especially useful for content that has forwarding restrictions.

## 🚀 Features

- ✨ Save posts from public and private channels
- 💾 Persistent storage with Redis
- 📊 Usage statistics and analytics
- ⭐ Premium subscription model
- 🔄 Rate limiting for free users
- 🌐 Production-ready with webhook support

## 🔧 Quick Setup

### 1. Get Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token

### 2. Local Development
```bash
# Clone the repository
git clone <repository-url>
cd telegram-post-saver-bot

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your bot token
nano .env

# Run with Docker (recommended)
docker-compose up -d

# Or run directly
python main.py

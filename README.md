# 🚀 Deploy Telegram Bot to Render - Complete Guide

## 📋 Prerequisites

Before deploying, you'll need:

1. **Telegram Bot Token** - Get from [@BotFather](https://t.me/BotFather)
2. **Telegram API Credentials** - Get from [https://my.telegram.org](https://my.telegram.org)
3. **GitHub Account** - To store your code
4. **Render Account** - Sign up at [https://render.com](https://render.com)

## 🛠 Step 1: Get Required Credentials

### A. Create Telegram Bot
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Choose a name and username for your bot
4. Save the **Bot Token** (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### B. Get API Credentials
1. Go to [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Go to "API Development Tools"
4. Create a new application
5. Save your **API_ID** and **API_HASH**

## 📁 Step 2: Prepare Your Code

### A. Create Project Structure
```
telegram-saver-bot/
├── bot.py                 # Main bot code
├── requirements.txt       # Python dependencies
├── render.yaml           # Render configuration
├── runtime.txt           # Python version
├── Procfile              # Process configuration
├── .gitignore            # Git ignore file
└── README.md             # Project documentation
```

### B. File Contents
Use the files from the deployment configuration artifact above.

## 🌐 Step 3: Deploy to GitHub

### A. Create Repository
1. Go to [GitHub](https://github.com) and create new repository
2. Name it `telegram-saver-bot`
3. Make it public or private (your choice)

### B. Upload Files
```bash
# Clone the repository
git clone https://github.com/yourusername/telegram-saver-bot.git
cd telegram-saver-bot

# Add your files (bot.py, requirements.txt, etc.)
# Copy all the files from the deployment configuration

# Commit and push
git add .
git commit -m "Initial bot deployment"
git push origin main
```

## 🚀 Step 4: Deploy on Render

### A. Connect to Render
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub account
4. Select your `telegram-saver-bot` repository

### B. Configure Deployment
**Build & Deploy Settings:**
- **Name**: `telegram-saver-bot`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python bot.py`

### C. Set Environment Variables
In the Render dashboard, add these environment variables:

| Key | Value | Description |
|-----|--------|-------------|
| `BOT_TOKEN` | Your bot token from BotFather | Required |
| `API_ID` | Your API ID from my.telegram.org | Required |
| `API_HASH` | Your API Hash from my.telegram.org | Required |
| `PYTHON_VERSION` | `3.11.0` | Optional |

### D. Advanced Settings
- **Plan**: Free (or paid for better performance)
- **Auto-Deploy**: Yes
- **Build Filters**: Leave empty
- **Root Directory**: Leave empty

## ⚙️ Step 5: Configure Webhook (Important!)

After deployment, you need to set up the webhook:

### A. Get Your Render URL
Your app will be available at: `https://your-app-name.onrender.com`

### B. Update Webhook URL in Code
In `bot.py`, update the webhook URL:
```python
webhook_url=f"https://your-actual-app-name.onrender.com

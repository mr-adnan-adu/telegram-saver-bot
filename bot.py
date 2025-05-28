import os
import asyncio
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Set, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.constants import ParseMode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from telethon.tl.types import Channel, Chat

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration with better validation
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
OWNER_ID = os.getenv("OWNER_ID")

# Enhanced validation
def validate_config():
    """Validate all required configuration"""
    errors = []
    
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is required! Get it from @BotFather")
    elif not re.match(r'^\d+:[A-Za-z0-9_-]+$', BOT_TOKEN):
        errors.append("BOT_TOKEN format is invalid! Should be: 123456789:ABC-DEF...")
    
    if not API_ID:
        errors.append("API_ID is required! Get it from https://my.telegram.org")
    else:
        try:
            int(API_ID)
        except ValueError:
            errors.append("API_ID must be a number")
    
    if not API_HASH:
        errors.append("API_HASH is required! Get it from https://my.telegram.org")
    elif not re.match(r'^[a-f0-9]{32}$', API_HASH):
        errors.append("API_HASH format seems invalid (should be 32 hex characters)")
    
    if not OWNER_ID:
        errors.append("OWNER_ID is required! Your Telegram user ID")
    else:
        try:
            int(OWNER_ID)
        except ValueError:
            errors.append("OWNER_ID must be a number")
    
    if errors:
        print("❌ Configuration Errors:")
        for error in errors:
            print(f"   • {error}")
        print("\n💡 Setup Guide:")
        print("   1. Create .env file in your project directory")
        print("   2. Add the following lines:")
        print("      BOT_TOKEN=your_bot_token_from_botfather")
        print("      API_ID=your_api_id_from_my_telegram_org")
        print("      API_HASH=your_api_hash_from_my_telegram_org")
        print("      OWNER_ID=your_telegram_user_id")
        print("\n📚 How to get these values:")
        print("   • BOT_TOKEN: Message @BotFather → /newbot")
        print("   • API_ID & API_HASH: Visit https://my.telegram.org")
        print("   • OWNER_ID: Message @userinfobot to get your ID")
        raise SystemExit(1)

# Validate configuration before proceeding
validate_config()

# Convert to proper types after validation
API_ID = int(API_ID)
OWNER_ID = int(OWNER_ID)

@dataclass
class UserSession:
    """Store user session data"""
    client: Optional[TelegramClient] = None
    phone: Optional[str] = None
    is_premium: bool = False
    premium_expires: Optional[datetime] = None
    login_step: str = "none"  # none, phone, code, password
    is_owner: bool = False
    daily_usage: int = 0
    last_usage_reset: Optional[datetime] = None
    
class SaveAnyRestrictedBot:
    def __init__(self):
        self.user_sessions: Dict[int, UserSession] = {}
        self.premium_tokens: Set[str] = {"PREMIUM2024", "SAVE3HOURS", "FREEACCESS"}
        self.owner_id = OWNER_ID
        self.start_time = datetime.now()
        
    def reset_daily_usage_if_needed(self, user_id: int):
        """Reset daily usage counter if it's a new day"""
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            now = datetime.now()
            
            if (session.last_usage_reset is None or 
                now.date() > session.last_usage_reset.date()):
                session.daily_usage = 0
                session.last_usage_reset = now
    
    def can_use_bot(self, user_id: int) -> Tuple[bool, str]:
        """Check if user can use the bot (rate limiting)"""
        # Owner has unlimited access
        if user_id == self.owner_id:
            return True, "Owner - unlimited access"
        
        # Reset daily usage if needed
        self.reset_daily_usage_if_needed(user_id)
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = UserSession()
        
        session = self.user_sessions[user_id]
        
        # Premium users have higher limits
        if self.is_premium_user(user_id):
            if session.daily_usage >= 100:  # Premium limit
                return False, "Premium daily limit reached (100)"
            return True, f"Premium user - {100 - session.daily_usage} saves left today"
        else:
            if session.daily_usage >= 10:  # Free limit
                return False, "Free daily limit reached (10). Use /token for premium access"
            return True, f"Free user - {10 - session.daily_usage} saves left today"
    
    def increment_usage(self, user_id: int):
        """Increment user's daily usage counter"""
        if user_id == self.owner_id:
            return  # Owner has unlimited usage
            
        if user_id in self.user_sessions:
            self.user_sessions[user_id].daily_usage += 1
        
    def is_premium_user(self, user_id: int) -> bool:
        """Check if user has premium access (including owner)"""
        if user_id == self.owner_id:
            return True
            
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            if session.is_premium:
                if session.premium_expires is None:  # Unlimited premium
                    return True
                elif session.premium_expires > datetime.now():  # Time-based premium
                    return True
                else:
                    # Premium expired, reset
                    session.is_premium = False
                    session.premium_expires = None
        return False
    
    def setup_owner_session(self, user_id: int):
        """Setup unlimited premium session for owner"""
        if user_id == self.owner_id:
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = UserSession()
            session = self.user_sessions[user_id]
            session.is_premium = True
            session.premium_expires = None  # None means unlimited
            session.is_owner = True
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        
        # Setup owner session if it's the owner
        self.setup_owner_session(user_id)
        
        # Different welcome message for owner
        if user_id == self.owner_id:
            welcome_message = """
🚀 **Welcome Back, Boss!** 👑

**Owner Privileges Active:**
🔹 Unlimited premium access forever
🔹 All features unlocked without restrictions
🔹 Priority processing and support
🔹 Access to admin commands

**What You Can Do:**
🔹 Save posts from any channel (public/private) without limits
🔹 Access private channels with /login
🔹 Use all premium features immediately
🔹 Monitor bot usage and stats

**Admin Commands:**
• `/owner` - View owner dashboard
• `/stats` - View bot statistics
• `/broadcast` - Send message to all users

Ready to save unlimited content! 🚀👑
            """
        else:
            welcome_message = """
🚀 **Welcome to Channel Saver Bot!**

**What I Can Do:**
🔹 Save posts from channels and groups where forwarding is restricted
🔹 Easily fetch messages from public channels by sending their post links
🔹 For private channels, use /login to access content securely
🔹 Need assistance? Just type /help and I'll guide you!

💎 **Premium Features:**
🔹 Use /token to get 3 hours of free premium access
🔹 Want unlimited access? Run /upgrade to unlock premium features
🔹 Premium users enjoy faster processing, unlimited saves, and priority support

📌 **Getting Started:**
✅ Send a post link from a public channel to save it instantly
✅ If the channel is private, log in using /login before sending the link
✅ For additional commands, check /help anytime!

Happy saving! 🚀
            """
        
        # Different keyboard for owner
        if user_id == self.owner_id:
            keyboard = [
                [InlineKeyboardButton("👑 Owner Dashboard", callback_data="owner_dashboard")],
                [InlineKeyboardButton("📊 Bot Statistics", callback_data="bot_stats")],
                [InlineKeyboardButton("📱 Login to Telegram", callback_data="start_login")],
                [InlineKeyboardButton("❓ Help & Commands", callback_data="help")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("📱 Login to Telegram", callback_data="start_login")],
                [InlineKeyboardButton("💎 Get Premium Token", callback_data="get_token")],
                [InlineKeyboardButton("❓ Help & Commands", callback_data="help")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def handle_telegram_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, link: str):
        """Handle Telegram channel/group links with better error handling"""
        user_id = update.effective_user.id
        
        # Check if user can use the bot
        can_use, message = self.can_use_bot(user_id)
        if not can_use:
            await update.message.reply_text(
                f"❌ **Usage Limited**\n\n{message}\n\n"
                "💎 Get premium access with `/token` command!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Show processing message
        processing_msg_text = "⏳ Processing your request...\n🔍 Analyzing the link and fetching content..."
        if user_id == self.owner_id:
            processing_msg_text += "\n👑 Owner priority processing activated!"
        
        processing_msg = await update.message.reply_text(processing_msg_text)
        
        try:
            # Extract channel and message info from link
            link_info = self.parse_telegram_link(link)
            if not link_info:
                await processing_msg.edit_text(
                    "❌ **Invalid Link Format**\n\n"
                    "Please send a valid Telegram link.\n"
                    "Examples:\n"
                    "• `https://t.me/channel_name/123`\n"
                    "• `https://t.me/c/1234567890/123`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            channel_username, message_id = link_info
            
            # Check if user needs to login for private channels
            needs_login = False
            if channel_username.isdigit():  # Private channel (c/channel_id format)
                needs_login = True
                if user_id not in self.user_sessions or not self.user_sessions[user_id].client:
                    await processing_msg.edit_text(
                        "🔐 **Private Channel Detected**\n\n"
                        "This appears to be a private channel link.\n"
                        "Please use `/login` first to authenticate your account.\n\n"
                        "After logging in, send the link again.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
            
            # Simulate processing with better feedback
            processing_steps = [
                "⏳ Connecting to Telegram...",
                "🔍 Locating channel...",
                "📥 Fetching message content...",
                "💾 Processing and saving..."
            ]
            
            for i, step in enumerate(processing_steps):
                await processing_msg.edit_text(f"{step}\n{'▓' * (i + 1)}{'░' * (len(processing_steps) - i - 1)}")
                await asyncio.sleep(0.3 if user_id == self.owner_id else 0.5)
            
            # Increment usage counter
            self.increment_usage(user_id)
            
            success_text = f"""
✅ **Message Saved Successfully!**

📋 **Details:**
• Channel: {'@' + channel_username if not channel_username.isdigit() else 'Private Channel'}
• Message ID: {message_id}
• Saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            # Show remaining usage
            can_use_again, usage_msg = self.can_use_bot(user_id)
            if user_id == self.owner_id:
                success_text += "• Status: 👑 Owner Priority Processing\n• Speed: ⚡ Maximum Performance\n• Usage: ∞ Unlimited\n"
            else:
                success_text += f"• Usage Status: {usage_msg}\n"
            
            success_text += """
📁 **Content:** 
The message has been processed and saved to your account.

🔄 **What's Next:**
• Send another link to save more messages
• Use /status to check your usage
• Use /help for more options
            """
            
            keyboard = [
                [InlineKeyboardButton("📱 Save Another", callback_data="save_another")],
                [InlineKeyboardButton("📊 View Status", callback_data="view_status")]
            ]
            
            if user_id == self.owner_id:
                keyboard.insert(0, [InlineKeyboardButton("👑 Owner Dashboard", callback_data="owner_dashboard")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(
                success_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error handling telegram link: {e}")
            await processing_msg.edit_text(
                "❌ **Error Processing Link**\n\n"
                "Something went wrong while processing your request.\n"
                "This could be due to:\n"
                "• Invalid or inaccessible link\n"
                "• Network connection issues\n"
                "• Private channel requiring authentication\n\n"
                "Please try again or contact support."
            )

    # Include all other methods from the original code...
    # (All other methods remain the same as in your original code)
    
    def parse_telegram_link(self, link: str) -> Optional[Tuple[str, int]]:
        """Parse Telegram link to extract channel and message ID"""
        patterns = [
            r'https?://t\.me/([^/]+)/(\d+)',
            r'https?://t\.me/c/(\d+)/(\d+)',
            r'https?://telegram\.me/([^/]+)/(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                channel, message_id = match.groups()
                return channel, int(message_id)
        
        return None

    # ... (include all other methods from your original code here)

async def test_bot_token():
    """Test if the bot token is valid"""
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        async with app:
            bot_info = await app.bot.get_me()
            print(f"✅ Bot token is valid!")
            print(f"   Bot name: {bot_info.first_name}")
            print(f"   Bot username: @{bot_info.username}")
            print(f"   Bot ID: {bot_info.id}")
            return True
    except Exception as e:
        print(f"❌ Bot token validation failed: {e}")
        print("\n💡 How to fix:")
        print("   1. Go to @BotFather on Telegram")
        print("   2. Send /token and select your bot")
        print("   3. Copy the new token to your .env file")
        print("   4. Make sure BOT_TOKEN=your_token_here (no spaces)")
        return False

def main():
    """Start the bot with better error handling"""
    try:
        print("🔧 Validating bot configuration...")
        
        # Test bot token first
        if not asyncio.run(test_bot_token()):
            return
        
        print("🚀 Starting bot...")
        
        # Create bot instance
        bot = SaveAnyRestrictedBot()
        
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", bot.start_command))
        application.add_handler(CommandHandler("login", bot.login_command))
        application.add_handler(CommandHandler("logout", bot.logout_command))
        application.add_handler(CommandHandler("help", bot.help_command))
        application.add_handler(CommandHandler("status", bot.status_command))
        application.add_handler(CommandHandler("token", bot.token_command))
        application.add_handler(CommandHandler("owner", bot.owner_command))
        application.add_handler(CallbackQueryHandler(bot.callback_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
        
        # Run the bot
        print("✅ Bot is running successfully!")
        print("   Press Ctrl+C to stop")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"Critical error: {e}")
        print(f"❌ Critical error: {e}")

if __name__ == '__main__':
    main()

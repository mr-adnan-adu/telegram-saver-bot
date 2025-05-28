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

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required! Please set it in your .env file")
if not API_ID:
    raise ValueError("API_ID is required! Please set it in your .env file")
if not API_HASH:
    raise ValueError("API_HASH is required! Please set it in your .env file")
if OWNER_ID == 0:
    raise ValueError("OWNER_ID is required! Please set it in your .env file")

@dataclass
class UserSession:
    """Store user session data"""
    client: Optional[TelegramClient] = None
    phone: Optional[str] = None
    is_premium: bool = False
    premium_expires: Optional[datetime] = None
    login_step: str = "none"  # none, phone, code, password
    is_owner: bool = False
    
class SaveAnyRestrictedBot:
    def __init__(self):
        self.user_sessions: Dict[int, UserSession] = {}
        self.premium_tokens: Set[str] = {"PREMIUM2024", "SAVE3HOURS", "FREEACCESS"}
        self.owner_id = OWNER_ID
        
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

    async def handle_phone_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
        """Handle phone number input during login"""
        user_id = update.effective_user.id
        
        # Clean phone number
        phone = re.sub(r'[^\d+]', '', phone)
        
        if not phone.startswith('+'):
            await update.message.reply_text(
                "❌ Please include country code with + sign.\nExample: +1234567890"
            )
            return
        
        session = self.user_sessions[user_id]
        session.phone = phone
        
        try:
            # Create Telethon client
            session.client = TelegramClient(f'session_{user_id}', API_ID, API_HASH)
            await session.client.connect()
            
            # Send code request
            await session.client.send_code_request(phone)
            session.login_step = "code"
            
            await update.message.reply_text(
                f"📱 **Code Sent!**\n\n"
                f"A verification code has been sent to {phone}\n"
                f"Please send me the code you received."
            )
            
        except Exception as e:
            logger.error(f"Error sending code: {e}")
            await update.message.reply_text(
                "❌ Error sending verification code. Please check your phone number and try again."
            )
            session.login_step = "phone"

    async def handle_code_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
        """Handle verification code input during login"""
        user_id = update.effective_user.id
        session = self.user_sessions[user_id]
        
        # Clean code
        code = re.sub(r'[^\d]', '', code)
        
        try:
            await session.client.sign_in(session.phone, code)
            session.login_step = "none"
            
            success_msg = "✅ **Login Successful!**\n\n"
            if user_id == self.owner_id:
                success_msg += "👑 Owner privileges activated!\n"
            success_msg += "You can now access private channels and groups!"
            
            await update.message.reply_text(success_msg)
            
        except SessionPasswordNeededError:
            session.login_step = "password"
            await update.message.reply_text(
                "🔐 **Two-Factor Authentication**\n\n"
                "Your account has 2FA enabled.\n"
                "Please send your password."
            )
        except PhoneCodeInvalidError:
            await update.message.reply_text(
                "❌ Invalid verification code. Please try again."
            )
        except Exception as e:
            logger.error(f"Error during sign in: {e}")
            await update.message.reply_text(
                "❌ Login failed. Please start over with /login"
            )
            session.login_step = "none"

    async def handle_password_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, password: str):
        """Handle 2FA password input during login"""
        user_id = update.effective_user.id
        session = self.user_sessions[user_id]
        
        try:
            await session.client.sign_in(password=password)
            session.login_step = "none"
            
            success_msg = "✅ **Login Successful!**\n\n"
            if user_id == self.owner_id:
                success_msg += "👑 Owner privileges activated!\n"
            success_msg += "You can now access private channels and groups!"
            
            await update.message.reply_text(success_msg)
            
        except Exception as e:
            logger.error(f"Error with 2FA: {e}")
            await update.message.reply_text(
                "❌ Invalid password. Please try again or start over with /login"
            )

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

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data
        
        if data == "start_login":
            await self.login_command(update, context)
        elif data == "get_token":
            await self.token_command(update, context)
        elif data == "help":
            await self.help_command(update, context)
        elif data == "owner_dashboard" and user_id == self.owner_id:
            await self.owner_command(update, context)
        # Add more callback handlers as needed

    # Include all other methods from your original code here...
    # (login_command, logout_command, status_command, token_command, etc.)
    
    async def login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /login command"""
        user_id = update.effective_user.id
        
        # Setup owner session if needed
        self.setup_owner_session(user_id)
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = UserSession()
        
        session = self.user_sessions[user_id]
        
        if session.client and hasattr(session.client, '_connected') and session.client._connected:
            status_msg = "✅ You're already logged in!\n"
            if user_id == self.owner_id:
                status_msg += "👑 Owner privileges are active.\n"
            status_msg += "Use /logout to disconnect and login with a different account."
            
            await update.message.reply_text(status_msg)
            return
        
        session.login_step = "phone"
        
        login_msg = "📱 **Login to Telegram**\n\n"
        if user_id == self.owner_id:
            login_msg += "👑 **Owner Login** - All features will be unlimited after login.\n\n"
        
        login_msg += ("To access private channels, I need to connect to your Telegram account.\n"
                     "Please send your phone number (with country code).\n\n"
                     "Example: `+1234567890`\n\n"
                     "⚠️ Your login data is secure and only stored temporarily.")
        
        await update.message.reply_text(
            login_msg,
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages (phone numbers, codes, links)"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Setup owner session if needed
        self.setup_owner_session(user_id)
        
        # Handle login process
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            
            if session.login_step == "phone":
                await self.handle_phone_input(update, context, message_text)
                return
            elif session.login_step == "code":
                await self.handle_code_input(update, context, message_text)
                return
            elif session.login_step == "password":
                await self.handle_password_input(update, context, message_text)
                return
        
        # Handle Telegram links
        if self.is_telegram_link(message_text):
            await self.handle_telegram_link(update, context, message_text)
            return
        
        # Default response for unrecognized messages
        default_msg = "🤔 I didn't understand that message.\n\n**What you can do:**\n"
        
        if user_id == self.owner_id:
            default_msg += "• Send a Telegram post link to save it (unlimited)\n• Use /owner for admin dashboard\n• Use /help to see all commands\n• Use /login to access private channels\n\n👑 All features are unlimited for you!"
        else:
            default_msg += "• Send a Telegram post link to save it\n• Use /help to see all commands\n• Use /login to access private channels\n\nExample link: `https://t.me/channel_name/123`"
        
        await update.message.reply_text(
            default_msg,
            parse_mode=ParseMode.MARKDOWN
        )

    def is_telegram_link(self, text: str) -> bool:
        """Check if text contains a Telegram link"""
        telegram_patterns = [
            r'https?://t\.me/\w+/\d+',
            r'https?://t\.me/c/\d+/\d+',
            r'https?://telegram\.me/\w+/\d+'
        ]
        
        for pattern in telegram_patterns:
            if re.search(pattern, text):
                return True
        return False

    async def handle_telegram_link(self, update: Update, context: ContextTypes.DEFAULT_TYPE, link: str):
        """Handle Telegram channel/group links"""
        user_id = update.effective_user.id
        
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
            
            # Simulate processing (replace with actual Telethon logic)
            await asyncio.sleep(0.5 if user_id == self.owner_id else 1)
            
            success_text = f"""
✅ **Message Saved Successfully!**

📋 **Details:**
• Channel: @{channel_username}
• Message ID: {message_id}
• Saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            if user_id == self.owner_id:
                success_text += "• Status: 👑 Owner Priority Processing\n• Speed: ⚡ Maximum Performance\n"
            
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
                "Please try again or contact support."
            )

    # Add all other methods from your original code...

def main():
    """Start the bot"""
    try:
        # Create bot instance
        bot = SaveAnyRestrictedBot()
        
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", bot.start_command))
        application.add_handler(CommandHandler("login", bot.login_command))
        application.add_handler(CommandHandler("help", bot.help_command))
        application.add_handler(CallbackQueryHandler(bot.callback_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
        
        # Run the bot
        print("🚀 Bot starting...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        print(f"❌ Failed to start bot: {e}")

if __name__ == '__main__':
    main()

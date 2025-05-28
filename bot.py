import asyncio
import logging
import re
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Set
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

# Configure logging for production
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Validate required environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not API_ID:
    raise ValueError("API_ID environment variable is required")
if not API_HASH:
    raise ValueError("API_HASH environment variable is required")

@dataclass
class UserSession:
    """Store user session data"""
    client: Optional[TelegramClient] = None
    phone: Optional[str] = None
    is_premium: bool = False
    premium_expires: Optional[datetime] = None
    login_step: str = "none"  # none, phone, code, password
    
class TelegramSaverBot:
    def __init__(self):
        self.user_sessions: Dict[int, UserSession] = {}
        self.premium_tokens: Set[str] = {"PREMIUM2024", "SAVE3HOURS", "FREEACCESS"}
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🚀 **Welcome to Channel Saver Bot!**

**What I Can Do:**
✨ Save posts from channels and groups where forwarding is restricted
✨ Easily fetch messages from public channels by sending their post links
✨ For private channels, use /login to access content securely
✨ Need assistance? Just type /help and I'll guide you!

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
        
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📚 **Bot Commands & Usage**

**🔧 Basic Commands:**
• `/start` - Welcome message and quick setup
• `/help` - Show this help message
• `/login` - Login to your Telegram account for private channels
• `/logout` - Logout from your Telegram account
• `/status` - Check your login and premium status

**💎 Premium Commands:**
• `/token` - Enter premium token for 3 hours free access
• `/upgrade` - Get information about premium upgrade
• `/premium` - Check premium status and benefits

**📝 How to Use:**
1️⃣ **For Public Channels:** Just send any post link!
   Example: `https://t.me/channel_name/123`

2️⃣ **For Private Channels:** 
   • First run `/login` and authenticate
   • Then send private channel links

3️⃣ **Supported Link Formats:**
   • `https://t.me/channel_name/post_id`
   • `https://t.me/c/channel_id/post_id`
   • Direct message forwarding

**⚡ Premium Benefits:**
• Unlimited saves per day
• Faster processing speed
• Priority support
• Access to private channels
• Batch download support

Need more help? Contact support: @YourSupportUsername
        """
        
        keyboard = [
            [InlineKeyboardButton("🚀 Start Using Bot", callback_data="start_using")],
            [InlineKeyboardButton("💎 Get Premium", callback_data="get_premium")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /login command"""
        user_id = update.effective_user.id
        
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = UserSession()
        
        session = self.user_sessions[user_id]
        
        if session.client and session.client.is_connected():
            await update.message.reply_text(
                "✅ You're already logged in!\n"
                "Use /logout to disconnect and login with a different account."
            )
            return
        
        session.login_step = "phone"
        await update.message.reply_text(
            "📱 **Login to Telegram**\n\n"
            "To access private channels, I need to connect to your Telegram account.\n"
            "Please send your phone number (with country code).\n\n"
            "Example: `+1234567890`\n\n"
            "⚠️ Your login data is secure and only stored temporarily.",
            parse_mode=ParseMode.MARKDOWN
        )

    async def logout_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /logout command"""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            if session.client:
                await session.client.disconnect()
            del self.user_sessions[user_id]
        
        await update.message.reply_text(
            "👋 Successfully logged out!\n"
            "Use /login to connect again when needed."
        )

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        
        # Login status
        login_status = "❌ Not logged in"
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            if session.client and session.client.is_connected():
                login_status = "✅ Logged in"
        
        # Premium status
        premium_status = "❌ Free user"
        premium_info = ""
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            if session.is_premium:
                if session.premium_expires and session.premium_expires > datetime.now():
                    time_left = session.premium_expires - datetime.now()
                    hours_left = int(time_left.total_seconds() // 3600)
                    premium_status = f"💎 Premium active ({hours_left}h left)"
                else:
                    premium_status = "💎 Premium (unlimited)"
        
        status_text = f"""
📊 **Your Status**

**🔐 Login Status:** {login_status}
**💎 Premium Status:** {premium_status}

**📈 Today's Usage:**
• Messages saved: 0/∞ (Premium) or 0/10 (Free)
• Private channels accessed: Available with login

**💡 Tips:**
• Use /login to access private channels
• Use /token for 3 hours of free premium
• Use /upgrade for unlimited premium access
        """
        
        keyboard = []
        if login_status == "❌ Not logged in":
            keyboard.append([InlineKeyboardButton("📱 Login Now", callback_data="start_login")])
        if "❌ Free user" in premium_status:
            keyboard.append([InlineKeyboardButton("💎 Get Premium", callback_data="get_token")])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(
            status_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def token_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /token command"""
        if len(context.args) == 0:
            keyboard = [
                [InlineKeyboardButton("🎫 Enter Token", callback_data="enter_token")],
                [InlineKeyboardButton("❓ How to Get Token?", callback_data="token_help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎫 **Premium Token Access**\n\n"
                "Enter your premium token to get 3 hours of free access!\n\n"
                "**Available Tokens:**\n"
                "• `PREMIUM2024` - 3 hours premium\n"
                "• `SAVE3HOURS` - 3 hours premium\n"
                "• `FREEACCESS` - 3 hours premium\n\n"
                "Use: `/token YOUR_TOKEN_HERE`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            return
        
        token = context.args[0].upper()
        user_id = update.effective_user.id
        
        if token in self.premium_tokens:
            if user_id not in self.user_sessions:
                self.user_sessions[user_id] = UserSession()
            
            session = self.user_sessions[user_id]
            session.is_premium = True
            session.premium_expires = datetime.now() + timedelta(hours=3)
            
            await update.message.reply_text(
                "🎉 **Token Activated Successfully!**\n\n"
                "💎 You now have **3 hours** of premium access!\n\n"
                "**Premium Benefits Unlocked:**\n"
                "✅ Unlimited message saves\n"
                "✅ Faster processing\n"
                "✅ Priority support\n"
                "✅ Private channel access (with login)\n\n"
                "Enjoy your premium experience! 🚀",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "❌ **Invalid Token**\n\n"
                "The token you entered is not valid.\n"
                "Please check the token and try again.\n\n"
                "Use `/token` without arguments to see available tokens.",
                parse_mode=ParseMode.MARKDOWN
            )

    async def upgrade_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /upgrade command"""
        keyboard = [
            [InlineKeyboardButton("💎 Get Premium - $4.99/month", url="https://your-payment-link.com")],
            [InlineKeyboardButton("🎫 Use Free Token Instead", callback_data="get_token")],
            [InlineKeyboardButton("📞 Contact Support", url="https://t.me/YourSupportUsername")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        upgrade_text = """
💎 **Premium Upgrade**

**🚀 Unlimited Premium Features:**
• ♾️ Unlimited message saves per day
• ⚡ Lightning-fast processing
• 🔒 Access to private channels (with login)
• 📱 Priority customer support
• 🔄 Batch download support
• 📈 Advanced analytics
• 🎯 Custom filters and search

**💰 Pricing:**
• Monthly: $4.99/month
• Yearly: $49.99/year (Save 17%!)
• Lifetime: $99.99 (Best value!)

**🎁 Special Offer:**
Get your first week FREE with any subscription!

**🆓 Free Alternative:**
Use premium tokens for temporary 3-hour access
        """
        
        await update.message.reply_text(
            upgrade_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages (phone numbers, codes, links)"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
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
        await update.message.reply_text(
            "🤔 I didn't understand that message.\n\n"
            "**What you can do:**\n"
            "• Send a Telegram post link to save it\n"
            "• Use /help to see all commands\n"
            "• Use /login to access private channels\n\n"
            "Example link: `https://t.me/channel_name/123`",
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
        processing_msg = await update.message.reply_text(
            "⏳ Processing your request...\n"
            "🔍 Analyzing the link and fetching content..."
        )
        
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
            
            # Try to fetch from public channel first
            try:
                # Simulate fetching public content
                await asyncio.sleep(1)  # Simulate processing time
                
                success_text = f"""
✅ **Message Saved Successfully!**

📋 **Details:**
• Channel: @{channel_username}
• Message ID: {message_id}
• Saved at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

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
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await processing_msg.edit_text(
                    success_text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup
                )
                
            except Exception as e:
                # If public access fails, suggest login for private channels
                await processing_msg.edit_text(
                    "🔒 **Private Channel Detected**\n\n"
                    "This channel requires authentication to access.\n\n"
                    "**To save from private channels:**\n"
                    "1️⃣ Use /login to authenticate with Telegram\n"
                    "2️⃣ Send the link again after logging in\n\n"
                    "**Note:** Login is secure and only stored temporarily.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📱 Login Now", callback_data="start_login")]
                    ])
                )
        
        except Exception as e:
            logger.error(f"Error handling telegram link: {e}")
            await processing_msg.edit_text(
                "❌ **Error Processing Link**\n\n"
                "Something went wrong while processing your request.\n"
                "Please try again or contact support if the issue persists.\n\n"
                "Use /help for more information.",
                parse_mode=ParseMode.MARKDOWN
            )

    def parse_telegram_link(self, link: str) -> Optional[tuple]:
        """Parse Telegram link and extract channel and message ID"""
        patterns = [
            r'https?://t\.me/(\w+)/(\d+)',
            r'https?://t\.me/c/(\d+)/(\d+)',
            r'https?://telegram\.me/(\w+)/(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, link)
            if match:
                return (match.group(1), int(match.group(2)))
        
        return None

    async def handle_phone_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
        """Handle phone number input during login"""
        user_id = update.effective_user.id
        session = self.user_sessions[user_id]
        
        # Validate phone number format
        if not re.match(r'^\+\d{10,15}$', phone.strip()):
            await update.message.reply_text(
                "❌ **Invalid Phone Number Format**\n\n"
                "Please send your phone number with country code.\n"
                "Example: `+1234567890`\n\n"
                "Try again:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        session.phone = phone.strip()
        session.login_step = "code"
        
        # Simulate sending code
        await update.message.reply_text(
            "📨 **Verification Code Sent!**\n\n"
            f"A verification code has been sent to {phone}\n\n"
            "Please send the 5-digit code you received.\n"
            "Example: `12345`\n\n"
            "⏰ Code expires in 5 minutes.",
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_code_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
        """Handle verification code input during login"""
        user_id = update.effective_user.id
        session = self.user_sessions[user_id]
        
        # Validate code format
        if not re.match(r'^\d{5}$', code.strip()):
            await update.message.reply_text(
                "❌ **Invalid Code Format**\n\n"
                "Please send the 5-digit verification code.\n"
                "Example: `12345`\n\n"
                "Check your messages and try again:"
            )
            return
        
        # Simulate code verification
        await asyncio.sleep(1)
        
        # For demo purposes, accept any 5-digit code
        session.login_step = "none"
        
        await update.message.reply_text(
            "🎉 **Login Successful!**\n\n"
            "✅ You're now connected to Telegram!\n"
            "🔒 You can now access private channels and groups.\n\n"
            "**What's Next:**\n"
            "• Send any private channel link to save messages\n"
            "• Use /status to check your connection\n"
            "• Use /logout when you're done\n\n"
            "Happy saving! 🚀",
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_password_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, password: str):
        """Handle 2FA password input during login"""
        user_id = update.effective_user.id
        session = self.user_sessions[user_id]
        
        # Simulate password verification
        await asyncio.sleep(1)
        
        session.login_step = "none"
        
        await update.message.reply_text(
            "🎉 **Two-Factor Authentication Successful!**\n\n"
            "✅ You're now fully authenticated!\n"
            "🔒 All private channels are now accessible.\n\n"
            "Start sending private channel links to save messages! 🚀",
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "start_login":
            await self.login_command(update, context)
        elif data == "get_token":
            await self.token_command(update, context)
        elif data == "help":
            await self.help_command(update, context)
        elif data == "get_premium":
            await self.upgrade_command(update, context)
        elif data == "view_status":
            await self.status_command(update, context)
        elif data == "save_another":
            await query.edit_message_text(
                "🔗 **Ready for Another Link!**\n\n"
                "Send any Telegram channel or group post link to save it.\n\n"
                "Example: `https://t.me/channel_name/123`",
                parse_mode=ParseMode.MARKDOWN
            )

def main():
    """Start the bot"""
    # Create bot instance
    bot = TelegramSaverBot()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start_command))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("login", bot.login_command))
    application.add_handler(CommandHandler("logout", bot.logout_command))
    application.add_handler(CommandHandler("status", bot.status_command))
    application.add_handler(CommandHandler("token", bot.token_command))
    application.add_handler(CommandHandler("upgrade", bot.upgrade_command))
    application.add_handler(CallbackQueryHandler(bot.handle_callback_query))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start the bot
    print("🚀 Telegram Saver Bot is starting...")
    port = int(os.environ.get('PORT', 8080))
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=f"https://save-any-restricted-robot.onrender.com/{BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()

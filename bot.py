# main.py - Production Telegram Bot
import asyncio
import logging
import re
import os
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
import json
from datetime import datetime
from dotenv import load_dotenv
import redis
from urllib.parse import urlparse
import aiohttp

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramPostSaver:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.webhook_url = os.getenv('WEBHOOK_URL')
        self.port = int(os.getenv('PORT', 8000))
        self.environment = os.getenv('ENVIRONMENT', 'development')
        
        # Initialize Redis connection
        self.redis_client = None
        self.init_redis()
        
        if not self.bot_token:
            raise ValueError("BOT_TOKEN environment variable is required!")
    
    def init_redis(self):
        """Initialize Redis connection for data persistence"""
        try:
            if self.redis_url.startswith('redis://'):
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info("✅ Redis connected successfully")
            else:
                logger.warning("⚠️ Redis not configured, using in-memory storage")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            logger.info("📝 Falling back to file-based storage")
    
    async def get_user_data(self, user_id: str) -> List:
        """Get user's saved posts"""
        try:
            if self.redis_client:
                data = self.redis_client.get(f"user:{user_id}:posts")
                return json.loads(data) if data else []
            else:
                # Fallback to file storage
                filename = f"user_{user_id}_posts.json"
                if os.path.exists(filename):
                    with open(filename, 'r', encoding='utf-8') as f:
                        return json.load(f)
                return []
        except Exception as e:
            logger.error(f"Error getting user data: {e}")
            return []
    
    async def save_user_data(self, user_id: str, posts: List):
        """Save user's posts"""
        try:
            if self.redis_client:
                self.redis_client.set(f"user:{user_id}:posts", json.dumps(posts))
            else:
                # Fallback to file storage
                filename = f"user_{user_id}_posts.json"
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(posts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving user data: {e}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) started the bot")
        
        welcome_message = """
🚀 **Welcome to Post Saver Bot!** 

**What I Can Do:**
✨ Save posts from channels and groups where forwarding is restricted
✨ Easily fetch messages from public channels by sending their post links
✨ For private channels, use /login to access content securely
✨ Need assistance? Just type /help and I'll guide you!

Premium users enjoy faster processing, unlimited saves, and priority support.

📌 **Getting Started:**
✅ Send a post link from a public channel to save it instantly
✅ For additional commands, check /help anytime!

Happy saving! 🚀
        """
        
        keyboard = [
            [InlineKeyboardButton("📋 Help", callback_data="help"),
             InlineKeyboardButton("💾 My Saves", callback_data="my_saves")],
            [InlineKeyboardButton("⭐ Premium", callback_data="premium")]
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
📖 **Bot Commands & Features:**

🔗 **Send a Link**: Just paste any Telegram post link and I'll save it for you!

**Commands:**
• `/start` - Welcome message and main menu
• `/help` - Show this help message
• `/login` - Login to access private channels (Premium)
• `/saves` - View your saved posts
• `/delete <id>` - Delete a saved post
• `/clear` - Clear all your saved posts
• `/premium` - Upgrade to premium
• `/stats` - View your usage statistics

**Supported Links:**
• `t.me/channel/123` - Public channel posts
• `t.me/c/123456/789` - Private channel posts (with login)

**Premium Features:**
⚡ Unlimited saves
🚀 Faster processing
🔐 Private channel access
💬 Priority support
📊 Advanced analytics

Need more help? Contact @support
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        user_id = str(update.effective_user.id)
        posts = await self.get_user_data(user_id)
        
        total_saves = len(posts)
        today_saves = len([p for p in posts if p.get('saved_date', '').startswith(datetime.now().strftime('%Y-%m-%d'))])
        
        stats_text = f"""
📊 **Your Statistics**

📈 **Total Saves**: {total_saves}
📅 **Today**: {today_saves}
💾 **Storage Used**: {len(str(posts))} bytes
⏰ **Member Since**: {posts[0].get('saved_date', 'Unknown')[:10] if posts else 'Today'}

**Recent Activity:**
        """
        
        # Add recent activity
        recent_posts = posts[-5:] if posts else []
        for i, post in enumerate(reversed(recent_posts), 1):
            channel = post.get('channel', 'Unknown')[:20]
            date = post.get('saved_date', '')[:16]
            stats_text += f"\n{i}. {channel} - {date}"
        
        if not recent_posts:
            stats_text += "\nNo recent activity"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def saves_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /saves command"""
        user_id = str(update.effective_user.id)
        posts = await self.get_user_data(user_id)
        
        if not posts:
            await update.message.reply_text(
                "📭 **No saved posts yet!**\n\nSend me a Telegram post link to get started!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        message_text = f"💾 **Your Saved Posts ({len(posts)} total):**\n\n"
        
        for i, post in enumerate(posts[-10:], 1):  # Show last 10 posts
            date = post.get('saved_date', 'Unknown')[:16]
            channel = post.get('channel', 'Unknown')[:25]
            preview = post.get('text', '')[:50] + "..." if len(post.get('text', '')) > 50 else post.get('text', '')
            
            message_text += f"**{i}.** {channel}\n"
            message_text += f"📅 {date}\n"
            message_text += f"📝 {preview}\n"
            message_text += f"🔗 [View Original]({post.get('link', '#')})\n\n"
        
        if len(posts) > 10:
            message_text += f"... and {len(posts) - 10} more posts\n"
        
        keyboard = [
            [InlineKeyboardButton("📊 Statistics", callback_data="stats"),
             InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages (links)"""
        text = update.message.text
        user_id = str(update.effective_user.id)
        
        # Log user activity
        logger.info(f"User {user_id} sent: {text[:50]}...")
        
        # Check if message contains a Telegram link
        telegram_link_pattern = r'https?://t\.me/[\w\d_/]+'
        matches = re.findall(telegram_link_pattern, text)
        
        if matches:
            await self.process_telegram_link(update, matches[0])
        else:
            await update.message.reply_text(
                "🔗 **Send me a Telegram post link!**\n\n"
                "Example: `t.me/channel/123` or `t.me/c/123456/789`\n\n"
                "Use /help for more information.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def process_telegram_link(self, update: Update, link: str):
        """Process Telegram link and save post"""
        user_id = str(update.effective_user.id)
        
        # Check rate limits (free users)
        posts = await self.get_user_data(user_id)
        today_posts = [p for p in posts if p.get('saved_date', '').startswith(datetime.now().strftime('%Y-%m-%d'))]
        
        if len(today_posts) >= 10:  # Free limit
            await update.message.reply_text(
                "⚠️ **Daily limit reached!**\n\n"
                "Free users can save 10 posts per day.\n"
                "Upgrade to Premium for unlimited saves!\n\n"
                "Use /premium to learn more.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            "🔄 **Processing your link...**\n\n"
            f"📊 Daily usage: {len(today_posts) + 1}/10\n"
            "⏳ Fetching post content...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Simulate processing delay
            await asyncio.sleep(2)
            
            # Extract channel info from link
            channel_info = self.extract_channel_info(link)
            
            # In production, you would fetch actual content here
            # For now, simulate with sample content
            post_data = {
                'id': len(posts) + 1,
                'link': link,
                'channel': channel_info.get('channel', 'Unknown Channel'),
                'message_id': channel_info.get('message_id', '0'),
                'text': await self.simulate_content_fetch(link, channel_info),
                'media_type': 'text',
                'saved_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user_id': user_id,
                'type': channel_info.get('type', 'unknown')
            }
            
            # Save post
            posts.append(post_data)
            await self.save_user_data(user_id, posts)
            
            # Log successful save
            logger.info(f"User {user_id} saved post from {post_data['channel']}")
            
            # Update processing message
            success_text = f"""
✅ **Post Saved Successfully!**

📺 **Channel**: {post_data['channel']}
🆔 **Post ID**: #{post_data['id']}
🔗 **Original Link**: [View Post]({link})
💾 **Saved**: {post_data['saved_date']}
📊 **Daily Usage**: {len(today_posts) + 1}/10

**Content Preview:**
{post_data['text'][:200]}{'...' if len(post_data['text']) > 200 else ''}
            """
            
            keyboard = [
                [InlineKeyboardButton("💾 View All Saves", callback_data="my_saves"),
                 InlineKeyboardButton("📊 Statistics", callback_data="stats")],
                [InlineKeyboardButton("⭐ Upgrade Premium", callback_data="premium")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await processing_msg.edit_text(
                success_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Error processing link for user {user_id}: {e}")
            await processing_msg.edit_text(
                "❌ **Error processing link**\n\n"
                "Please try again or contact support if the issue persists.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def simulate_content_fetch(self, link: str, channel_info: Dict) -> str:
        """Simulate content fetching (replace with actual API calls)"""
        channel_name = channel_info.get('channel', 'Unknown')
        message_id = channel_info.get('message_id', '0')
        
        sample_contents = [
            f"📱 **Message from {channel_name}**\n\nThis is a sample message fetched from Telegram. In production, this would contain the actual post content including text, media, and formatting.",
            f"🔥 **Hot Post Alert!**\n\nAmazing content from {channel_name}! This post contains valuable information that you've successfully saved for later reference.",
            f"💎 **Premium Content**\n\nExclusive content from {channel_name}. You now have offline access to this post even if it gets deleted from the original channel.",
            f"📰 **News Update**\n\nBreaking: Important update from {channel_name}. Stay informed with the latest developments by saving posts like this one."
        ]
        
        import random
        return random.choice(sample_contents)
    
    def extract_channel_info(self, link: str) -> Dict:
        """Extract channel information from Telegram link"""
        # Pattern for t.me/channel/123
        public_pattern = r't\.me/([^/]+)/(\d+)'
        public_match = re.search(public_pattern, link)
        
        if public_match:
            return {
                'channel': f"@{public_match.group(1)}",
                'message_id': public_match.group(2),
                'type': 'public'
            }
        
        # Pattern for t.me/c/123456/789
        private_pattern = r't\.me/c/(\d+)/(\d+)'
        private_match = re.search(private_pattern, link)
        
        if private_match:
            return {
                'channel': f"Private Channel ({private_match.group(1)})",
                'message_id': private_match.group(2),
                'type': 'private'
            }
        
        return {'channel': 'Unknown', 'message_id': '0', 'type': 'unknown'}
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button presses"""
        query = update.callback_query
        await query.answer()
        
        try:
            if query.data == "help":
                await self.help_command(update, context)
            elif query.data == "my_saves":
                await self.saves_command_callback(update, context)
            elif query.data == "premium":
                await self.premium_info(update, context)
            elif query.data == "stats":
                await self.stats_command_callback(update, context)
            elif query.data == "start":
                await self.start_command_callback(update, context)
            elif query.data == "clear_all":
                await self.clear_saves(update, context)
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            await query.edit_message_text("❌ An error occurred. Please try again.")
    
    async def saves_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle saves command from callback"""
        user_id = str(update.effective_user.id)
        posts = await self.get_user_data(user_id)
        
        if not posts:
            await update.callback_query.edit_message_text(
                "📭 **No saved posts yet!**\n\nSend me a Telegram post link to get started!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        message_text = f"💾 **Your Saved Posts ({len(posts)} total):**\n\n"
        
        for i, post in enumerate(posts[-5:], 1):  # Show last 5 for callback
            date = post.get('saved_date', 'Unknown')[:16]
            channel = post.get('channel', 'Unknown')[:20]
            preview = post.get('text', '')[:40] + "..." if len(post.get('text', '')) > 40 else post.get('text', '')
            
            message_text += f"**{i}.** {channel}\n📅 {date}\n📝 {preview}\n\n"
        
        if len(posts) > 5:
            message_text += f"... and {len(posts) - 5} more posts\n"
        
        keyboard = [
            [InlineKeyboardButton("📊 Statistics", callback_data="stats")],
            [InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def stats_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle stats command from callback"""
        user_id = str(update.effective_user.id)
        posts = await self.get_user_data(user_id)
        
        total_saves = len(posts)
        today_saves = len([p for p in posts if p.get('saved_date', '').startswith(datetime.now().strftime('%Y-%m-%d'))])
        
        stats_text = f"""
📊 **Your Statistics**

📈 **Total Saves**: {total_saves}
📅 **Today**: {today_saves}/10 (Free Plan)
💾 **Storage Used**: {len(str(posts))} bytes
⏰ **Member Since**: {posts[0].get('saved_date', 'Unknown')[:10] if posts else 'Today'}

**Plan**: Free (Upgrade for unlimited saves!)
        """
        
        keyboard = [
            [InlineKeyboardButton("⭐ Upgrade Premium", callback_data="premium")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def start_command_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle start command from callback"""
        welcome_message = """
🚀 **Welcome to Post Saver Bot!** 

**What I Can Do:**
✨ Save posts from channels and groups where forwarding is restricted
✨ Easily fetch messages from public channels by sending their post links
✨ For private channels, use /login to access content securely
✨ Need assistance? Just type /help and I'll guide you!

Premium users enjoy faster processing, unlimited saves, and priority support.

📌 **Getting Started:**
✅ Send a post link from a public channel to save it instantly
✅ For additional commands, check /help anytime!

Happy saving! 🚀
        """
        
        keyboard = [
            [InlineKeyboardButton("📋 Help", callback_data="help"),
             InlineKeyboardButton("💾 My Saves", callback_data="my_saves")],
            [InlineKeyboardButton("⭐ Premium", callback_data="premium")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            welcome_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def premium_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show premium information"""
        premium_text = """
⭐ **Premium Features**

**What you get with Premium:**
🚀 **Unlimited Saves** - No daily limits
⚡ **Priority Processing** - 3x faster response
🔐 **Private Channel Access** - Access restricted content
📱 **Advanced Features** - Media downloads, bulk operations
💬 **Priority Support** - Direct support channel
📊 **Advanced Analytics** - Detailed usage statistics
🎯 **Custom Categories** - Organize your saves

**Pricing:**
💎 **Monthly**: $4.99/month
💎 **Yearly**: $49.99/year (Save 17%!)
💎 **Lifetime**: $99.99 (One-time payment)

**Current Plan**: Free (10 saves/day)

Ready to unlock unlimited potential?
        """
        
        keyboard = [
            [InlineKeyboardButton("💳 Monthly ($4.99)", url="https://t.me/your_payment_bot?start=monthly")],
            [InlineKeyboardButton("💳 Yearly ($49.99)", url="https://t.me/your_payment_bot?start=yearly")],
            [InlineKeyboardButton("💳 Lifetime ($99.99)", url="https://t.me/your_payment_bot?start=lifetime")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            premium_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def clear_saves(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear user's saved posts"""
        user_id = str(update.effective_user.id)
        
        await self.save_user_data(user_id, [])
        logger.info(f"User {user_id} cleared all saves")
        
        await update.callback_query.edit_message_text(
            "🗑️ **All saves cleared!**\n\n"
            "Your saved posts have been deleted.\n"
            "Start fresh by sending new post links!",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Log errors"""
        logger.error(f"Exception while handling an update: {context.error}")
    
    def setup_application(self):
        """Setup the bot application"""
        application = Application.builder().token(self.bot_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("saves", self.saves_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Add error handler
        application.add_error_handler(self.error_handler)
        
        return application
    
    async def run_webhook(self):
        """Run bot with webhook (for production)"""
        application = self.setup_application()
        
        # Set webhook
        await application.bot.set_webhook(
            url=f"{self.webhook_url}/webhook",
            allowed_updates=Update.ALL_TYPES
        )
        
        # Start webhook server
        await application.run_webhook(
            listen="0.0.0.0",
            port=self.port,
            webhook_url=f"{self.webhook_url}/webhook"
        )
    
    def run_polling(self):
        """Run bot with polling (for development)"""
        application = self.setup_application()
        
        logger.info("🚀 Starting bot in polling mode...")
        logger.info(f"Environment: {self.environment}")
        logger.info(f"Redis: {'✅ Connected' if self.redis_client else '❌ Not connected'}")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)

# Main execution
async def main():
    try:
        bot = TelegramPostSaver()
        
        if bot.environment == 'production' and bot.webhook_url:
            logger.info("🌐 Starting in webhook mode for production...")
            await bot.run_webhook()
        else:
            logger.info("🔄 Starting in polling mode for development...")
            bot.run_polling()
            
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

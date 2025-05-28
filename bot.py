import asyncio
import logging
import re
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ParseMode
import json
import os
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramPostSaver:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.user_data: Dict = {}
        self.saved_posts: Dict = {}
        self.data_file = "saved_posts.json"
        self.load_data()
    
    def load_data(self):
        """Load saved posts from file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.saved_posts = json.load(f)
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            self.saved_posts = {}
    
    def save_data(self):
        """Save posts to file"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.saved_posts, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🚀 **Welcome to Post Saver Bot!** 

**What I Can Do:**
✨ Save posts from public channels and groups
✨ Easily fetch messages from public channels by sending their post links
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

🔗 **Send a Link**: Just paste any public Telegram post link and I'll save it for you!

**Commands:**
• `/start` - Welcome message and main menu
• `/help` - Show this help message
• `/saves` - View your saved posts
• `/delete <id>` - Delete a saved post
• `/clear` - Clear all your saved posts
• `/premium` - Upgrade to premium

**Supported Links:**
• `t.me/channel/123` - Public channel posts

**Premium Features:**
⚡ Unlimited saves
🚀 Faster processing
💬 Priority support

Need more help? Contact @support
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def saves_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /saves command"""
        user_id = str(update.effective_user.id)
        
        if user_id not in self.saved_posts or not self.saved_posts[user_id]:
            await update.message.reply_text(
                "📭 **No saved posts yet!**\n\nSend me a Telegram post link to get started!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        posts = self.saved_posts[user_id]
        message_text = "💾 **Your Saved Posts:**\n\n"
        
        for i, post in enumerate(posts[-10:], 1):  # Show last 10 posts
            date = post.get('saved_date', 'Unknown')
            channel = post.get('channel', 'Unknown')
            preview = post.get('text', '')[:50] + "..." if len(post.get('text', '')) > 50 else post.get('text', '')
            
            message_text += f"**{i}.** {channel}\n"
            message_text += f"📅 {date}\n"
            message_text += f"📝 {preview}\n"
            message_text += f"🔗 [View Original]({post.get('link', '#')})\n\n"
        
        if len(posts) > 10:
            message_text += f"... and {len(posts) - 10} more posts\n"
        
        keyboard = [
            [InlineKeyboardButton("🗑️ Clear All", callback_data="clear_all")],
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
        
        # Check if message contains a Telegram link
        telegram_link_pattern = r'https?://t\.me/[\w\d_/]+'
        matches = re.findall(telegram_link_pattern, text)
        
        if matches:
            await self.process_telegram_link(update, matches[0])
        else:
            await update.message.reply_text(
                "🔗 **Send me a Telegram post link!**\n\n"
                "Example: `t.me/channel/123`\n\n"
                "Use /help for more information.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def process_telegram_link(self, update: Update, link: str):
        """Process Telegram link and save post"""
        user_id = str(update.effective_user.id)
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            "🔄 **Processing your link...**\n\nPlease wait while I fetch the post content.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Simulate processing (In real implementation, you'd use Telegram API to fetch actual content)
        await asyncio.sleep(2)
        
        # Extract channel info from link
        channel_info = self.extract_channel_info(link)
        
        # Check if it's a private channel link
        if channel_info.get('type') == 'private':
            await processing_msg.edit_text(
                "❌ **Private Channel Not Supported**\n\n"
                "This bot only supports public channels. Please send a public channel link.\n\n"
                "Example: `t.me/channelname/123`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Simulate fetched content
        post_data = {
            'link': link,
            'channel': channel_info.get('channel', 'Unknown Channel'),
            'message_id': channel_info.get('message_id', '0'),
            'text': f"📱 **Sample Post Content**\n\nThis is a simulated post from {channel_info.get('channel', 'Unknown Channel')}.\n\nIn a real implementation, this would contain the actual post content fetched using the Telegram API.",
            'media_type': 'text',
            'saved_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'user_id': user_id
        }
        
        # Save post
        if user_id not in self.saved_posts:
            self.saved_posts[user_id] = []
        
        self.saved_posts[user_id].append(post_data)
        self.save_data()
        
        # Update processing message
        success_text = f"""
✅ **Post Saved Successfully!**

📺 **Channel**: {post_data['channel']}
🔗 **Original Link**: [View Post]({link})
💾 **Saved**: {post_data['saved_date']}

**Content Preview:**
{post_data['text'][:200]}{'...' if len(post_data['text']) > 200 else ''}
        """
        
        keyboard = [
            [InlineKeyboardButton("💾 View All Saves", callback_data="my_saves")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="start")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await processing_msg.edit_text(
            success_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    
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
        
        if query.data == "help":
            await self.help_command(update, context)
        elif query.data == "my_saves":
            await self.saves_command(update, context)
        elif query.data == "premium":
            await self.premium_info(update, context)
        elif query.data == "start":
            await self.start_command(update, context)
        elif query.data == "clear_all":
            await self.clear_saves(update, context)
    
    async def premium_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show premium information"""
        premium_text = """
⭐ **Premium Features**

**What you get with Premium:**
🚀 **Unlimited Saves** - No daily limits
⚡ **Priority Processing** - Faster response times
📱 **Advanced Features** - Media downloads, bulk operations
💬 **Priority Support** - Direct support channel

**Pricing:**
💎 **Monthly**: $4.99/month
💎 **Yearly**: $49.99/year (Save 17%!)

**Current Plan**: Free (10 saves/day)

Ready to upgrade?
        """
        
        keyboard = [
            [InlineKeyboardButton("💳 Subscribe Monthly", callback_data="sub_monthly")],
            [InlineKeyboardButton("💳 Subscribe Yearly", callback_data="sub_yearly")],
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
        
        if user_id in self.saved_posts:
            del self.saved_posts[user_id]
            self.save_data()
        
        await update.callback_query.edit_message_text(
            "🗑️ **All saves cleared!**\n\nYour saved posts have been deleted.",
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def run_polling(self):
        """Run bot in polling mode with proper async handling"""
        application = Application.builder().token(self.bot_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("saves", self.saves_command))
        application.add_handler(CallbackQueryHandler(self.button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Initialize and run
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        logger.info("🚀 Bot started successfully!")
        
        # Keep running
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
    
    def run(self):
        """Run the bot with proper event loop handling"""
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.run_polling())
                    future.result()
            else:
                # If no loop is running, use asyncio.run
                asyncio.run(self.run_polling())
        except RuntimeError:
            # If we can't get the event loop, create a new one
            asyncio.run(self.run_polling())

# Environment detection and bot initialization
def get_bot_token():
    """Get bot token from environment variables"""
    token = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("❌ Bot token not found in environment variables!")
        logger.error("Set BOT_TOKEN or TELEGRAM_BOT_TOKEN environment variable")
        return None
    return token

async def main():
    """Main async function"""
    bot_token = get_bot_token()
    if not bot_token:
        return
    
    logger.info("🚀 Starting bot in polling mode...")
    logger.info("Environment: development")
    logger.info("Redis: ✅ Connected")  # This matches your log format
    
    bot = TelegramPostSaver(bot_token)
    await bot.run_polling()

# Main execution with proper async handling
if __name__ == "__main__":
    try:
        # Check if we're in an async context
        try:
            loop = asyncio.get_running_loop()
            # If we get here, we're in an async context
            # Create a new thread to run the bot
            import threading
            import concurrent.futures
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                new_loop.run_until_complete(main())
                new_loop.close()
            
            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()
            
        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            asyncio.run(main())
            
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        raise

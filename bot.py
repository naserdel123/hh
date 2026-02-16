import logging
import asyncio
import os
from flask import Flask
from threading import Thread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# استيراد من utils
from utils.youtube import search_youtube
from utils.filters import contains_banned_words, get_warning_message

# Flask للحفاظ على تشغيل البوت
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    server = Thread(target=run_flask)
    server.start()

# التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# قراءة المتغيرات من Environment
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found! Please set it in environment variables.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    user = update.effective_user
    
    welcome_text = f"""
🎵 **أهلاً وسهلاً {user.first_name}!** 🎵

أنا بوت موسيقى متكامل! 🤖

**مميزاتي:**
• 🔍 البحث عن الأغاني في يوتيوب
• 🛡️ حذف الرسائل المخالفة تلقائياً
• 👤 معرفة معلومات المستخدمين
• ⚡️ سرعة في الاستجابة

**الأوامر:**
`/بحث` + اسم الأغنية - للبحث في يوتيوب
`/ايدي` - لمعرفة الـ ID (رد على شخص)
`/id` - نفس الأمر بالإنجليزي

**للاستخدام:** أضفني إلى مجموعتك واجعلني مشرفاً!
    """
    
    keyboard = [
        [InlineKeyboardButton(
            "➕ أضفني إلى مجموعتك", 
            url=f"https://t.me/{context.bot.username}?startgroup=true"
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_text, 
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر البحث"""
    if not context.args:
        await update.message.reply_text(
            "❌ **طريقة الاستخدام:**\n"
            "`/بحث اسم الأغنية`\n\n"
            "مثال: `/بحث محمد عبده يا غايب`",
            parse_mode='Markdown'
        )
        return
    
    query = ' '.join(context.args)
    status_msg = await update.message.reply_text(f"🔍 جاري البحث عن: *{query}*...", parse_mode='Markdown')
    
    try:
        results = await search_youtube(query)
        
        if not results:
            await status_msg.edit_text("❌ لم أجد نتائج للبحث")
            return
        
        # حذف رسالة الانتظار
        await status_msg.delete()
        
        # عرض النتائج
        for i, video in enumerate(results[:5], 1):
            keyboard = [[InlineKeyboardButton(
                "▶️ تشغيل في يوتيوب", 
                url=video['url']
            )]]
            
            message = (
                f"*{i}. {video['title']}*\n"
                f"👤 {video['channel']}\n"
                f"⏱ {video['duration']}\n"
                f"👁 {video['views']:,} مشاهدة"
            )
            
            await update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        await status_msg.edit_text("❌ حدث خطأ أثناء البحث")

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الحصول على ID"""
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        target_chat = update.message.reply_to_message.chat
        
        info_text = f"""
🆔 **معلومات المستخدم:**

👤 **الاسم:** `{target_user.first_name}`
📝 **اليوزر:** @{target_user.username if target_user.username else 'لا يوجد'}
🆔 **الآيدي:** `{target_user.id}`
🤖 **بوت؟** {'نعم' if target_user.is_bot else 'لا'}

💬 **في المجموعة:**
📛 **اسم المجموعة:** {target_chat.title}
🆔 **آيدي المجموعة:** `{target_chat.id}`
        """
    else:
        user = update.effective_user
        chat = update.effective_chat
        
        info_text = f"""
🆔 **معلوماتك:**

👤 **الاسم:** `{user.first_name}`
📝 **اليوزر:** @{user.username if user.username else 'لا يوجد'}
🆔 **آيديك:** `{user.id}`
🤖 **بوت؟** {'نعم' if user.is_bot else 'لا'}

💬 **المحادثة الحالية:**
📛 **النوع:** {chat.type}
🆔 **الآيدي:** `{chat.id}`
        """
    
    await update.message.reply_text(info_text, parse_mode='Markdown')

async def moderate_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الإشراف التلقائي"""
    message = update.message
    if not message or not message.text:
        return
    
    if contains_banned_words(message.text):
        try:
            await message.delete()
            
            warning = get_warning_message(message.from_user.first_name)
            warn_msg = await context.bot.send_message(
                message.chat.id,
                warning,
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(10)
            await warn_msg.delete()
            
            logger.info(f"Deleted message from {message.from_user.id}")
            
        except Exception as e:
            logger.error(f"Moderation error: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الأخطاء"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """تشغيل البوت"""
    # تشغيل Flask للحفاظ على البوت
    keep_alive()
    
    # إنشاء التطبيق
    application = Application.builder().token(BOT_TOKEN).build()
    
    # الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("بحث", search_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("id", get_id))
    application.add_handler(CommandHandler("ايدي", get_id))
    
    # الإشراف في المجموعات
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            moderate_message
        )
    )
    
    # الأخطاء
    application.add_error_handler(error_handler)
    
    print("🤖 Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
    
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN, GROUP_ID, TOPIC_ID, LANGUAGES, DEFAULT_LANGUAGE, SEMI_AUTOREPLY_MODE
from database import db
from datetime import datetime

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def generate_autoreply(question: str) -> str:
    """Generate a placeholder autoreply (replace with actual AI generation)"""
    return f"[AUTO-REPLY] Thank you for your message: '{question[:50]}...'. Our team will review this and get back to you shortly."

def get_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now().isoformat()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show language selection"""
    user_id = update.effective_user.id
    
    # Check if user already has a language set
    user_language = db.get_user_language(user_id)
    
    if user_language == DEFAULT_LANGUAGE:
        # Show language selection
        keyboard = []
        for lang_code, lang_data in LANGUAGES.items():
            keyboard.append([InlineKeyboardButton(lang_data['name'], callback_data=f"lang_{lang_code}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            LANGUAGES[DEFAULT_LANGUAGE]['welcome'],
            reply_markup=reply_markup
        )
    else:
        # User already has language set
        await update.message.reply_text(LANGUAGES[user_language]['welcome'])

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    language_code = query.data.split('_')[1]
    
    # Set user language
    db.set_user_language(user_id, language_code)
    
    await query.edit_message_text(LANGUAGES[language_code]['language_selected'])

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages from private chats"""
    user_id = update.effective_user.id
    user_language = db.get_user_language(user_id)
    timestamp = get_timestamp()
    
    # Get user info
    user = update.effective_user
    user_handle = user.username or f"{user.first_name} {user.last_name or ''}".strip()
    
    # Create message text with user handle
    message_text = f"From: @{user_handle}\n\n{update.message.text}"
    
    try:
        # Forward message to group/topic
        if TOPIC_ID:
            sent_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=message_text,
                message_thread_id=int(TOPIC_ID)
            )
        else:
            sent_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=message_text
            )
        
        # Store mapping
        db.store_message_mapping(update.message.message_id, sent_message.message_id, user_id)
        
        # Add to TSV file with timestamp
        db.add_conversation(question=update.message.text, timestamp=timestamp)
        
        # Generate autoreply if mode is enabled
        if SEMI_AUTOREPLY_MODE:
            autoreply = generate_autoreply(update.message.text)
            
            # Create approve/discard buttons
            keyboard = [
                [
                    InlineKeyboardButton(LANGUAGES[user_language]['approve'], callback_data=f"approve_{sent_message.message_id}"),
                    InlineKeyboardButton(LANGUAGES[user_language]['discard'], callback_data=f"discard_{sent_message.message_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send autoreply with buttons
            autoreply_text = f"{LANGUAGES[user_language]['generated_reply']}\n\n{autoreply}"
            autoreply_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=autoreply_text,
                reply_markup=reply_markup,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
            
            # Store autoreply mapping
            db.store_autoreply_mapping(autoreply_message.message_id, user_id, update.message.text, autoreply)
            
            # Update TSV with autoreply
            db.update_conversation(question=update.message.text, autoreply=autoreply, is_approved=None, timestamp=timestamp)
        
        # Confirm to user
        await update.message.reply_text(LANGUAGES[user_language]['message_forwarded'])
        
    except Exception as e:
        logger.error(f"Error forwarding message: {e}")
        await update.message.reply_text(LANGUAGES[user_language]['error_occurred'])

async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approve/discard button callbacks"""
    query = update.callback_query
    await query.answer()
    
    action, message_id = query.data.split('_', 1)
    message_id = int(message_id)
    timestamp = get_timestamp()
    
    # Get autoreply info
    autoreply_info = db.get_autoreply_info(query.message.message_id)
    if not autoreply_info:
        await query.edit_message_text("Error: Could not find autoreply information.")
        return
    
    user_id = autoreply_info['user_id']
    question = autoreply_info['question']
    autoreply = autoreply_info['autoreply']
    user_language = db.get_user_language(user_id)
    
    if action == "approve":
        # Send autoreply to user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"{LANGUAGES[user_language]['reply_received']}\n\n{autoreply}"
            )
            
            # Update TSV with approval timestamp
            db.update_conversation(question=question, autoreply=autoreply, is_approved="1", timestamp=timestamp)
            
            # Update the message to show it was approved
            await query.edit_message_text(
                f"{LANGUAGES[user_language]['generated_reply']}\n\n{autoreply}\n\n✅ {LANGUAGES[user_language]['reply_approved']}"
            )
            
        except Exception as e:
            logger.error(f"Error sending approved reply: {e}")
            await query.edit_message_text("Error sending reply to user.")
    
    elif action == "discard":
        # Update TSV with discard timestamp
        db.update_conversation(question=question, autoreply=autoreply, is_approved="0", timestamp=timestamp)
        
        # Update the message to show it was discarded
        await query.edit_message_text(
            f"{LANGUAGES[user_language]['generated_reply']}\n\n{autoreply}\n\n❌ {LANGUAGES[user_language]['reply_discarded']}"
        )

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages in group (replies to forwarded messages)"""
    # Check if this is a reply to a message
    if not update.message.reply_to_message:
        return
    
    # Check if bot is mentioned in the message
    bot_mentioned = False
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == 'mention' and f"@{context.bot.username}" in update.message.text:
                bot_mentioned = True
                break
    
    # Get the original message info
    original_message_id = update.message.reply_to_message.message_id
    user_info = db.get_user_from_group_message(original_message_id)
    timestamp = get_timestamp()
    
    if user_info:
        user_id, user_message_id = user_info
        user_language = db.get_user_language(user_id)
        
        # Check if this is a manual reply after autoreply was discarded
        autoreply_info = None
        for msg_id, info in db.data['autoreply_mappings'].items():
            if info['user_id'] == user_id and info['question'] in update.message.reply_to_message.text:
                autoreply_info = info
                break
        
        # Send reply back to user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"{LANGUAGES[user_language]['reply_received']}\n\n{update.message.text}"
            )
            
            # Update TSV if this was a manual reply after discarded autoreply
            if autoreply_info:
                db.update_conversation(
                    question=autoreply_info['question'],
                    autoreply=autoreply_info['autoreply'],
                    manual_reply=update.message.text,
                    is_approved="Discarded",
                    timestamp=timestamp
                )
            else:
                # Regular manual reply
                question_text = update.message.reply_to_message.text.replace("From: @", "").split("\n\n", 1)[1] if "\n\n" in update.message.reply_to_message.text else update.message.reply_to_message.text
                db.update_conversation(
                    question=question_text,
                    manual_reply=update.message.text,
                    is_approved=None,
                    timestamp=timestamp
                )
            
        except Exception as e:
            logger.error(f"Error sending reply to user: {e}")
    
    elif bot_mentioned:
        # Bot was mentioned in a group, send reply back to the same group
        try:
            # Remove bot mention from message
            reply_text = update.message.text.replace(f"@{context.bot.username}", "").strip()
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=reply_text
            )
        except Exception as e:
            logger.error(f"Error sending group reply: {e}")

async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media messages (photos, documents, etc.)"""
    user_id = update.effective_user.id
    user_language = db.get_user_language(user_id)
    timestamp = get_timestamp()
    
    # Get user info
    user = update.effective_user
    user_handle = user.username or f"{user.first_name} {user.last_name or ''}".strip()
    
    # Create caption with user handle
    caption = f"From: @{user_handle}"
    if update.message.caption:
        caption += f"\n\n{update.message.caption}"
    
    try:
        # Forward media to group/topic
        if update.message.photo:
            sent_message = await context.bot.send_photo(
                chat_id=GROUP_ID,
                photo=update.message.photo[-1].file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        elif update.message.document:
            sent_message = await context.bot.send_document(
                chat_id=GROUP_ID,
                document=update.message.document.file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        elif update.message.video:
            sent_message = await context.bot.send_video(
                chat_id=GROUP_ID,
                video=update.message.video.file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        elif update.message.audio:
            sent_message = await context.bot.send_audio(
                chat_id=GROUP_ID,
                audio=update.message.audio.file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        elif update.message.voice:
            sent_message = await context.bot.send_voice(
                chat_id=GROUP_ID,
                voice=update.message.voice.file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        else:
            return
        
        # Store mapping
        db.store_message_mapping(update.message.message_id, sent_message.message_id, user_id)
        
        # Add to TSV file (for media, we'll use the caption or a placeholder)
        media_text = update.message.caption or "[Media message]"
        db.add_conversation(question=media_text, timestamp=timestamp)
        
        # Generate autoreply if mode is enabled
        if SEMI_AUTOREPLY_MODE:
            autoreply = generate_autoreply(media_text)
            
            # Create approve/discard buttons
            keyboard = [
                [
                    InlineKeyboardButton(LANGUAGES[user_language]['approve'], callback_data=f"approve_{sent_message.message_id}"),
                    InlineKeyboardButton(LANGUAGES[user_language]['discard'], callback_data=f"discard_{sent_message.message_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send autoreply with buttons
            autoreply_text = f"{LANGUAGES[user_language]['generated_reply']}\n\n{autoreply}"
            autoreply_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=autoreply_text,
                reply_markup=reply_markup,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
            
            # Store autoreply mapping
            db.store_autoreply_mapping(autoreply_message.message_id, user_id, media_text, autoreply)
            
            # Update TSV with autoreply
            db.update_conversation(question=media_text, autoreply=autoreply, is_approved=None, timestamp=timestamp)
        
        # Confirm to user
        await update.message.reply_text(LANGUAGES[user_language]['message_forwarded'])
        
    except Exception as e:
        logger.error(f"Error forwarding media message: {e}")
        await update.message.reply_text(LANGUAGES[user_language]['error_occurred'])

async def handle_group_media_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media replies in group"""
    if not update.message.reply_to_message:
        return
    
    # Check if bot is mentioned
    bot_mentioned = False
    if update.message.caption and f"@{context.bot.username}" in update.message.caption:
        bot_mentioned = True
    
    # Get the original message info
    original_message_id = update.message.reply_to_message.message_id
    user_info = db.get_user_from_group_message(original_message_id)
    
    if user_info:
        user_id, user_message_id = user_info
        user_language = db.get_user_language(user_id)
        
        # Send media reply back to user
        try:
            caption = LANGUAGES[user_language]['reply_received']
            if update.message.caption:
                caption += f"\n\n{update.message.caption}"
            
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=update.message.photo[-1].file_id,
                    caption=caption
                )
            elif update.message.document:
                await context.bot.send_document(
                    chat_id=user_id,
                    document=update.message.document.file_id,
                    caption=caption
                )
            elif update.message.video:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=update.message.video.file_id,
                    caption=caption
                )
            elif update.message.audio:
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=update.message.audio.file_id,
                    caption=caption
                )
            elif update.message.voice:
                await context.bot.send_voice(
                    chat_id=user_id,
                    voice=update.message.voice.file_id,
                    caption=caption
                )
        except Exception as e:
            logger.error(f"Error sending media reply to user: {e}")
    
    elif bot_mentioned:
        # Bot was mentioned, send media back to group
        try:
            caption = update.message.caption.replace(f"@{context.bot.username}", "").strip() if update.message.caption else None
            
            if update.message.photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=update.message.photo[-1].file_id,
                    caption=caption
                )
            elif update.message.document:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=update.message.document.file_id,
                    caption=caption
                )
            elif update.message.video:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=update.message.video.file_id,
                    caption=caption
                )
            elif update.message.audio:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id,
                    audio=update.message.audio.file_id,
                    caption=caption
                )
            elif update.message.voice:
                await context.bot.send_voice(
                    chat_id=update.effective_chat.id,
                    voice=update.message.voice.file_id,
                    caption=caption
                )
        except Exception as e:
            logger.error(f"Error sending group media reply: {e}")

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment variables")
        return
    
    if not GROUP_ID:
        logger.error("GROUP_ID not set in environment variables")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(handle_approval_callback, pattern="^(approve|discard)_"))
    
    # Private chat handlers
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        handle_private_message
    ))
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.PHOTO | filters.DOCUMENT | filters.VIDEO | filters.AUDIO | filters.VOICE),
        handle_media_message
    ))
    
    # Group chat handlers
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & filters.REPLY,
        handle_group_message
    ))
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & (filters.PHOTO | filters.DOCUMENT | filters.VIDEO | filters.AUDIO | filters.VOICE) & filters.REPLY,
        handle_group_media_reply
    ))
    
    # Start the bot
    logger.info("Starting bot...")
    application.run_polling()

if __name__ == '__main__':
    main()

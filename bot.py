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

def validate_topic_id(chat_id: int, topic_id: str) -> bool:
    """Validate if a topic ID exists in the chat"""
    try:
        # Try to get chat information to validate topic
        # This is a simple validation - in production you might want more robust checking
        return True if topic_id and topic_id.isdigit() else False
    except Exception:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show language selection"""
    user_id = update.effective_user.id
    logger.info(f"User {user_id} started the bot")
    
    # Check if user already has a language set
    user_language = db.get_user_language(user_id)
    logger.debug(f"User {user_id} language: {user_language}")
    
    if user_language == DEFAULT_LANGUAGE:
        # Show language selection
        logger.info(f"Showing language selection to user {user_id}")
        keyboard = []
        for lang_code, lang_data in LANGUAGES.items():
            keyboard.append([InlineKeyboardButton(lang_data['name'], callback_data=f"lang_{lang_code}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            LANGUAGES[DEFAULT_LANGUAGE]['welcome'],
            reply_markup=reply_markup
        )
        logger.info(f"Language selection sent to user {user_id}")
    else:
        # User already has language set
        logger.info(f"User {user_id} already has language set to {user_language}")
        await update.message.reply_text(LANGUAGES[user_language]['welcome'])
        logger.info(f"Welcome message sent to user {user_id}")

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle language selection callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    language_code = query.data.split('_')[1]
    logger.info(f"User {user_id} selected language: {language_code}")
    
    # Set user language
    db.set_user_language(user_id, language_code)
    logger.debug(f"Language {language_code} set for user {user_id}")
    
    await query.edit_message_text(LANGUAGES[language_code]['language_selected'])
    logger.info(f"Language selection confirmation sent to user {user_id}")

async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages from private chats"""
    user_id = update.effective_user.id
    user_language = db.get_user_language(user_id)
    timestamp = get_timestamp()
    
    logger.info(f"Processing private message from user {user_id} (language: {user_language})")
    
    # Get user info
    user = update.effective_user
    user_handle = user.username or f"{user.first_name} {user.last_name or ''}".strip()
    logger.debug(f"User handle: {user_handle}")
    
    # Create message text with user handle
    message_text = f"From: @{user_handle}\n\n{update.message.text}"
    logger.debug(f"Message text: {message_text[:100]}...")
    
    try:
        # Forward message to group/topic
        logger.info(f"Forwarding message to group {GROUP_ID}")
        if TOPIC_ID:
            logger.info(f"Using topic ID: {TOPIC_ID}")
            sent_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=message_text,
                message_thread_id=int(TOPIC_ID)
            )
        else:
            logger.info("No topic ID, sending to group directly")
            sent_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=message_text
            )
        
        logger.info(f"Message forwarded successfully, sent_message_id: {sent_message.message_id}")
        
        # Store mapping
        logger.debug(f"Storing message mapping: {update.message.message_id} -> {sent_message.message_id}")
        db.store_message_mapping(update.message.message_id, sent_message.message_id, user_id)
        
        # Add to TSV file with timestamp
        logger.debug("Adding conversation to TSV")
        db.add_conversation(question=update.message.text, timestamp=timestamp)
        
        # Generate autoreply if mode is enabled
        if SEMI_AUTOREPLY_MODE:
            logger.info("Semi-autoreply mode enabled, generating autoreply")
            autoreply = generate_autoreply(update.message.text)
            logger.debug(f"Generated autoreply: {autoreply[:100]}...")
            
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
            logger.info("Sending autoreply to group")
            autoreply_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=autoreply_text,
                reply_markup=reply_markup,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
            
            logger.info(f"Autoreply sent successfully, autoreply_message_id: {autoreply_message.message_id}")
            
            # Store autoreply mapping
            logger.debug("Storing autoreply mapping")
            db.store_autoreply_mapping(autoreply_message.message_id, user_id, update.message.text, autoreply)
            
            # Update TSV with autoreply
            logger.debug("Updating conversation with autoreply")
            db.update_conversation(question=update.message.text, autoreply=autoreply, is_approved=None, timestamp=timestamp)
        else:
            logger.info("Semi-autoreply mode disabled")
        
        # Confirm to user
        logger.info(f"Sending confirmation to user {user_id}")
        await update.message.reply_text(LANGUAGES[user_language]['message_forwarded'])
        logger.info("Confirmation sent successfully")
        
    except Exception as e:
        logger.error(f"Error forwarding message: {e}")
        await update.message.reply_text(LANGUAGES[user_language]['error_occurred'])

async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approve/discard callbacks for autoreplies"""
    query = update.callback_query
    await query.answer()
    
    action, message_id = query.data.split('_')
    message_id = int(message_id)
    user_id = query.from_user.id
    
    logger.info(f"User {user_id} {action}ed autoreply for message {message_id}")
    
    if action == "approve":
        # Send autoreply to user
        try:
            # Get autoreply info
            autoreply_info = db.get_autoreply_info(message_id)
            if autoreply_info:
                target_user_id = autoreply_info['user_id']
                autoreply = autoreply_info['autoreply']
                user_language = db.get_user_language(target_user_id)
                logger.info(f"Approving autoreply for user {target_user_id}")
                
                # Send autoreply to user
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"{LANGUAGES[user_language]['generated_reply']}\n\n{autoreply}"
                )
                logger.info(f"Autoreply sent to user {target_user_id}")
                
                # Update TSV
                timestamp = get_timestamp()
                db.update_conversation(
                    question=autoreply_info['question'],
                    autoreply=autoreply,
                    is_approved="Approved",
                    timestamp=timestamp
                )
                logger.debug("Conversation updated with approved status")
                
                # Update the message to show it was approved
                await query.edit_message_text(
                    f"{LANGUAGES[user_language]['generated_reply']}\n\n{autoreply}\n\n✅ {LANGUAGES[user_language]['reply_approved']}"
                )
                logger.info("Approval message updated")
            else:
                logger.error(f"Autoreply info not found for message {message_id}")
                await query.edit_message_text("Error: Autoreply info not found")
        except Exception as e:
            logger.error(f"Error approving autoreply: {e}")
            await query.edit_message_text("Error occurred while approving autoreply")
    
    elif action == "discard":
        # Mark autoreply as discarded
        try:
            autoreply_info = db.get_autoreply_info(message_id)
            if autoreply_info:
                target_user_id = autoreply_info['user_id']
                user_language = db.get_user_language(target_user_id)
                logger.info(f"Discarding autoreply for user {target_user_id}")
                
                # Update TSV
                timestamp = get_timestamp()
                db.update_conversation(
                    question=autoreply_info['question'],
                    autoreply=autoreply_info['autoreply'],
                    is_approved="Discarded",
                    timestamp=timestamp
                )
                logger.debug("Conversation updated with discarded status")
                
                # Update the message to show it was discarded
                await query.edit_message_text(
                    f"{LANGUAGES[user_language]['generated_reply']}\n\n{autoreply_info['autoreply']}\n\n❌ {LANGUAGES[user_language]['reply_discarded']}"
                )
                logger.info("Discard message updated")
            else:
                logger.error(f"Autoreply info not found for message {message_id}")
                await query.edit_message_text("Error: Autoreply info not found")
        except Exception as e:
            logger.error(f"Error discarding autoreply: {e}")
            await query.edit_message_text("Error occurred while discarding autoreply")

def is_bot_mentioned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if bot is mentioned in the message (works for both public and private groups)"""
    bot_username = context.bot.username
    if not bot_username:
        logger.warning("Bot username not available for mention detection")
        return False
    
    logger.debug(f"Checking for bot mention in message from user {update.effective_user.id}")
    
    # Check text content for bot mention
    if update.message.text:
        # Check for @username mention
        if f"@{bot_username}" in update.message.text:
            logger.info(f"Bot mentioned via @{bot_username} in text message")
            return True
        
        # Check for /username mention (without @)
        if f"/{bot_username}" in update.message.text:
            logger.info(f"Bot mentioned via /{bot_username} in text message")
            return True
    
    # Check caption for bot mention
    if update.message.caption:
        if f"@{bot_username}" in update.message.caption:
            logger.info(f"Bot mentioned via @{bot_username} in media caption")
            return True
        if f"/{bot_username}" in update.message.caption:
            logger.info(f"Bot mentioned via /{bot_username} in media caption")
            return True
    
    # Check entities for mentions (more reliable in public groups)
    if update.message.entities:
        for entity in update.message.entities:
            if entity.type == 'mention':
                mention_text = update.message.text[entity.offset:entity.offset + entity.length]
                if mention_text == f"@{bot_username}":
                    logger.info(f"Bot mentioned via entity detection: {mention_text}")
                    return True
            elif entity.type == 'bot_command':
                command_text = update.message.text[entity.offset:entity.offset + entity.length]
                if command_text == f"/{bot_username}":
                    logger.info(f"Bot mentioned via command entity: {command_text}")
                    return True
    
    logger.debug("No bot mention detected")
    return False

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages in group (replies to forwarded messages)"""
    group_id = update.effective_chat.id
    logger.info(f"Processing group message from user {update.effective_user.id} in group {group_id}")
    
    # Check if this is a reply to a message
    if not update.message.reply_to_message:
        logger.debug(f"Message is not a reply, ignoring (group {group_id})")
        return
    
    logger.debug(f"Message is a reply to message ID {update.message.reply_to_message.message_id} in group {group_id}")
    
    # Check if bot is mentioned in the message using improved detection
    bot_mentioned = is_bot_mentioned(update, context)
    logger.debug(f"Bot mentioned: {bot_mentioned} (group {group_id})")
    
    # Get the original message info
    original_message_id = update.message.reply_to_message.message_id
    user_info = db.get_user_from_group_message(original_message_id)
    timestamp = get_timestamp()
    
    logger.debug(f"User info lookup result: {user_info} (group {group_id})")
    
    if user_info:
        user_id, user_message_id, source_group_id = user_info
        user_language = db.get_user_language(user_id)
        logger.info(f"Found user info: user_id={user_id}, user_language={user_language}, source_group_id={source_group_id} (group {group_id})")
        
        # Check if this is a manual reply after autoreply was discarded
        autoreply_info = None
        for msg_id, info in db.data['autoreply_mappings'].items():
            if info['user_id'] == user_id and info['question'] in update.message.reply_to_message.text:
                autoreply_info = info
                logger.info(f"Found autoreply info for user {user_id} (group {group_id})")
                break
        
        # Send reply back to source group mentioning the user
        try:
            if source_group_id:
                # This is a group-to-group forward, send reply back to source group
                logger.info(f"Sending reply back to source group {source_group_id} mentioning user {user_id}")
                
                # Get user info for mention
                user_handle = f"@{user_id}"  # We'll need to get the actual username
                reply_text = f"@{user_handle}: {update.message.text}"
                
                await context.bot.send_message(
                    chat_id=source_group_id,
                    text=reply_text
                )
                logger.info(f"Successfully sent reply to source group {source_group_id} mentioning user {user_id}")
            else:
                # This is a private message forward, send reply directly to user
                logger.info(f"Sending reply to user {user_id} from group {group_id}")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"{LANGUAGES[user_language]['reply_received']}\n\n{update.message.text}"
                )
                logger.info(f"Successfully sent reply to user {user_id} from group {group_id}")
            
            # Update TSV if this was a manual reply after discarded autoreply
            if autoreply_info:
                logger.info(f"Updating conversation with discarded autoreply info (group {group_id})")
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
                logger.info(f"Updating conversation with regular manual reply (group {group_id})")
                db.update_conversation(
                    question=question_text,
                    manual_reply=update.message.text,
                    is_approved=None,
                    timestamp=timestamp
                )
            
        except Exception as e:
            logger.error(f"Error sending reply from group {group_id}: {e}")
    
    elif bot_mentioned:
        # Bot was mentioned in a group, forward message to target group instead of sending back to same group
        logger.info(f"Bot was mentioned in group {group_id}, forwarding to target group {GROUP_ID}")
        try:
            # Remove bot mention from message
            reply_text = update.message.text.replace(f"@{context.bot.username}", "").strip()
            logger.debug(f"Reply text after removing mention: {reply_text} (group {group_id})")
            
            if reply_text:
                # Get user info for the mention
                user = update.effective_user
                user_handle = user.username or f"{user.first_name} {user.last_name or ''}".strip()
                logger.debug(f"User handle: {user_handle} (group {group_id})")
                
                # Create message with source group info and username
                source_group_title = update.effective_chat.title or f"Group {group_id}"
                full_message = f"From group: {source_group_title}\nFrom user: @{user_handle}\n\n{reply_text}"
                logger.info(f"Forwarding message to target group: {full_message[:100]}...")
                
                # Send to target group and topic
                if TOPIC_ID:
                    try:
                        logger.info(f"Attempting to send to topic {TOPIC_ID} in target group {GROUP_ID}")
                        sent_message = await context.bot.send_message(
                            chat_id=GROUP_ID,
                            text=full_message,
                            message_thread_id=int(TOPIC_ID)
                        )
                        logger.info(f"Successfully forwarded to topic {TOPIC_ID} in target group {GROUP_ID}")
                        
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for group forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                        
                    except Exception as topic_error:
                        logger.warning(f"Failed to send to topic {TOPIC_ID} in target group {GROUP_ID}: {topic_error}")
                        logger.info(f"Falling back to sending to target group {GROUP_ID} directly")
                        sent_message = await context.bot.send_message(
                            chat_id=GROUP_ID,
                            text=full_message
                        )
                        logger.info(f"Successfully forwarded to target group {GROUP_ID} (fallback)")
                        
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for group forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                else:
                    logger.info(f"Sending to target group {GROUP_ID}")
                    sent_message = await context.bot.send_message(
                        chat_id=GROUP_ID,
                        text=full_message
                    )
                    logger.info(f"Successfully forwarded to target group {GROUP_ID}")
                    
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for group forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                
                # Confirm to the user in the source group
                confirmation = f"✅ Your message has been forwarded to the support team."
                await context.bot.send_message(
                    chat_id=group_id,
                    text=confirmation
                )
                logger.info(f"Confirmation sent to source group {group_id}")
            else:
                logger.debug(f"No text after removing mention, ignoring (group {group_id})")
        except Exception as e:
            logger.error(f"Error forwarding message from group {group_id} to target group: {e}")
            # Try to send error message to source group
            try:
                await context.bot.send_message(
                    chat_id=group_id,
                    text="❌ An error occurred while forwarding your message."
                )
            except:
                pass
    else:
        logger.debug(f"No user info found and bot not mentioned, ignoring message (group {group_id})")

async def handle_media_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media messages (photos, documents, etc.)"""
    user_id = update.effective_user.id
    user_language = db.get_user_language(user_id)
    timestamp = get_timestamp()
    
    logger.info(f"Processing media message from user {user_id} (language: {user_language})")
    
    # Get user info
    user = update.effective_user
    user_handle = user.username or f"{user.first_name} {user.last_name or ''}".strip()
    logger.debug(f"User handle: {user_handle}")
    
    # Create caption with user handle
    caption = f"From: @{user_handle}"
    if update.message.caption:
        caption += f"\n\n{update.message.caption}"
        logger.debug(f"Media has caption: {update.message.caption[:50]}...")
    
    logger.debug(f"Final caption: {caption[:100]}...")
    
    try:
        # Forward media to group/topic
        logger.info(f"Forwarding media to group {GROUP_ID}")
        if update.message.photo:
            logger.info("Forwarding photo")
            sent_message = await context.bot.send_photo(
                chat_id=GROUP_ID,
                photo=update.message.photo[-1].file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        elif update.message.document:
            logger.info("Forwarding document")
            sent_message = await context.bot.send_document(
                chat_id=GROUP_ID,
                document=update.message.document.file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        elif update.message.video:
            logger.info("Forwarding video")
            sent_message = await context.bot.send_video(
                chat_id=GROUP_ID,
                video=update.message.video.file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        elif update.message.audio:
            logger.info("Forwarding audio")
            sent_message = await context.bot.send_audio(
                chat_id=GROUP_ID,
                audio=update.message.audio.file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        elif update.message.voice:
            logger.info("Forwarding voice message")
            sent_message = await context.bot.send_voice(
                chat_id=GROUP_ID,
                voice=update.message.voice.file_id,
                caption=caption,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
        else:
            logger.warning("Unknown media type, ignoring")
            return
        
        logger.info(f"Media forwarded successfully, sent_message_id: {sent_message.message_id}")
        
        # Store mapping
        logger.debug(f"Storing media message mapping: {update.message.message_id} -> {sent_message.message_id}")
        db.store_message_mapping(update.message.message_id, sent_message.message_id, user_id)
        
        # Add to TSV file (for media, we'll use the caption or a placeholder)
        media_text = update.message.caption or "[Media message]"
        logger.debug(f"Adding media conversation to TSV: {media_text}")
        db.add_conversation(question=media_text, timestamp=timestamp)
        
        # Generate autoreply if mode is enabled
        if SEMI_AUTOREPLY_MODE:
            logger.info("Semi-autoreply mode enabled for media, generating autoreply")
            autoreply = generate_autoreply(media_text)
            logger.debug(f"Generated media autoreply: {autoreply[:100]}...")
            
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
            logger.info("Sending media autoreply to group")
            autoreply_message = await context.bot.send_message(
                chat_id=GROUP_ID,
                text=autoreply_text,
                reply_markup=reply_markup,
                message_thread_id=int(TOPIC_ID) if TOPIC_ID else None
            )
            
            logger.info(f"Media autoreply sent successfully, autoreply_message_id: {autoreply_message.message_id}")
            
            # Store autoreply mapping
            logger.debug("Storing media autoreply mapping")
            db.store_autoreply_mapping(autoreply_message.message_id, user_id, media_text, autoreply)
            
            # Update TSV with autoreply
            logger.debug("Updating media conversation with autoreply")
            db.update_conversation(question=media_text, autoreply=autoreply, is_approved=None, timestamp=timestamp)
        else:
            logger.info("Semi-autoreply mode disabled for media")
        
        # Confirm to user
        logger.info(f"Sending media confirmation to user {user_id}")
        await update.message.reply_text(LANGUAGES[user_language]['message_forwarded'])
        logger.info("Media confirmation sent successfully")
        
    except Exception as e:
        logger.error(f"Error forwarding media message: {e}")
        await update.message.reply_text(LANGUAGES[user_language]['error_occurred'])

async def handle_group_media_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle media replies in group"""
    group_id = update.effective_chat.id
    logger.info(f"Processing group media reply from user {update.effective_user.id} in group {group_id}")
    
    if not update.message.reply_to_message:
        logger.debug(f"Media message is not a reply, ignoring (group {group_id})")
        return
    
    logger.debug(f"Media reply to message ID {update.message.reply_to_message.message_id} in group {group_id}")
    
    # Check if bot is mentioned using improved detection
    bot_mentioned = is_bot_mentioned(update, context)
    logger.debug(f"Bot mentioned in media reply: {bot_mentioned} (group {group_id})")
    
    # Get the original message info
    original_message_id = update.message.reply_to_message.message_id
    user_info = db.get_user_from_group_message(original_message_id)
    logger.debug(f"User info lookup result: {user_info} (group {group_id})")
    
    if user_info:
        user_id, user_message_id, source_group_id = user_info
        user_language = db.get_user_language(user_id)
        logger.info(f"Found user info: user_id={user_id}, user_language={user_language}, source_group_id={source_group_id} (group {group_id})")
        
        # Send media reply back to user
        try:
            logger.info(f"Sending media reply to user {user_id} from group {group_id}")
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
            logger.info(f"Successfully sent media reply to user {user_id} from group {group_id}")
        except Exception as e:
            logger.error(f"Error sending media reply to user {user_id} from group {group_id}: {e}")
    
    elif bot_mentioned:
        # Bot was mentioned, forward media to target group instead of sending back to same group
        logger.info(f"Bot was mentioned in media, forwarding to target group {GROUP_ID}")
        try:
            # Get user info for the mention
            user = update.effective_user
            user_handle = user.username or f"{user.first_name} {user.last_name or ''}".strip()
            logger.debug(f"User handle: {user_handle} (group {group_id})")
            
            # Remove bot mention and add username to caption
            if update.message.caption:
                caption = update.message.caption.replace(f"@{context.bot.username}", "").strip()
                caption = f"From group: {update.effective_chat.title or f'Group {group_id}'}\nFrom user: @{user_handle}\n\n{caption}"
                logger.debug(f"Caption after processing: {caption} (group {group_id})")
            else:
                source_group_title = update.effective_chat.title or f"Group {group_id}"
                caption = f"From group: {source_group_title}\nFrom user: @{user_handle}"
                logger.debug(f"No caption, using user handle: {caption} (group {group_id})")
            
            # Send to target group and topic
            logger.info(f"Forwarding media to target group {GROUP_ID}")
            if TOPIC_ID:
                try:
                    logger.info(f"Attempting to send media to topic {TOPIC_ID} in target group {GROUP_ID}")
                    if update.message.photo:
                        sent_message = await context.bot.send_photo(
                            chat_id=GROUP_ID,
                            photo=update.message.photo[-1].file_id,
                            caption=caption,
                            message_thread_id=int(TOPIC_ID)
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    elif update.message.document:
                        sent_message = await context.bot.send_document(
                            chat_id=GROUP_ID,
                            document=update.message.document.file_id,
                            caption=caption,
                            message_thread_id=int(TOPIC_ID)
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    elif update.message.video:
                        sent_message = await context.bot.send_video(
                            chat_id=GROUP_ID,
                            video=update.message.video.file_id,
                            caption=caption,
                            message_thread_id=int(TOPIC_ID)
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    elif update.message.audio:
                        sent_message = await context.bot.send_audio(
                            chat_id=GROUP_ID,
                            audio=update.message.audio.file_id,
                            caption=caption,
                            message_thread_id=int(TOPIC_ID)
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    elif update.message.voice:
                        sent_message = await context.bot.send_voice(
                            chat_id=GROUP_ID,
                            voice=update.message.voice.file_id,
                            caption=caption,
                            message_thread_id=int(TOPIC_ID)
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    logger.info(f"Successfully forwarded media to topic {TOPIC_ID} in target group {GROUP_ID}")
                except Exception as topic_error:
                    logger.warning(f"Failed to send media to topic {TOPIC_ID} in target group {GROUP_ID}: {topic_error}")
                    logger.info(f"Falling back to sending media to target group {GROUP_ID} directly")
                    if update.message.photo:
                        sent_message = await context.bot.send_photo(
                            chat_id=GROUP_ID,
                            photo=update.message.photo[-1].file_id,
                            caption=caption
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    elif update.message.document:
                        sent_message = await context.bot.send_document(
                            chat_id=GROUP_ID,
                            document=update.message.document.file_id,
                            caption=caption
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    elif update.message.video:
                        sent_message = await context.bot.send_video(
                            chat_id=GROUP_ID,
                            video=update.message.video.file_id,
                            caption=caption
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    elif update.message.audio:
                        sent_message = await context.bot.send_audio(
                            chat_id=GROUP_ID,
                            audio=update.message.audio.file_id,
                            caption=caption
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    elif update.message.voice:
                        sent_message = await context.bot.send_voice(
                            chat_id=GROUP_ID,
                            voice=update.message.voice.file_id,
                            caption=caption
                        )
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                    logger.info(f"Successfully forwarded media to target group {GROUP_ID} (fallback)")
            else:
                logger.info(f"Sending media to target group {GROUP_ID}")
                if update.message.photo:
                    sent_message = await context.bot.send_photo(
                        chat_id=GROUP_ID,
                        photo=update.message.photo[-1].file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.document:
                    sent_message = await context.bot.send_document(
                        chat_id=GROUP_ID,
                        document=update.message.document.file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.video:
                    sent_message = await context.bot.send_video(
                        chat_id=GROUP_ID,
                        video=update.message.video.file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.audio:
                    sent_message = await context.bot.send_audio(
                        chat_id=GROUP_ID,
                        audio=update.message.audio.file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.voice:
                    sent_message = await context.bot.send_voice(
                        chat_id=GROUP_ID,
                        voice=update.message.voice.file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media reply forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                logger.info(f"Successfully forwarded media to target group {GROUP_ID}")
            
            # Confirm to the user in the source group
            confirmation = f"✅ Your media has been forwarded to the support team."
            await context.bot.send_message(
                chat_id=group_id,
                text=confirmation
            )
            logger.info(f"Confirmation sent to source group {group_id}")
        except Exception as e:
            logger.error(f"Error forwarding media from group {group_id} to target group: {e}")
            # Try to send error message to source group
            try:
                await context.bot.send_message(
                    chat_id=group_id,
                    text="❌ An error occurred while forwarding your media."
                )
            except:
                pass
    else:
        logger.debug(f"No user info found and bot not mentioned, ignoring media message (group {group_id})")

async def handle_group_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle standalone bot mentions in group chats (not replies)"""
    group_id = update.effective_chat.id
    logger.info(f"Processing standalone group mention from user {update.effective_user.id} in group {group_id}")
    
    # Check if bot is mentioned in the message
    if not is_bot_mentioned(update, context):
        logger.debug(f"Bot not mentioned in standalone message, ignoring (group {group_id})")
        return
    
    logger.info(f"Bot mentioned in standalone message, forwarding to target group {GROUP_ID}")
    
    try:
        # Remove bot mention from message
        if update.message.text:
            reply_text = update.message.text.replace(f"@{context.bot.username}", "").strip()
            logger.debug(f"Reply text after removing mention: {reply_text} (group {group_id})")
            
            if reply_text:
                # Get user info for the mention
                user = update.effective_user
                user_handle = user.username or f"{user.first_name} {user.last_name or ''}".strip()
                logger.debug(f"User handle: {user_handle} (group {group_id})")
                
                # Create message with source group info and username
                source_group_title = update.effective_chat.title or f"Group {group_id}"
                full_message = f"From group: {source_group_title}\nFrom user: @{user_handle}\n\n{reply_text}"
                logger.info(f"Forwarding standalone message to target group: {full_message[:100]}...")
                
                # Send to target group and topic
                if TOPIC_ID:
                    try:
                        logger.info(f"Attempting to send to topic {TOPIC_ID} in target group {GROUP_ID}")
                        sent_message = await context.bot.send_message(
                            chat_id=GROUP_ID,
                            text=full_message,
                            message_thread_id=int(TOPIC_ID)
                        )
                        logger.info(f"Successfully forwarded to topic {TOPIC_ID} in target group {GROUP_ID}")
                        
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for standalone group forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                        
                    except Exception as topic_error:
                        logger.warning(f"Failed to send to topic {TOPIC_ID} in target group {GROUP_ID}: {topic_error}")
                        logger.info(f"Falling back to sending to target group {GROUP_ID} directly")
                        sent_message = await context.bot.send_message(
                            chat_id=GROUP_ID,
                            text=full_message
                        )
                        logger.info(f"Successfully forwarded to target group {GROUP_ID} (fallback)")
                        
                        # Store message mapping for replies
                        logger.debug(f"Storing message mapping for standalone group forward: {update.message.message_id} -> {sent_message.message_id}")
                        db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                else:
                    logger.info(f"Sending to target group {GROUP_ID}")
                    sent_message = await context.bot.send_message(
                        chat_id=GROUP_ID,
                        text=full_message
                    )
                    logger.info(f"Successfully forwarded to target group {GROUP_ID}")
                    
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for standalone group forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                
                # Confirm to the user in the source group
                confirmation = f"✅ Your message has been forwarded to the support team."
                await context.bot.send_message(
                    chat_id=group_id,
                    text=confirmation
                )
                logger.info(f"Confirmation sent to source group {group_id}")
            else:
                logger.debug(f"No text after removing mention, ignoring (group {group_id})")
        else:
            logger.debug(f"No text in message, ignoring (group {group_id})")
    except Exception as e:
        logger.error(f"Error forwarding standalone message from group {group_id} to target group: {e}")
        # Try to send error message to source group
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text="❌ An error occurred while forwarding your message."
            )
        except:
            pass

async def handle_group_media_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle standalone bot mentions with media in group chats (not replies)"""
    group_id = update.effective_chat.id
    logger.info(f"Processing standalone group media mention from user {update.effective_user.id} in group {group_id}")
    
    # Check if bot is mentioned in the message
    if not is_bot_mentioned(update, context):
        logger.debug(f"Bot not mentioned in standalone media message, ignoring (group {group_id})")
        return
    
    logger.info(f"Bot mentioned in standalone media message, processing (group {group_id})")
    
    try:
        # Get user info for the mention
        user = update.effective_user
        user_handle = user.username or f"{user.first_name} {user.last_name or ''}".strip()
        logger.debug(f"User handle: {user_handle} (group {group_id})")
        
        # Remove bot mention and add username to caption
        if update.message.caption:
            caption = update.message.caption.replace(f"@{context.bot.username}", "").strip()
            caption = f"From group: {update.effective_chat.title or f'Group {group_id}'}\nFrom user: @{user_handle}\n\n{caption}"
            logger.debug(f"Caption after processing: {caption} (group {group_id})")
        else:
            source_group_title = update.effective_chat.title or f"Group {group_id}"
            caption = f"From group: {source_group_title}\nFrom user: @{user_handle}"
            logger.debug(f"No caption, using user handle: {caption} (group {group_id})")
        
        # Send to configured target group instead of the group where mention occurred
        logger.info(f"Bot mentioned in group {group_id}, forwarding media to configured target group {GROUP_ID}")
        if TOPIC_ID:
            try:
                logger.info(f"Attempting to send media to topic {TOPIC_ID} in target group {GROUP_ID}")
                if update.message.photo:
                    sent_message = await context.bot.send_photo(
                        chat_id=GROUP_ID,
                        photo=update.message.photo[-1].file_id,
                        caption=caption,
                        message_thread_id=int(TOPIC_ID)
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.document:
                    sent_message = await context.bot.send_document(
                        chat_id=GROUP_ID,
                        document=update.message.document.file_id,
                        caption=caption,
                        message_thread_id=int(TOPIC_ID)
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.video:
                    sent_message = await context.bot.send_video(
                        chat_id=GROUP_ID,
                        video=update.message.video.file_id,
                        caption=caption,
                        message_thread_id=int(TOPIC_ID)
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.audio:
                    sent_message = await context.bot.send_audio(
                        chat_id=GROUP_ID,
                        audio=update.message.audio.file_id,
                        caption=caption,
                        message_thread_id=int(TOPIC_ID)
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.voice:
                    sent_message = await context.bot.send_voice(
                        chat_id=GROUP_ID,
                        voice=update.message.voice.file_id,
                        caption=caption,
                        message_thread_id=int(TOPIC_ID)
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                logger.info(f"Successfully sent media to topic {TOPIC_ID} in target group {GROUP_ID}")
            except Exception as topic_error:
                logger.warning(f"Failed to send media to topic {TOPIC_ID} in target group {GROUP_ID}: {topic_error}")
                logger.info(f"Falling back to sending media to target group {GROUP_ID} directly")
                if update.message.photo:
                    sent_message = await context.bot.send_photo(
                        chat_id=GROUP_ID,
                        photo=update.message.photo[-1].file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.document:
                    sent_message = await context.bot.send_document(
                        chat_id=GROUP_ID,
                        document=update.message.document.file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.video:
                    sent_message = await context.bot.send_video(
                        chat_id=GROUP_ID,
                        video=update.message.video.file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.audio:
                    sent_message = await context.bot.send_audio(
                        chat_id=GROUP_ID,
                        audio=update.message.audio.file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                elif update.message.voice:
                    sent_message = await context.bot.send_voice(
                        chat_id=GROUP_ID,
                        voice=update.message.voice.file_id,
                        caption=caption
                    )
                    # Store message mapping for replies
                    logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                    db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
                logger.info(f"Successfully sent media to target group {GROUP_ID} (fallback)")
        else:
            logger.info(f"Sending media to target group {GROUP_ID}")
            if update.message.photo:
                sent_message = await context.bot.send_photo(
                    chat_id=GROUP_ID,
                    photo=update.message.photo[-1].file_id,
                    caption=caption
                )
                # Store message mapping for replies
                logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
            elif update.message.document:
                sent_message = await context.bot.send_document(
                    chat_id=GROUP_ID,
                    document=update.message.document.file_id,
                    caption=caption
                )
                # Store message mapping for replies
                logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
            elif update.message.video:
                sent_message = await context.bot.send_video(
                    chat_id=GROUP_ID,
                    video=update.message.video.file_id,
                    caption=caption
                )
                # Store message mapping for replies
                logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
            elif update.message.audio:
                sent_message = await context.bot.send_audio(
                    chat_id=GROUP_ID,
                    audio=update.message.audio.file_id,
                    caption=caption
                )
                # Store message mapping for replies
                logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
            elif update.message.voice:
                sent_message = await context.bot.send_voice(
                    chat_id=GROUP_ID,
                    voice=update.message.voice.file_id,
                    caption=caption
                )
                # Store message mapping for replies
                logger.debug(f"Storing message mapping for media forward: {update.message.message_id} -> {sent_message.message_id}")
                db.store_message_mapping(update.message.message_id, sent_message.message_id, user.id, group_id)
            logger.info(f"Successfully sent media to target group {GROUP_ID}")
        logger.info(f"Successfully forwarded media mention from group {group_id} to target group {GROUP_ID}")
        
        # Confirm to the user in the source group
        confirmation = f"✅ Your media has been forwarded to the support team."
        await context.bot.send_message(
            chat_id=group_id,
            text=confirmation
        )
        logger.info(f"Confirmation sent to source group {group_id}")
    except Exception as e:
        logger.error(f"Error handling group media mention in group {group_id}: {e}")
        # Try to send error message to source group
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text="❌ An error occurred while forwarding your media."
            )
        except:
            pass

def main():
    """Start the bot"""
    logger.info("Initializing bot...")
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment variables")
        return
    
    if not GROUP_ID:
        logger.error("GROUP_ID not set in environment variables")
        return
    
    logger.info(f"Bot configuration: GROUP_ID={GROUP_ID}, TOPIC_ID={TOPIC_ID}, SEMI_AUTOREPLY_MODE={SEMI_AUTOREPLY_MODE}")
    
    # Validate topic ID if provided
    if TOPIC_ID:
        if not validate_topic_id(int(GROUP_ID), TOPIC_ID):
            logger.warning(f"TOPIC_ID {TOPIC_ID} may be invalid. Bot will fall back to group chat if topic sending fails.")
        else:
            logger.info(f"TOPIC_ID {TOPIC_ID} appears valid")
    else:
        logger.info("No TOPIC_ID configured, all messages will be sent to group chat")
    
    # Create application
    logger.info("Creating application...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    logger.info("Registering handlers...")
    application.add_handler(CommandHandler("start", start))
    logger.debug("Registered /start command handler")
    
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    logger.debug("Registered language callback handler")
    
    application.add_handler(CallbackQueryHandler(handle_approval_callback, pattern="^(approve|discard)_"))
    logger.debug("Registered approval callback handler")
    
    # Private chat handlers
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
        handle_private_message
    ))
    logger.debug("Registered private text message handler")
    
    application.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & (filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE),
        handle_media_message
    ))
    logger.debug("Registered private media message handler")
    
    # Group chat handlers
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & filters.REPLY,
        handle_group_message
    ))
    logger.debug("Registered group text reply handler")
    
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & (filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE) & filters.REPLY,
        handle_group_media_reply
    ))
    logger.debug("Registered group media reply handler")
    
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & filters.TEXT & ~filters.REPLY,
        handle_group_mention
    ))
    logger.debug("Registered standalone group text mention handler")
    
    application.add_handler(MessageHandler(
        filters.ChatType.GROUPS & (filters.PHOTO | filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE) & ~filters.REPLY,
        handle_group_media_mention
    ))
    logger.debug("Registered standalone group media mention handler")
    
    # Start the bot
    logger.info("All handlers registered successfully")
    logger.info("Starting bot polling...")
    application.run_polling()

if __name__ == '__main__':
    main()

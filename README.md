# Telegram Support Bot

A Telegram bot that forwards messages from users to a support group and handles replies. The bot supports multiple languages (English, Russian, and Georgian) and can handle both text and media messages. It includes a semi-autoreply mode with approval/discard functionality.

## Features

- **Multi-language support**: English, Russian, and Georgian
- **Message forwarding**: Forwards user messages to a designated support group/topic
- **Reply handling**: Sends replies from the support group back to the original user
- **Group mentions**: When the bot is mentioned in a group, it sends the reply back to that group
- **Media support**: Handles photos, documents, videos, audio, and voice messages
- **Anonymous replies**: Replies are sent without showing who wrote them
- **User handle display**: Shows the sender's handle in forwarded messages
- **Semi-autoreply mode**: Generates automatic replies with approval/discard buttons
- **TSV storage**: Stores all conversations in a TSV file for analysis
- **Approval workflow**: Support team can approve or discard generated replies
- **Timestamp logging**: Tracks when messages and replies are sent

## Setup

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the instructions
3. Copy the bot token you receive

### 2. Get Group ID

1. Add your bot to the support group
2. Send a message in the group
3. Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find the `chat.id` field in the response (it will be a negative number)
5. If using a forum group, also note the `message_thread_id` for the topic

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp env_example.txt .env
```

Edit the `.env` file with your actual values:

```env
BOT_TOKEN=your_actual_bot_token_here
GROUP_ID=-1001234567890
TOPIC_ID=123  # Optional, only for forum groups
SEMI_AUTOREPLY_MODE=true  # Enable/disable semi-autoreply mode
TSV_FILE=conversations.tsv  # File to store conversations
```

### 5. Run the Bot

```bash
python bot.py
```

## Usage

### For Users

1. Start a conversation with the bot by sending `/start`
2. Choose your preferred language (English, Russian, or Georgian)
3. Send any message (text or media) to the bot
4. The bot will forward your message to the support team
5. When the support team replies, you'll receive the response

### For Support Team

#### Semi-Autoreply Mode (Enabled by default)

1. **Generated replies**: When a user sends a message, the bot generates an automatic reply
2. **Approval buttons**: Each generated reply comes with "Approve" and "Discard" buttons
3. **Approve**: Click "Approve" to send the generated reply to the user
4. **Discard**: Click "Discard" to reject the generated reply
5. **Manual reply after discard**: If you discard an autoreply, you can still reply manually to the original message

#### Manual Reply Mode

1. **Direct replies**: Simply reply to any forwarded message in the support group
2. **Group mentions**: Include `@your_bot_username` in your message to send a reply to the same group

### Message Flow

#### With Semi-Autoreply Mode:
1. **User → Bot**: User sends a message to the bot
2. **Bot → Support Group**: Bot forwards the message with user handle to the support group
3. **Bot → Support Group**: Bot generates and sends an autoreply with approve/discard buttons
4. **Support Team → Bot**: Support team clicks "Approve" or "Discard"
5. **Bot → User**: If approved, bot sends the autoreply to the user
6. **Support Team → Bot**: If discarded, support team can reply manually to the original message
7. **Bot → User**: Manual reply is sent to the user

#### Without Semi-Autoreply Mode:
1. **User → Bot**: User sends a message to the bot
2. **Bot → Support Group**: Bot forwards the message with user handle to the support group
3. **Support Team → Bot**: Support team replies to the forwarded message
4. **Bot → User**: Bot sends the reply back to the original user

## TSV File Structure

The bot stores all conversations in a TSV file with the following columns:

- **Timestamp**: ISO format timestamp when the action occurred
- **Question**: The original message from the user
- **Autoreply**: The generated automatic reply (if any)
- **Manual reply**: The manual reply from support team (if any)
- **is_approved**: Approval status
  - `1`: Autoreply was approved and sent
  - `0`: Autoreply was discarded
  - `None`: Semi-autoreply mode is disabled or no autoreply was generated
  - `"Discarded"`: Autoreply was discarded and then a manual reply was sent

### Example TSV Entry:
```
2024-01-15T10:30:45.123456	Hello, I need help	[AUTO-REPLY] Thank you for your message...		None
2024-01-15T10:31:12.456789	Hello, I need help	[AUTO-REPLY] Thank you for your message...		1
2024-01-15T10:32:00.789012	Hello, I need help	[AUTO-REPLY] Thank you for your message...	Here's how to solve your issue	Discarded
```

## File Structure

```
├── bot.py              # Main bot application
├── config.py           # Configuration and language settings
├── database.py         # Database and TSV file handling
├── requirements.txt    # Python dependencies
├── env_example.txt     # Example environment variables
├── README.md          # This file
├── bot_data.json      # User data storage (created automatically)
└── conversations.tsv  # Conversation storage (created automatically)
```

## Configuration

### Languages

The bot supports three languages:
- **English** (default)
- **Russian** (Русский)
- **Georgian** (ქართული)

Language strings can be modified in `config.py`.

### Semi-Autoreply Mode

- **Enable**: Set `SEMI_AUTOREPLY_MODE=true` in your `.env` file
- **Disable**: Set `SEMI_AUTOREPLY_MODE=false` in your `.env` file

When enabled, the bot will:
1. Generate an automatic reply for each user message
2. Send the autoreply to the support group with approve/discard buttons
3. Wait for approval before sending to the user

### Database

The bot uses:
- **JSON file** (`bot_data.json`) for user preferences and message mappings
- **TSV file** (`conversations.tsv`) for storing all conversations and their outcomes

## Customizing Autoreplies

To customize the autoreply generation, modify the `generate_autoreply()` function in `bot.py`:

```python
def generate_autoreply(question: str) -> str:
    """Generate a placeholder autoreply (replace with actual AI generation)"""
    # Replace this with your AI model or custom logic
    return f"[AUTO-REPLY] Thank you for your message: '{question[:50]}...'. Our team will review this and get back to you shortly."
```

## Security Notes

- Keep your bot token secure and never share it publicly
- The bot only processes messages it receives directly
- User data is stored locally in JSON and TSV formats
- Consider using a proper database for production use

## Troubleshooting

### Common Issues

1. **Bot not responding**: Check that the bot token is correct and the bot is running
2. **Messages not forwarded**: Verify the GROUP_ID is correct and the bot has permission to send messages in the group
3. **Replies not working**: Ensure the bot has permission to read messages in the support group
4. **Autoreply not generating**: Check that `SEMI_AUTOREPLY_MODE=true` in your `.env` file

### Logs

The bot logs all activities. Check the console output for error messages and debugging information.

## Development

To modify the bot:

1. Edit `config.py` to change language strings or add new languages
2. Modify `bot.py` to add new features or change behavior
3. Update `database.py` if you need to store additional user data
4. Customize the `generate_autoreply()` function for your AI model

## License

This project is open source and available under the MIT License.

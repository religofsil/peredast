import os
from dotenv import load_dotenv

load_dotenv()

ENV = os.getenv('ENV', 'dev').lower()

def _env_pick(dev_key: str, prod_key: str, fallback_key: str):
    """Pick value based on ENV with a sensible fallback to single-key envs."""
    if ENV == 'prod':
        return os.getenv(prod_key) or os.getenv(fallback_key)
    # default to dev
    return os.getenv(dev_key) or os.getenv(fallback_key)

# Bot configuration (supports dev/prod separation)
BOT_TOKEN = _env_pick('BOT_TOKEN_DEV', 'BOT_TOKEN_PROD', 'BOT_TOKEN')
GROUP_ID = _env_pick('GROUP_ID_DEV', 'GROUP_ID_PROD', 'GROUP_ID')  # The group where messages will be forwarded
TOPIC_ID = _env_pick('TOPIC_ID_DEV', 'TOPIC_ID_PROD', 'TOPIC_ID')  # The topic ID in the group (optional)
SEMI_AUTOREPLY_MODE = os.getenv('SEMI_AUTOREPLY_MODE', 'true').lower() == 'true'  # Enable semi-autoreply mode

TSV_FILE = _env_pick('TSV_FILE_DEV', 'TSV_FILE_PROD', 'TSV_FILE')  # File to store conversations

# Language options
LANGUAGES = {
    'en': {
        'name': 'English',
        'welcome': 'Welcome! Please choose your language:',
        'language_selected': 'Language set to English',
        'message_forwarded': 'Your message has been forwarded to the support team.',
        'reply_received': 'You received a reply:',
        'error_occurred': 'An error occurred. Please try again.',
        'choose_language': 'Please choose your language:',
        'generated_reply': 'Generated reply:',
        'approve': 'Approve',
        'discard': 'Discard',
        'reply_approved': 'Reply approved and sent to user.',
        'reply_discarded': 'Reply discarded.',
        'manual_reply_sent': 'Manual reply sent to user.',
        'timestamp': 'Timestamp'
    },
    'ru': {
        'name': 'Русский',
        'welcome': 'Добро пожаловать! Пожалуйста, выберите ваш язык:',
        'language_selected': 'Язык установлен на русский',
        'message_forwarded': 'Ваше сообщение было отправлено в службу поддержки.',
        'reply_received': 'Вы получили ответ:',
        'error_occurred': 'Произошла ошибка. Пожалуйста, попробуйте снова.',
        'choose_language': 'Пожалуйста, выберите ваш язык:',
        'generated_reply': 'Сгенерированный ответ:',
        'approve': 'Одобрить',
        'discard': 'Отклонить',
        'reply_approved': 'Ответ одобрен и отправлен пользователю.',
        'reply_discarded': 'Ответ отклонен.',
        'manual_reply_sent': 'Ручной ответ отправлен пользователю.',
        'timestamp': 'Временная метка'
    },
    'ka': {
        'name': 'ქართული',
        'welcome': 'მოგესალმებათ! გთხოვთ აირჩიოთ თქვენი ენა:',
        'language_selected': 'ენა დაყენებულია ქართულად',
        'message_forwarded': 'თქვენი შეტყობინება გადაეცა მხარდაჭერის გუნდს.',
        'reply_received': 'თქვენ მიიღეთ პასუხი:',
        'error_occurred': 'დაფიქსირდა შეცდომა. გთხოვთ სცადოთ თავიდან.',
        'choose_language': 'გთხოვთ აირჩიოთ თქვენი ენა:',
        'generated_reply': 'გენერირებული პასუხი:',
        'approve': 'დამტკიცება',
        'discard': 'უარყოფა',
        'reply_approved': 'პასუხი დამტკიცებული და გაგზავნილია მომხმარებელთან.',
        'reply_discarded': 'პასუხი უარყოფილია.',
        'manual_reply_sent': 'ხელით დაწერილი პასუხი გაგზავნილია მომხმარებელთან.',
        'timestamp': 'დროის ნიშანი'
    }
}

DEFAULT_LANGUAGE = 'en'

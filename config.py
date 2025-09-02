import os
from dotenv import load_dotenv

load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_ID = os.getenv('GROUP_ID')  # The group where messages will be forwarded
TOPIC_ID = os.getenv('TOPIC_ID')  # The topic ID in the group (optional)
SEMI_AUTOREPLY_MODE = os.getenv('SEMI_AUTOREPLY_MODE', 'true').lower() == 'true'  # Enable semi-autoreply mode
TSV_FILE = os.getenv('TSV_FILE', 'conversations.tsv')  # File to store conversations

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

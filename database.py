import json
import os
import csv
from datetime import datetime
from typing import Dict, Optional, Tuple, List
from config import TSV_FILE

class SimpleDatabase:
    def __init__(self, db_file: str = "bot_data.json"):
        self.db_file = db_file
        self.data = self._load_data()
        self._init_tsv_file()
    
    def _load_data(self) -> Dict:
        """Load data from JSON file"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {
            'user_languages': {},
            'message_mappings': {},
            'group_mappings': {},
            'autoreply_mappings': {}  # Store autoreply message mappings
        }
    
    def _save_data(self):
        """Save data to JSON file"""
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def _init_tsv_file(self):
        """Initialize TSV file with headers if it doesn't exist"""
        if not os.path.exists(TSV_FILE):
            with open(TSV_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter='\t')
                writer.writerow(['Timestamp', 'Question', 'Autoreply', 'Manual reply', 'is_approved'])
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format"""
        return datetime.now().isoformat()
    
    def add_conversation(self, question: str, autoreply: str = "", manual_reply: str = "", is_approved: Optional[str] = None, timestamp: Optional[str] = None):
        """Add a conversation entry to TSV file"""
        if timestamp is None:
            timestamp = self._get_timestamp()
        
        with open(TSV_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow([timestamp, question, autoreply, manual_reply, is_approved])
    
    def update_conversation(self, question: str, autoreply: str = "", manual_reply: str = "", is_approved: Optional[str] = None, timestamp: Optional[str] = None):
        """Update the last conversation entry"""
        # Read all rows
        rows = []
        with open(TSV_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            rows = list(reader)
        
        # Update the last row (excluding header)
        if len(rows) > 1:
            if timestamp is None:
                timestamp = self._get_timestamp()
            rows[-1] = [timestamp, question, autoreply, manual_reply, is_approved]
            
            # Write back
            with open(TSV_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter='\t')
                writer.writerows(rows)
    
    def set_user_language(self, user_id: int, language: str):
        """Set user's preferred language"""
        self.data['user_languages'][str(user_id)] = language
        self._save_data()
    
    def get_user_language(self, user_id: int) -> str:
        """Get user's preferred language"""
        return self.data['user_languages'].get(str(user_id), 'en')
    
    def store_message_mapping(self, user_message_id: int, group_message_id: int, user_id: int):
        """Store mapping between user message and group message"""
        self.data['message_mappings'][str(group_message_id)] = {
            'user_message_id': user_message_id,
            'user_id': user_id
        }
        self._save_data()
    
    def get_user_from_group_message(self, group_message_id: int) -> Optional[Tuple[int, int]]:
        """Get user info from group message ID"""
        mapping = self.data['message_mappings'].get(str(group_message_id))
        if mapping:
            return mapping['user_id'], mapping['user_message_id']
        return None
    
    def store_autoreply_mapping(self, autoreply_message_id: int, user_id: int, question: str, autoreply: str):
        """Store mapping for autoreply messages"""
        self.data['autoreply_mappings'][str(autoreply_message_id)] = {
            'user_id': user_id,
            'question': question,
            'autoreply': autoreply
        }
        self._save_data()
    
    def get_autoreply_info(self, autoreply_message_id: int) -> Optional[Dict]:
        """Get autoreply info from message ID"""
        return self.data['autoreply_mappings'].get(str(autoreply_message_id))
    
    def store_group_mapping(self, group_id: int, original_group_id: int):
        """Store mapping for group-to-group replies"""
        self.data['group_mappings'][str(group_id)] = original_group_id
        self._save_data()
    
    def get_original_group(self, group_id: int) -> Optional[int]:
        """Get original group ID from current group ID"""
        return self.data['group_mappings'].get(str(group_id))

# Global database instance
db = SimpleDatabase()

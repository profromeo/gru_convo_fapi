
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class TelegramBotService:
    """Service for interacting with Telegram Bot API."""
    
    def __init__(self):
        # In a real implementation this would hold the bot client/token
        self.logger = logging.getLogger(__name__)

    async def _send_telegram_message(self, chat_id: str, text: str, reply_markup: Optional[Dict] = None, tenant_uid: str = None):
        """
        Placeholder for sending message to Telegram.
        In a real scenario, this would use httpx/aiohttp to call the Telegram API.
        """
        self.logger.info(f"Sending Telegram message to {chat_id}: {text}")
        if reply_markup:
            self.logger.info(f"With replay markup: {reply_markup}")
        # Implementation of actual sending logic would go here
        pass

    async def _handle_convo_response(self, chat_id: str, text: str, full_response: Dict, tenant_uid: str = None):
        """Parse response and send to Telegram with proper buttons"""
        options = full_response.get("metadata", {}).get("telegram_options")
        data_list = full_response.get("metadata", {}).get("data_list")
        list_key = full_response.get("metadata", {}).get("list_key", "id")
        
        # Also check direct keys in case they are merged differently (defensive programming)
        if not options:
             options = full_response.get("telegram_options")
        if not data_list:
             data_list = full_response.get("data_list")

        keyboard = None

        if options and isinstance(options, list):
            keyboard = self._build_inline_keyboard(options)
        elif data_list and isinstance(data_list, list):
            dynamic_options = []
            display_key = full_response.get("metadata", {}).get("display_key", "label")
            
            for item in data_list:
                if isinstance(item, dict):
                    # Use configured key, fallback to common defaults
                    label = item.get(display_key) or item.get("display") or item.get("label") or str(item)
                    value = item.get(list_key) or item.get("value") or item.get("id") or str(item)
                    dynamic_options.append({"label": label, "value": value})
                else:
                    dynamic_options.append({"label": str(item), "value": str(item)})
            
            keyboard = self._build_inline_keyboard(dynamic_options)

        await self._send_telegram_message(chat_id, text, reply_markup=keyboard, tenant_uid=tenant_uid)

    def _build_inline_keyboard(self, options: List[Dict]) -> Dict:
        """Helper to build Telegram Inline Keyboard"""
        inline_keyboard = []
        for opt in options:
            label = opt.get("label", "Option")
            value = opt.get("value", "val")
            inline_keyboard.append([{"text": label, "callback_data": str(value)}])
        
        return {"inline_keyboard": inline_keyboard}

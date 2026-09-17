"""
Telegram Notifier service for sending job digest messages.
Handles HTTP communication with the Telegram Bot API safely and resiliently.
"""

import logging
from typing import Optional
import requests

from app.config import Config

logger = logging.getLogger("app.services.telegram_notifier")


class TelegramNotifier:
    """
    Service for dispatching text notifications via Telegram Bot API.
    """

    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
        enabled: bool = True,
        timeout: float = 10.0,
        config: Optional[Config] = None,
    ):
        """
        Initializes TelegramNotifier with credentials or Config object.
        """
        if config:
            self.bot_token = config.telegram_bot_token
            self.chat_id = config.telegram_chat_id
            self.enabled = config.telegram_enabled
        else:
            self.bot_token = bot_token.strip()
            self.chat_id = str(chat_id).strip()
            self.enabled = enabled and bool(self.bot_token and self.chat_id)

        self.timeout = timeout
        self.api_url = (
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            if self.bot_token
            else ""
        )

    def is_configured(self) -> bool:
        """
        Returns True if Telegram notifications are enabled and valid credentials exist.
        """
        return bool(self.enabled and self.bot_token and self.chat_id)

    def _mask_token(self, text: str) -> str:
        """
        Redacts/masks the Telegram bot token from log strings or exception tracebacks.
        """
        if not self.bot_token:
            return text
        return text.replace(self.bot_token, "[REDACTED_BOT_TOKEN]")

    def send_message(self, text: str) -> bool:
        """
        Sends a single text message via Telegram Bot API.

        Args:
            text: Message body to send.

        Returns:
            bool: True if Telegram API returned success (200 OK with ok=True), False otherwise.
        """
        if not self.is_configured():
            logger.warning(
                "Telegram notifier is disabled or missing required configuration (bot token / chat ID)."
            )
            return False

        if not text or not text.strip():
            logger.warning("Attempted to send an empty message to Telegram.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    logger.info("Telegram message delivered successfully.")
                    return True
                else:
                    description = self._mask_token(
                        data.get("description", "Unknown error")
                    )
                    logger.error(
                        "Telegram API returned error status: %s", description
                    )
                    return False
            else:
                masked_response = self._mask_token(response.text)
                logger.error(
                    "Telegram API returned HTTP status %d: %s",
                    response.status_code,
                    masked_response,
                )
                return False

        except requests.exceptions.Timeout:
            logger.error("Telegram API request timed out after %.1f seconds.", self.timeout)
            return False
        except requests.exceptions.RequestException as e:
            masked_error = self._mask_token(str(e))
            logger.error("Failed to connect to Telegram API: %s", masked_error)
            return False
        except Exception as e:
            masked_error = self._mask_token(str(e))
            logger.error("Unexpected error during Telegram message delivery: %s", masked_error)
            return False

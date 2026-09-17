"""
Unit tests for TelegramNotifier service.
"""

import logging
from unittest.mock import MagicMock, patch
import pytest
import requests

from app.config import Config
from app.services.telegram_notifier import TelegramNotifier


def test_telegram_notifier_configuration_valid():
    """Test TelegramNotifier when credentials are valid."""
    config = Config(
        adzuna_app_id="app_id",
        adzuna_app_key="app_key",
        telegram_bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        telegram_chat_id="987654321",
        telegram_enabled=True,
    )
    notifier = TelegramNotifier(config=config)
    assert notifier.is_configured() is True
    assert notifier.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert notifier.chat_id == "987654321"


def test_telegram_notifier_missing_token():
    """Test TelegramNotifier when bot token is missing."""
    notifier = TelegramNotifier(bot_token="", chat_id="123456", enabled=True)
    assert notifier.is_configured() is False


def test_telegram_notifier_missing_chat_id():
    """Test TelegramNotifier when chat ID is missing."""
    notifier = TelegramNotifier(
        bot_token="123456:ABC-DEF", chat_id="", enabled=True
    )
    assert notifier.is_configured() is False


def test_telegram_notifier_disabled():
    """Test TelegramNotifier when disabled mode is explicit."""
    notifier = TelegramNotifier(
        bot_token="123456:ABC-DEF", chat_id="987654321", enabled=False
    )
    assert notifier.is_configured() is False
    assert notifier.send_message("Test message") is False


@patch("requests.post")
def test_send_message_success(mock_post):
    """Test successful message delivery via Telegram API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {"message_id": 1}}
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(
        bot_token="TEST_BOT_TOKEN", chat_id="12345", enabled=True
    )
    result = notifier.send_message("Hello World")

    assert result is True
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert "https://api.telegram.org/botTEST_BOT_TOKEN/sendMessage" in args[0]
    assert kwargs["json"] == {
        "chat_id": "12345",
        "text": "Hello World",
        "disable_web_page_preview": True,
    }


@patch("requests.post")
def test_send_message_http_error(mock_post):
    """Test handling of Telegram API returning HTTP status error (e.g., 400 Bad Request)."""
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = '{"ok": false, "error_code": 400, "description": "Bad Request: chat not found"}'
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(
        bot_token="TEST_BOT_TOKEN", chat_id="invalid_id", enabled=True
    )
    result = notifier.send_message("Test message")

    assert result is False


@patch("requests.post")
def test_send_message_timeout(mock_post):
    """Test handling of request timeout."""
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

    notifier = TelegramNotifier(
        bot_token="TEST_BOT_TOKEN", chat_id="12345", enabled=True, timeout=5.0
    )
    result = notifier.send_message("Test message")

    assert result is False


@patch("requests.post")
def test_send_message_network_failure(mock_post):
    """Test handling of network failure (RequestException)."""
    mock_post.side_effect = requests.exceptions.ConnectionError("Failed to connect")

    notifier = TelegramNotifier(
        bot_token="TEST_BOT_TOKEN", chat_id="12345", enabled=True
    )
    result = notifier.send_message("Test message")

    assert result is False


@patch("requests.post")
def test_send_message_malformed_json_response(mock_post):
    """Test handling of malformed API response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": False, "description": "Invalid payload"}
    mock_post.return_value = mock_response

    notifier = TelegramNotifier(
        bot_token="TEST_BOT_TOKEN", chat_id="12345", enabled=True
    )
    result = notifier.send_message("Test message")

    assert result is False


@patch("requests.post")
def test_token_never_logged_on_error(mock_post, caplog):
    """Test that Telegram bot token is masked/redacted and never appears in logs upon error."""
    secret_token = "SECRET_123456789_TOKEN"
    mock_post.side_effect = requests.exceptions.RequestException(
        f"Error with URL https://api.telegram.org/bot{secret_token}/sendMessage"
    )

    notifier = TelegramNotifier(
        bot_token=secret_token, chat_id="12345", enabled=True
    )

    with caplog.at_level(logging.ERROR):
        result = notifier.send_message("Test message")

    assert result is False
    log_text = caplog.text
    assert secret_token not in log_text
    assert "[REDACTED_BOT_TOKEN]" in log_text

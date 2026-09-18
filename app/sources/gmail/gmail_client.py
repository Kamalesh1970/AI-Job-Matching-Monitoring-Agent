"""
Gmail API client wrapper handling OAuth authentication, message searching,
payload retrieval, and base64url MIME body decoding.
Uses strictly the read-only scope: https://www.googleapis.com/auth/gmail.readonly
"""

import base64
import logging
import os
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build

from app.sources.gmail.models import ParsedEmailData

logger = logging.getLogger(__name__)

READONLY_SCOPE = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailAPIClient:
    """
    Client interface for accessing Gmail messages via Gmail API (read-only scope).
    """

    def __init__(
        self,
        credentials_path: str = "credentials.json",
        token_path: str = "token.json",
        scopes: Optional[List[str]] = None,
    ):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.scopes = scopes or READONLY_SCOPE
        self._service: Optional[Resource] = None
        self._creds: Optional[Credentials] = None

    def authenticate(self) -> Credentials:
        """
        Loads cached token.json or initiates OAuth 2.0 flow using credentials.json.
        Refreshes expired credentials if refresh token is available.

        Raises:
            FileNotFoundError: If credentials.json is missing when new auth is needed.
            Exception: On OAuth authentication failure.
        """
        creds = None

        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
            except Exception as e:
                logger.warning("Failed to load credentials from token path '%s': %s", self.token_path, str(e))

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    logger.info("Refreshing expired Gmail OAuth token...")
                    creds.refresh(Request())
                except Exception as e:
                    logger.warning("Failed to refresh Gmail OAuth token: %s", str(e))
                    creds = None

            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Gmail OAuth client secrets file not found at '{self.credentials_path}'. "
                        "Please download credentials.json from Google Cloud Console."
                    )

                logger.info("Initiating Desktop OAuth flow for Gmail API read-only scope...")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.scopes)
                creds = flow.run_local_server(port=0)

                # Persist token locally for subsequent executions
                token_dir = os.path.dirname(self.token_path)
                if token_dir:
                    os.makedirs(token_dir, exist_ok=True)
                with open(self.token_path, "w", encoding="utf-8") as token_file:
                    token_file.write(creds.to_json())
                logger.info("Saved new Gmail OAuth token to '%s'.", self.token_path)

        self._creds = creds
        return creds

    def get_service(self) -> Resource:
        """
        Builds and returns the Gmail API Resource service object.
        """
        if self._service is None:
            creds = self.authenticate()
            self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def search_messages(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Searches Gmail messages matching the specified query string.

        Args:
            query: Gmail search expression (e.g. 'from:(linkedin.com) newer_than:2d').
            max_results: Maximum number of messages to return.

        Returns:
            List[Dict[str, Any]]: List of message dictionaries containing 'id' and 'threadId'.
        """
        try:
            service = self.get_service()
            logger.info("Searching Gmail messages with query='%s' (max_results=%d)...", query, max_results)
            response = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
            messages = response.get("messages", [])
            logger.info("Gmail search found %d message(s).", len(messages))
            return messages
        except Exception as e:
            logger.error("Gmail search failed for query='%s': %s", query, str(e))
            raise

    def get_message_detail(self, message_id: str) -> Dict[str, Any]:
        """
        Fetches full message details for a message ID.
        """
        try:
            service = self.get_service()
            msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
            return msg
        except Exception as e:
            logger.error("Failed to fetch detail for Gmail message ID '%s': %s", message_id, str(e))
            raise

    @staticmethod
    def _decode_body_data(data_str: str) -> str:
        """Decodes base64url encoded string into UTF-8 text."""
        if not data_str:
            return ""
        try:
            padded = data_str.replace("-", "+").replace("_", "/")
            padding_len = len(padded) % 4
            if padding_len:
                padded += "=" * (4 - padding_len)
            decoded_bytes = base64.b64decode(padded)
            return decoded_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            logger.warning("Error decoding base64url email body: %s", str(e))
            return ""

    def decode_message_payload(self, message_dict: Dict[str, Any]) -> ParsedEmailData:
        """
        Parses full raw Gmail message JSON response into a ParsedEmailData dataclass.
        Extracts headers (Subject, From, Date) and decodes text/plain and text/html parts.
        """
        msg_id = message_dict.get("id", "")
        payload = message_dict.get("payload", {})
        headers = payload.get("headers", [])

        subject = ""
        sender = ""
        received_at = ""

        for header in headers:
            name = header.get("name", "").lower()
            val = header.get("value", "")
            if name == "subject":
                subject = val
            elif name == "from":
                sender = val
            elif name in ("date", "received") and not received_at:
                received_at = val

        plain_text = ""
        html_content = ""

        def extract_parts(part_data: Dict[str, Any]):
            nonlocal plain_text, html_content
            mime_type = part_data.get("mimeType", "").lower()
            body_data = part_data.get("body", {}).get("data", "")

            if mime_type == "text/plain" and not plain_text and body_data:
                plain_text = self._decode_body_data(body_data)
            elif mime_type == "text/html" and not html_content and body_data:
                html_content = self._decode_body_data(body_data)

            for subpart in part_data.get("parts", []):
                extract_parts(subpart)

        extract_parts(payload)

        # Fallback if top-level body has data directly
        if not plain_text and not html_content:
            body_data = payload.get("body", {}).get("data", "")
            if body_data:
                decoded = self._decode_body_data(body_data)
                if "<html" in decoded.lower() or "<div" in decoded.lower():
                    html_content = decoded
                else:
                    plain_text = decoded

        return ParsedEmailData(
            message_id=msg_id,
            received_at=received_at,
            subject=subject,
            sender=sender,
            plain_text=plain_text,
            html_content=html_content,
        )

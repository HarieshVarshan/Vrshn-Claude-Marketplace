"""
Email client for IMAP/SMTP operations.

Provides:
- IMAP: list, get, search, delete, move emails, list folders, download attachments
- SMTP: send emails with optional attachments

Uses Python stdlib (imaplib, smtplib, email) - no external email libraries needed.
"""

import base64
import email
import imaplib
import os
import re
import smtplib
from datetime import datetime
from email import policy
from email.header import decode_header
from email.message import EmailMessage
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, parseaddr, parsedate_to_datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv


class EmailConfig:
    """Configuration loader for email credentials and server settings."""

    def __init__(self, config_path: Optional[str] = None):
        # Primary: common atlassian config
        atlassian_config = os.path.expanduser('~/.config/atlassian/.env')
        # Override: service-specific config (optional)
        service_config = config_path or os.environ.get(
            'EMAIL_CONFIG',
            os.path.expanduser('~/.config/email-mcp/.env')
        )

        # Load atlassian config first, then override with service-specific if exists
        if os.path.exists(atlassian_config):
            load_dotenv(atlassian_config)
        if os.path.exists(service_config):
            load_dotenv(service_config, override=True)

        # Authentication
        self.email_user = os.environ.get('EMAIL_USER', '')
        self.email_password = os.environ.get('EMAIL_PASSWORD', '')

        # IMAP settings
        self.imap_host = os.environ.get('IMAP_HOST', '')
        self.imap_port = int(os.environ.get('IMAP_PORT', '993'))
        self.imap_secure = os.environ.get('IMAP_SECURE', 'true').lower() == 'true'

        # SMTP settings
        self.smtp_host = os.environ.get('SMTP_HOST', '')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        self.smtp_secure = os.environ.get('SMTP_SECURE', 'true').lower() == 'true'
        self.smtp_starttls = os.environ.get('SMTP_STARTTLS', 'true').lower() == 'true'


def _decode_header_value(value: str) -> str:
    """Decode an RFC 2047 encoded header value."""
    if not value:
        return ''
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or 'utf-8', errors='replace'))
        else:
            decoded.append(part)
    return ''.join(decoded)


def _parse_address_list(header_value: str) -> List[Dict[str, str]]:
    """Parse a comma-separated address header into a list of {name, address} dicts."""
    if not header_value:
        return []
    result = []
    # Split by comma, but be careful of commas inside quoted strings
    raw = _decode_header_value(header_value)
    # email.utils.getaddresses handles this properly
    from email.utils import getaddresses
    for name, addr in getaddresses([raw]):
        result.append({'name': name, 'address': addr})
    return result


def _parse_email_message(msg: email.message.Message, uid: int) -> Dict[str, Any]:
    """Parse an email.message.Message into a structured dict."""
    # Headers
    subject = _decode_header_value(msg.get('Subject', ''))
    from_header = _decode_header_value(msg.get('From', ''))
    to_header = _decode_header_value(msg.get('To', ''))
    cc_header = _decode_header_value(msg.get('Cc', ''))
    date_header = msg.get('Date', '')
    message_id = msg.get('Message-ID', '')

    # Parse date
    date_str = ''
    if date_header:
        try:
            dt = parsedate_to_datetime(date_header)
            date_str = dt.isoformat()
        except Exception:
            date_str = date_header

    # Body
    text_body = ''
    html_body = ''
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get('Content-Disposition', ''))
            if 'attachment' in disposition:
                continue
            if content_type == 'text/plain':
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    text_body = payload.decode(charset, errors='replace')
            elif content_type == 'text/html':
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    html_body = payload.decode(charset, errors='replace')
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or 'utf-8'
            content_type = msg.get_content_type()
            body_text = payload.decode(charset, errors='replace')
            if content_type == 'text/html':
                html_body = body_text
            else:
                text_body = body_text

    # Attachments metadata
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            disposition = str(part.get('Content-Disposition', ''))
            if 'attachment' in disposition or (
                part.get_content_maintype() not in ('text', 'multipart')
                and part.get_content_disposition() == 'attachment'
            ):
                filename = part.get_filename()
                if filename:
                    filename = _decode_header_value(filename)
                    size = len(part.get_payload(decode=True) or b'')
                    attachments.append({
                        'filename': filename,
                        'contentType': part.get_content_type(),
                        'size': size,
                    })

    return {
        'uid': uid,
        'messageId': message_id,
        'subject': subject,
        'from': _parse_address_list(from_header) if from_header else [],
        'to': _parse_address_list(to_header) if to_header else [],
        'cc': _parse_address_list(cc_header) if cc_header else [],
        'date': date_str,
        'body': text_body or html_body,
        'bodyType': 'html' if html_body and not text_body else 'text',
        'attachments': attachments,
    }


def _parse_email_summary(msg: email.message.Message, uid: int, flags: str = '') -> Dict[str, Any]:
    """Parse an email into a lightweight summary (no body)."""
    subject = _decode_header_value(msg.get('Subject', ''))
    from_header = _decode_header_value(msg.get('From', ''))
    to_header = _decode_header_value(msg.get('To', ''))
    date_header = msg.get('Date', '')
    message_id = msg.get('Message-ID', '')

    date_str = ''
    if date_header:
        try:
            dt = parsedate_to_datetime(date_header)
            date_str = dt.isoformat()
        except Exception:
            date_str = date_header

    # Parse flags
    flag_list = []
    if flags:
        flag_list = re.findall(r'\\(\w+)', flags)

    # Count attachments
    attachment_count = 0
    if msg.is_multipart():
        for part in msg.walk():
            disposition = str(part.get('Content-Disposition', ''))
            if 'attachment' in disposition:
                attachment_count += 1

    return {
        'uid': uid,
        'messageId': message_id,
        'subject': subject,
        'from': _parse_address_list(from_header),
        'to': _parse_address_list(to_header),
        'date': date_str,
        'flags': flag_list,
        'attachmentCount': attachment_count,
    }


class EmailClient:
    """Client for email operations via IMAP and SMTP."""

    def __init__(self, config: EmailConfig):
        self.config = config

    # ==================== IMAP Helpers ====================

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        """Create and authenticate an IMAP connection."""
        if self.config.imap_secure:
            conn = imaplib.IMAP4_SSL(self.config.imap_host, self.config.imap_port)
        else:
            conn = imaplib.IMAP4(self.config.imap_host, self.config.imap_port)
        conn.login(self.config.email_user, self.config.email_password)
        return conn

    def _fetch_message(self, conn: imaplib.IMAP4_SSL, uid: int,
                       parts: str = '(RFC822)') -> email.message.Message:
        """Fetch a single message by UID."""
        status, data = conn.uid('fetch', str(uid), parts)
        if status != 'OK' or not data or data[0] is None:
            raise ValueError(f"Email with UID {uid} not found")
        raw = data[0][1] if isinstance(data[0], tuple) else data[0]
        return email.message_from_bytes(raw)

    # ==================== Email Operations ====================

    def send_email(self, to: List[str], subject: str, body: str,
                   cc: List[str] = None, bcc: List[str] = None,
                   attachments: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Send an email via SMTP.

        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body (plain text or HTML)
            cc: Optional CC recipients
            bcc: Optional BCC recipients
            attachments: Optional list of {'filename': str, 'path': str}
        """
        msg = MIMEMultipart()
        msg['From'] = self.config.email_user
        msg['To'] = ', '.join(to)
        msg['Subject'] = subject
        msg['Date'] = formatdate(localtime=True)

        if cc:
            msg['Cc'] = ', '.join(cc)

        # Detect HTML
        if '<html' in body.lower() or '<p>' in body.lower() or '<br' in body.lower():
            msg.attach(MIMEText(body, 'html', 'utf-8'))
        else:
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Attachments
        if attachments:
            for att in attachments:
                filepath = os.path.expanduser(att['path'])
                filename = att.get('filename', os.path.basename(filepath))
                with open(filepath, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=filename)
                part['Content-Disposition'] = f'attachment; filename="{filename}"'
                msg.attach(part)

        # All recipients for SMTP envelope
        all_recipients = list(to)
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)

        # Connect and send
        if self.config.smtp_secure:
            server = smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port)
        else:
            server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
            if self.config.smtp_starttls:
                server.ehlo()
                server.starttls()
                server.ehlo()

        try:
            # Some SMTP servers (e.g. internal relays) don't require auth
            if self.config.email_password:
                server.login(self.config.email_user, self.config.email_password)
            server.sendmail(self.config.email_user, all_recipients, msg.as_string())
        finally:
            server.quit()

        return {
            'status': 'sent',
            'to': to,
            'cc': cc or [],
            'subject': subject,
            'attachmentCount': len(attachments) if attachments else 0,
        }

    def get_email(self, uid: int, folder: str = 'INBOX',
                  mark_seen: bool = False) -> Dict[str, Any]:
        """Get full email details by UID."""
        conn = self._connect_imap()
        try:
            conn.select(folder, readonly=not mark_seen)
            msg = self._fetch_message(conn, uid)
            result = _parse_email_message(msg, uid)
            if mark_seen:
                conn.uid('store', str(uid), '+FLAGS', '(\\Seen)')
            return result
        finally:
            conn.logout()

    def list_emails(self, folder: str = 'INBOX', limit: int = 50,
                    offset: int = 0, unread_only: bool = False) -> Dict[str, Any]:
        """List emails from a folder."""
        conn = self._connect_imap()
        try:
            conn.select(folder, readonly=True)

            # Search
            if unread_only:
                status, data = conn.uid('search', None, 'UNSEEN')
            else:
                status, data = conn.uid('search', None, 'ALL')

            if status != 'OK':
                return {'emails': [], 'total': 0, 'folder': folder}

            uids = data[0].split() if data[0] else []
            # Reverse to get newest first
            uids = list(reversed(uids))
            total = len(uids)

            # Apply pagination
            page_uids = uids[offset:offset + limit]

            emails = []
            if page_uids:
                uid_str = b','.join(page_uids)
                status, data = conn.uid('fetch', uid_str, '(RFC822 FLAGS)')
                if status == 'OK' and data:
                    # data comes as pairs of (envelope, body) + closing byte
                    i = 0
                    while i < len(data):
                        item = data[i]
                        if isinstance(item, tuple) and len(item) == 2:
                            # Parse UID and flags from response
                            meta = item[0].decode('utf-8', errors='replace')
                            raw_bytes = item[1]
                            uid_match = re.search(r'UID (\d+)', meta)
                            flags_match = re.search(r'FLAGS \(([^)]*)\)', meta)
                            uid_val = int(uid_match.group(1)) if uid_match else 0
                            flags_str = flags_match.group(1) if flags_match else ''
                            msg = email.message_from_bytes(raw_bytes)
                            emails.append(_parse_email_summary(msg, uid_val, flags_str))
                        i += 1

            return {
                'emails': emails,
                'total': total,
                'folder': folder,
                'offset': offset,
                'limit': limit,
            }
        finally:
            conn.logout()

    def search_emails(self, folder: str = 'INBOX', query: str = None,
                      from_addr: str = None, subject: str = None,
                      date_from: str = None, date_to: str = None,
                      limit: int = 50) -> Dict[str, Any]:
        """Search emails by criteria using IMAP SEARCH."""
        conn = self._connect_imap()
        try:
            conn.select(folder, readonly=True)

            # Build IMAP search criteria
            criteria = []
            if query:
                # IMAP TEXT searches subject + body
                criteria.append(f'TEXT "{query}"')
            if from_addr:
                criteria.append(f'FROM "{from_addr}"')
            if subject:
                criteria.append(f'SUBJECT "{subject}"')
            if date_from:
                # Convert YYYY-MM-DD to DD-Mon-YYYY
                try:
                    dt = datetime.strptime(date_from, '%Y-%m-%d')
                    criteria.append(f'SINCE {dt.strftime("%d-%b-%Y")}')
                except ValueError:
                    pass
            if date_to:
                try:
                    dt = datetime.strptime(date_to, '%Y-%m-%d')
                    criteria.append(f'BEFORE {dt.strftime("%d-%b-%Y")}')
                except ValueError:
                    pass

            if not criteria:
                criteria.append('ALL')

            search_str = ' '.join(criteria)
            status, data = conn.uid('search', None, search_str)

            if status != 'OK':
                return {'emails': [], 'total': 0, 'folder': folder}

            uids = data[0].split() if data[0] else []
            uids = list(reversed(uids))  # Newest first
            total = len(uids)
            page_uids = uids[:limit]

            emails = []
            if page_uids:
                uid_str = b','.join(page_uids)
                status, data = conn.uid('fetch', uid_str, '(RFC822 FLAGS)')
                if status == 'OK' and data:
                    i = 0
                    while i < len(data):
                        item = data[i]
                        if isinstance(item, tuple) and len(item) == 2:
                            meta = item[0].decode('utf-8', errors='replace')
                            raw_bytes = item[1]
                            uid_match = re.search(r'UID (\d+)', meta)
                            flags_match = re.search(r'FLAGS \(([^)]*)\)', meta)
                            uid_val = int(uid_match.group(1)) if uid_match else 0
                            flags_str = flags_match.group(1) if flags_match else ''
                            msg = email.message_from_bytes(raw_bytes)
                            emails.append(_parse_email_summary(msg, uid_val, flags_str))
                        i += 1

            return {
                'emails': emails,
                'total': total,
                'folder': folder,
                'query': search_str,
            }
        finally:
            conn.logout()

    def delete_emails(self, ids: List[int], folder: str = 'INBOX',
                      permanent: bool = False) -> Dict[str, Any]:
        """Delete emails by UID.

        Args:
            ids: List of IMAP UIDs
            folder: Source folder
            permanent: If True, permanently delete. If False, move to Trash.
        """
        conn = self._connect_imap()
        try:
            conn.select(folder)
            uid_str = ','.join(str(uid) for uid in ids)

            if permanent:
                conn.uid('store', uid_str, '+FLAGS', '(\\Deleted)')
                conn.expunge()
            else:
                # Try common Trash folder names
                trash_folders = ['Trash', '[Gmail]/Trash', 'Deleted Items',
                                 'Deleted Messages', 'INBOX.Trash']
                trash_folder = None
                status, folders = conn.list()
                if status == 'OK':
                    for f in folders:
                        decoded = f.decode('utf-8', errors='replace')
                        for tf in trash_folders:
                            if tf.lower() in decoded.lower():
                                # Extract folder name from IMAP LIST response
                                match = re.search(r'"[^"]*" (.+)$', decoded)
                                if match:
                                    trash_folder = match.group(1).strip('"').strip()
                                    break
                        if trash_folder:
                            break

                if trash_folder:
                    conn.uid('copy', uid_str, trash_folder)
                    conn.uid('store', uid_str, '+FLAGS', '(\\Deleted)')
                    conn.expunge()
                else:
                    # Fallback: mark as deleted
                    conn.uid('store', uid_str, '+FLAGS', '(\\Deleted)')
                    conn.expunge()

            return {
                'status': 'deleted',
                'ids': ids,
                'permanent': permanent,
                'folder': folder,
            }
        finally:
            conn.logout()

    def move_emails(self, ids: List[int], target_folder: str,
                    source_folder: str = 'INBOX') -> Dict[str, Any]:
        """Move emails to a different folder."""
        conn = self._connect_imap()
        try:
            conn.select(source_folder)
            uid_str = ','.join(str(uid) for uid in ids)

            # Copy to target, then delete from source
            status, _ = conn.uid('copy', uid_str, target_folder)
            if status != 'OK':
                raise ValueError(f"Failed to copy emails to '{target_folder}'. "
                                 "Verify the folder name with email_get_folders.")
            conn.uid('store', uid_str, '+FLAGS', '(\\Deleted)')
            conn.expunge()

            return {
                'status': 'moved',
                'ids': ids,
                'sourceFolder': source_folder,
                'targetFolder': target_folder,
            }
        finally:
            conn.logout()

    def get_folders(self) -> List[Dict[str, Any]]:
        """List available IMAP folders."""
        conn = self._connect_imap()
        try:
            status, data = conn.list()
            if status != 'OK':
                return []

            folders = []
            for item in data:
                decoded = item.decode('utf-8', errors='replace')
                # Parse IMAP LIST response: (\\flags) "delimiter" "name"
                match = re.match(r'\(([^)]*)\)\s+"([^"]*)"\s+(.+)$', decoded)
                if match:
                    flags = match.group(1)
                    delimiter = match.group(2)
                    name = match.group(3).strip('"').strip()
                    folders.append({
                        'name': name,
                        'delimiter': delimiter,
                        'flags': flags,
                    })
            return folders
        finally:
            conn.logout()

    def download_attachment(self, uid: int, folder: str = 'INBOX',
                            filename: str = None,
                            save_path: str = None) -> List[Dict[str, Any]]:
        """Download attachment(s) from an email.

        Args:
            uid: IMAP UID
            folder: Folder name
            filename: Specific filename to download (None for all)
            save_path: Directory to save to (None to return base64 content)

        Returns:
            List of attachment dicts with filename, size, and either path or content.
        """
        conn = self._connect_imap()
        try:
            conn.select(folder, readonly=True)
            msg = self._fetch_message(conn, uid)

            results = []
            if not msg.is_multipart():
                return results

            for part in msg.walk():
                disposition = str(part.get('Content-Disposition', ''))
                if 'attachment' not in disposition:
                    # Also check for non-text parts without explicit disposition
                    if part.get_content_maintype() in ('text', 'multipart'):
                        continue
                    if part.get_content_disposition() != 'attachment':
                        continue

                att_filename = part.get_filename()
                if not att_filename:
                    continue
                att_filename = _decode_header_value(att_filename)

                if filename and att_filename != filename:
                    continue

                payload = part.get_payload(decode=True)
                if payload is None:
                    continue

                att_info = {
                    'filename': att_filename,
                    'contentType': part.get_content_type(),
                    'size': len(payload),
                }

                if save_path:
                    save_dir = os.path.expanduser(save_path)
                    os.makedirs(save_dir, exist_ok=True)
                    filepath = os.path.join(save_dir, att_filename)
                    with open(filepath, 'wb') as f:
                        f.write(payload)
                    att_info['path'] = filepath
                else:
                    att_info['content'] = base64.b64encode(payload).decode('ascii')

                results.append(att_info)

            return results
        finally:
            conn.logout()


# Singleton instances
_config: Optional[EmailConfig] = None
_client: Optional[EmailClient] = None


def get_config() -> EmailConfig:
    """Get or create the global email config."""
    global _config
    if _config is None:
        _config = EmailConfig()
    return _config


def get_email_client() -> EmailClient:
    """Get or create the email client."""
    global _client
    if _client is None:
        _client = EmailClient(get_config())
    return _client

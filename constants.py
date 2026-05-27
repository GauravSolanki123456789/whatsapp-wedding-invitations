"""Shared constants used across the WhatsApp Invitations app."""

APP_TITLE = "WhatsApp Wedding Invitations"
APP_ICON = "💒"

# Data column name — used in Excel parsing, DataFrames, and the data editor
MOBILE_NUMBER_COLUMN = "mobile_number"

# Session state keys
SESSION_GUEST_LIST = "guest_list"
SESSION_MESSAGE = "message"
SESSION_COUNTRY_CODE = "country_code"
SESSION_SEND_LOG = "send_log"
SESSION_FILE_UPLOAD_KEY = "file_uploader_key"
SESSION_ATTACHMENT_PATH = "attachment_path"
SESSION_ATTACHMENT_NAME = "attachment_name"
SESSION_COMPOSE_LOADED = "compose_loaded"
SESSION_DELAY_MIN = "delay_min_seconds"
SESSION_DELAY_MAX = "delay_max_seconds"
SESSION_SEND_MODE = "send_mode"
SESSION_MANUAL_SENT = "manual_sent_numbers"
SESSION_GUEST_LIST_LOADED = "guest_list_loaded"

# Send modes
SEND_MODE_QUICK = "quick_send"
SEND_MODE_AUTO = "auto_send"

# Send log status values
STATUS_SENT = "Sent"
STATUS_FAILED = "Failed"
STATUS_PENDING = "Pending"

# WhatsApp link bases (used in wa_links.py)
WA_ME_BASE = "https://wa.me"
WHATSAPP_WEB_BASE = "https://web.whatsapp.com/send"

# Persistence paths
DATA_FOLDER = "data"
GUEST_LIST_FILE = "data/guest_list.json"
LAST_COMPOSE_FILE = "data/last_compose.json"
MANUAL_SEND_LOG_FILE = "data/manual_send_log.json"
LAST_ATTACHMENT_DIR = "attachments/last_compose"

# Attachment settings
ATTACHMENT_FOLDER = "attachments"
ALLOWED_ATTACHMENT_TYPES = [
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "mp4",
    "mov",
    "avi",
    "mkv",
    "webm",
    "3gp",
    "m4v",
]
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
DOCUMENT_EXTENSIONS = {".pdf"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp", ".m4v"}

# WhatsApp sending defaults
DELAY_MIN_SECONDS = 15
DELAY_MAX_SECONDS = 30
WHATSAPP_PAGE_WAIT_SECONDS = 25
WHATSAPP_TAB_CLOSE_SECONDS = 4
WHATSAPP_AFTER_PASTE_SECONDS = 3
WHATSAPP_AFTER_ATTACH_SECONDS = 6
WHATSAPP_AFTER_VIDEO_ATTACH_SECONDS = 20
WHATSAPP_UPLOAD_SECONDS_PER_MB = 3
WHATSAPP_MAX_UPLOAD_WAIT_SECONDS = 180

# WhatsApp Web file-size limits (MB)
WHATSAPP_MAX_VIDEO_MB = 100
WHATSAPP_MAX_DOCUMENT_MB = 100
WHATSAPP_MAX_IMAGE_MB = 16

# Default country code (India); change in sidebar if needed
DEFAULT_COUNTRY_CODE = "+91"

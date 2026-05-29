"""Shared constants used across the WhatsApp Invitations app."""

APP_TITLE = "WhatsApp Wedding Invitations"
APP_ICON = "💒"
APP_TAGLINE = "Families · lists · invites · gift QR · scan"

# Data column names — consistent across Excel, DB, UI, and reports
MOBILE_NUMBER_COLUMN = "mobile_number"
GUEST_NAME_COLUMN = "guest_name"
GIFT_QUANTITY_COLUMN = "gift_quantity"

# QR payload prefix (encoded in guest QR images)
QR_TOKEN_PREFIX = "waiv:"

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
SESSION_GROUP_NAME = "group_name"
SESSION_GROUP_MODE = "group_mode"
SESSION_GROUP_LOG = "group_log"
SESSION_GUIDED_COOLDOWN_UNTIL = "guided_cooldown_until"
SESSION_ATTACHMENT_BYTES = "attachment_bytes"
SESSION_ACTIVE_FAMILY_ID = "active_family_id"
SESSION_ACTIVE_GUEST_LIST_ID = "active_guest_list_id"
SESSION_ACTIVE_FUNCTION_ID = "active_function_id"
SESSION_LAST_SCAN_TOKEN = "last_scan_token"
SESSION_SCAN_LOOKUP_GUEST = "scan_lookup_guest"
SESSION_LAST_PROCESSED_SCAN_PAYLOAD = "last_processed_scan_payload"
SESSION_SCAN_PHOTO_KEY = "scan_photo_key"
SESSION_SCAN_UPLOAD_KEY = "scan_upload_key"
SESSION_SCAN_PASTE_KEY = "scan_paste_key"
SESSION_SCAN_COMPONENT_KEY = "scan_component_key"
SESSION_LAST_COMPONENT_SCAN = "last_component_scan"
SESSION_USE_NAMED_LIST = "use_named_guest_list"
SESSION_SCANNER_STAFF_NAME = "scanner_staff_name"

# URL query param set by live QR scanner (auto guest lookup)
QUERY_PARAM_SCAN_TOKEN = "scan_token"

# Send modes
SEND_MODE_QUICK = "quick_send"
SEND_MODE_GUIDED = "guided_send"
SEND_MODE_AUTO = "auto_send"

# Group creation modes (same pattern as send modes)
GROUP_MODE_QUICK = "quick_group"
GROUP_MODE_AUTO = "auto_group"

# WhatsApp group limits
WHATSAPP_MAX_GROUP_PARTICIPANTS = 256
DEFAULT_GROUP_NAME = "Wedding Guests"
GROUP_CONTACT_NAME_PREFIX = "Wedding Guest"

# Send log status values
STATUS_SENT = "Sent"
STATUS_FAILED = "Failed"
STATUS_PENDING = "Pending"

# WhatsApp link bases (used in wa_links.py)
WA_ME_BASE = "https://wa.me"
WHATSAPP_WEB_BASE = "https://web.whatsapp.com/send"

# Persistence paths
DATA_FOLDER = "data"
DATABASE_FILE = "data/app.db"
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
DELAY_MIN_SECONDS = 3
DELAY_MAX_SECONDS = 5
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

# Chrome automation (local Auto Send only)
WHATSAPP_CHROME_DEBUG_PORT = 9223
WHATSAPP_CHROME_PROFILE_DIR_NAME = ".chrome-whatsapp-profile"
ATTACHMENT_UPLOAD_STAGING_DIR = "attachments/upload_staging"
ATTACHMENT_UPLOAD_STAGING_NAME = "invite"

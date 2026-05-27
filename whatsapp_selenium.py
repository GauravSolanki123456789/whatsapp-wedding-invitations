"""Reliable WhatsApp Web automation using Selenium element selectors."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from platform import system
from urllib.parse import quote

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from constants import (
    DOCUMENT_EXTENSIONS,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    WHATSAPP_AFTER_ATTACH_SECONDS,
    WHATSAPP_MAX_UPLOAD_WAIT_SECONDS,
    WHATSAPP_UPLOAD_SECONDS_PER_MB,
    WHATSAPP_PAGE_WAIT_SECONDS,
)
from utils import validate_attachment_for_whatsapp

CHROME_DEBUG_PORT = int(os.environ.get("WHATSAPP_CHROME_DEBUG_PORT", "9222"))
CHROME_PROFILE_DIR = os.environ.get(
    "WHATSAPP_CHROME_PROFILE_DIR",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"),
)
CHROME_PROFILE_NAME = os.environ.get("WHATSAPP_CHROME_PROFILE", "Default")
CHAT_WAIT_SECONDS = WHATSAPP_PAGE_WAIT_SECONDS
LOGIN_WAIT_SECONDS = 180
UPLOAD_WAIT_SECONDS = WHATSAPP_MAX_UPLOAD_WAIT_SECONDS

# Short pauses only where the UI needs a moment to react (not between guests)
UI_PAUSE_SHORT = 0.25
UI_PAUSE_MED = 0.5


def find_chrome_executable() -> str:
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError(
        "Google Chrome not found. Install Chrome to use Auto Send."
    )


def is_debug_port_open(port: int = CHROME_DEBUG_PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def is_chrome_running() -> bool:
    if system().lower() != "windows":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chrome.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return "chrome.exe" in result.stdout.lower()
    except (subprocess.SubprocessError, OSError):
        return False


def kill_chrome_processes() -> None:
    """Close Chrome so we can relaunch it with the automation port."""
    if system().lower() != "windows":
        return
    if not is_chrome_running():
        return
    subprocess.run(
        ["taskkill", "/F", "/IM", "chrome.exe", "/T"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    for _ in range(20):
        if not is_chrome_running():
            return
        time.sleep(0.5)


def phone_for_url(mobile_number: str) -> str:
    return mobile_number.lstrip("+").replace(" ", "")


def conversation_url(mobile_number: str, message: str = "") -> str:
    phone = phone_for_url(mobile_number)
    url = (
        f"https://web.whatsapp.com/send?phone={phone}"
        f"&type=phone_number&app_absent=0"
    )
    if message.strip():
        url = f"{url}&text={quote(message)}"
    return url


def selenium_file_path(attachment_path: str) -> str:
    """Absolute path with native separators — required for Windows file inputs."""
    return os.path.normpath(os.path.abspath(attachment_path))


def normalize_file_path(attachment_path: str) -> str:
    return selenium_file_path(attachment_path)


def attachment_kind(attachment_path: str) -> str:
    suffix = Path(attachment_path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in DOCUMENT_EXTENSIONS:
        return "document"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    raise ValueError(f"Unsupported attachment type: {suffix}")


def friendly_error(error: Exception) -> str:
    message = str(error).lower()
    if "not supported" in message or "rejected the file" in message:
        return (
            "WhatsApp rejected the file. Videos must be sent via Photos & videos "
            "and must be under 100 MB. Compress large MP4 files and try again."
        )
    if "no such window" in message or "target window already closed" in message:
        return (
            "Lost the WhatsApp tab in Chrome. Keep web.whatsapp.com open in a tab, "
            "run scripts\\start-chrome-debug.bat if needed, then try again."
        )
    if "chrome must be started" in message or "start-chrome-debug" in message:
        return str(error)
    if "chat is not open" in message or "could not open whatsapp chat" in message:
        return (
            "WhatsApp chat did not open for this number. "
            "Make sure the contact exists in WhatsApp, then try again."
        )
    if "attach menu" in message or "photos" in message or "file input" in message or "upload" in message:
        return str(error)
    if "attach" in message and ("+" in message or "button" in message):
        return (
            "Could not find the WhatsApp attach (+) button. "
            "Close any open preview in Chrome, keep the WhatsApp tab visible, "
            "wait for the chat to fully load, then try again."
        )
    if "click intercepted" in message or "starting chat" in message or "still loading" in message or "spinner" in message:
        return (
            "WhatsApp was still loading. Keep the automation Chrome window "
            "maximized and visible, then try again."
        )
    if "qr code" in message or "scan" in message:
        return "Scan the QR code in the automation Chrome window, then try again."
    if "preview" in message or "document was not sent" in message or "send button" in message:
        return str(error)
    if "compress" in message or "mb" in message:
        return str(error)
    if "invalid" in message and "number" in message:
        return str(error)
    if len(str(error)) > 220:
        return "WhatsApp automation failed. Keep the Chrome window open and try again."
    return str(error)


CHROME_SETUP_HINT = (
    "Click Auto Send again — Chrome will restart automatically with WhatsApp."
)


class WhatsAppSession:
    """Uses your existing Chrome — switches to the WhatsApp tab you already have open."""

    def __init__(self) -> None:
        self.driver: webdriver.Chrome | None = None
        self._whatsapp_tab_handle: str | None = None
        self._attached_via_debugger = False

    def start(self) -> None:
        if self.driver is not None:
            self._ensure_whatsapp_tab()
            return

        if not is_debug_port_open():
            if is_chrome_running():
                kill_chrome_processes()
            self._launch_chrome_with_debugging()

        if not is_debug_port_open():
            raise RuntimeError(
                "Chrome did not start for automation. " + CHROME_SETUP_HINT
            )

        if not self._try_connect_debugger():
            kill_chrome_processes()
            self._launch_chrome_with_debugging()
            if not self._try_connect_debugger():
                raise RuntimeError(
                    f"Could not connect to Chrome. {CHROME_SETUP_HINT}"
                )

        assert self.driver is not None
        existing = self._find_logged_in_whatsapp_tab()
        if existing:
            self.driver.switch_to.window(existing)
            self._whatsapp_tab_handle = existing
            self._wait_for_app_ready()
            return

        whatsapp_url_tab = self._find_whatsapp_url_tab()
        if whatsapp_url_tab:
            self.driver.switch_to.window(whatsapp_url_tab)
            self._whatsapp_tab_handle = whatsapp_url_tab
            self._wait_until_logged_in()
            self._wait_for_app_ready()
            return

        self.driver.switch_to.new_window("tab")
        self._whatsapp_tab_handle = self.driver.current_window_handle
        self._hide_automation_flags()
        self.driver.get("https://web.whatsapp.com")
        self._wait_until_logged_in()
        self._wait_for_app_ready()

    def _try_connect_debugger(self) -> bool:
        if not is_debug_port_open():
            return False
        try:
            options = Options()
            options.add_experimental_option(
                "debuggerAddress", f"127.0.0.1:{CHROME_DEBUG_PORT}"
            )
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self._attached_via_debugger = True
            return True
        except WebDriverException:
            self.driver = None
            return False

    def _launch_chrome_with_debugging(self) -> None:
        chrome_path = find_chrome_executable()
        launch_args = [
            chrome_path,
            f"--remote-debugging-port={CHROME_DEBUG_PORT}",
            "--remote-allow-origins=*",
            "https://web.whatsapp.com",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
            "--disable-session-crashed-bubble",
        ]
        if os.path.isdir(CHROME_PROFILE_DIR):
            launch_args.extend(
                [
                    f"--user-data-dir={CHROME_PROFILE_DIR}",
                    f"--profile-directory={CHROME_PROFILE_NAME}",
                ]
            )
        subprocess.Popen(
            launch_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        for _ in range(60):
            if is_debug_port_open():
                time.sleep(2)
                return
            time.sleep(1)
        raise RuntimeError("Chrome did not start for automation.")

    def _find_whatsapp_url_tab(self) -> str | None:
        if self.driver is None:
            return None
        for handle in list(self.driver.window_handles):
            try:
                self.driver.switch_to.window(handle)
                if "web.whatsapp.com" in (self.driver.current_url or ""):
                    return handle
            except WebDriverException:
                continue
        return None

    def _find_logged_in_whatsapp_tab(self) -> str | None:
        if self.driver is None:
            return None
        for handle in list(self.driver.window_handles):
            try:
                self.driver.switch_to.window(handle)
                if "web.whatsapp.com" not in (self.driver.current_url or ""):
                    continue
                if self._is_logged_in():
                    return handle
            except WebDriverException:
                continue
        return None

    def _ensure_whatsapp_tab(self) -> None:
        if self.driver is None:
            return
        try:
            handles = self.driver.window_handles
        except WebDriverException as exc:
            raise RuntimeError(
                "Lost connection to Chrome. Run scripts\\start-chrome-debug.bat "
                "and keep your WhatsApp tab open."
            ) from exc

        if (
            self._whatsapp_tab_handle
            and self._whatsapp_tab_handle in handles
        ):
            try:
                self.driver.switch_to.window(self._whatsapp_tab_handle)
                return
            except WebDriverException:
                pass

        found = self._find_logged_in_whatsapp_tab()
        if found:
            self.driver.switch_to.window(found)
            self._whatsapp_tab_handle = found
            return

        raise RuntimeError(
            "WhatsApp tab not found. Open web.whatsapp.com in Chrome and log in, then try again."
        )

    def _switch_to_whatsapp_tab(self) -> None:
        self._ensure_whatsapp_tab()

    def _hide_automation_flags(self) -> None:
        if self.driver is None:
            return
        try:
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                    """
                },
            )
        except WebDriverException:
            pass

    def stop(self) -> None:
        """Detach from Chrome — never close your tabs or quit the browser."""
        self.driver = None
        self._whatsapp_tab_handle = None

    def _has_attachment_overlay(self) -> bool:
        if self.driver is None:
            return False
        if self._attach_menu_is_open():
            return True
        preview_markers = [
            '[data-testid="media-caption-input-container"]',
            '[data-testid="media-viewer"]',
            '[data-animate-media-viewer="true"]',
        ]
        for selector in preview_markers:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if element.is_displayed():
                    return True
        return False

    def dismiss_stale_ui(self) -> None:
        """Close attachment previews/menus only — never close an open chat."""
        if self.driver is None:
            return
        if not self._has_attachment_overlay():
            return
        for _ in range(2):
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.4)
        time.sleep(0.5)

    def dismiss_before_navigation(self) -> None:
        """Reset overlays before navigating to a new chat URL."""
        self.dismiss_stale_ui()

    def send(
        self,
        mobile_number: str,
        message: str,
        attachment_path: str | None = None,
    ) -> None:
        if self.driver is None:
            raise RuntimeError("WhatsApp browser session is not started.")

        if attachment_path:
            size_error = validate_attachment_for_whatsapp(attachment_path)
            if size_error:
                raise ValueError(size_error)

        if not attachment_path and not message.strip():
            raise ValueError("Message or attachment is required.")

        self.dismiss_before_navigation()
        self._focus_browser_window()
        self._ensure_whatsapp_tab()

        if attachment_path:
            self._open_conversation(mobile_number)
            self._focus_browser_window()
            self._focus_chat_footer()
            time.sleep(UI_PAUSE_MED)
        else:
            self.driver.get(conversation_url(mobile_number, message))
            self._wait_for_chat_ready()
            self._ensure_valid_number(mobile_number)

        if attachment_path:
            self._send_attachment(normalize_file_path(attachment_path), message)
        else:
            self._click_send_button()

        time.sleep(UI_PAUSE_MED)

    def _focus_browser_window(self) -> None:
        if self.driver is None:
            return
        try:
            self.driver.switch_to.window(self.driver.current_window_handle)
        except WebDriverException:
            pass
        if system().lower() == "windows":
            try:
                import pygetwindow as gw

                for title_fragment in ("WhatsApp", "Chrome"):
                    matches = gw.getWindowsWithTitle(title_fragment)
                    for window in matches:
                        if "whatsapp" in window.title.lower():
                            window.activate()
                            break
            except Exception:
                pass
        time.sleep(0.5)

    def _find_message_composers(self) -> list[WebElement]:
        if self.driver is None:
            return []

        composer_selectors = [
            '#main footer div[contenteditable="true"][role="textbox"]',
            '#main footer div[contenteditable="true"][data-tab="10"]',
            '#main footer div[contenteditable="true"]',
            '#main [data-testid="conversation-compose-box-input"] div[contenteditable="true"]',
            '[data-testid="conversation-compose-box-input"] div[contenteditable="true"]',
        ]
        seen: set[str] = set()
        composers: list[WebElement] = []
        for selector in composer_selectors:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if element.id in seen or not element.is_displayed():
                    continue
                data_tab = (element.get_attribute("data-tab") or "").strip()
                if data_tab == "3":
                    continue
                seen.add(element.id)
                composers.append(element)
        return composers

    def _has_chat_footer(self) -> bool:
        if self.driver is None:
            return False
        footers = self.driver.find_elements(By.CSS_SELECTOR, "#main footer")
        return any(footer.is_displayed() for footer in footers)

    def _ensure_on_whatsapp_home(self) -> None:
        """Switch to the WhatsApp tab without reloading the whole browser."""
        if self.driver is None:
            return
        self._switch_to_whatsapp_tab()
        if "web.whatsapp.com" not in (self.driver.current_url or ""):
            self.driver.get("https://web.whatsapp.com")
        if not self._is_logged_in():
            self._wait_until_logged_in()

    def _is_logged_in(self) -> bool:
        if self.driver is None:
            return False
        return bool(
            self.driver.find_elements(By.CSS_SELECTOR, "#pane-side")
            or self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="chat-list"]')
        )

    def _is_conversation_open(self) -> bool:
        """True when chat is usable: composer, attach menu, preview, or footer + button."""
        if self.driver is None:
            return False

        if self._attach_menu_is_open() or self._preview_is_open():
            return True

        if self._find_message_composers() or self._find_attach_buttons():
            return True

        if self._is_main_panel_loading():
            return False

        if not self._has_chat_footer():
            return False

        attach_in_footer = self.driver.find_elements(
            By.CSS_SELECTOR,
            '#main footer span[data-icon="plus-rounded"], '
            '#main footer span[data-icon="plus"], '
            '#main footer span[data-icon="clip"], '
            '#main footer span[data-icon="attach-menu-plus"]',
        )
        return any(button.is_displayed() for button in attach_in_footer)

    def _has_chat_header(self) -> bool:
        if self.driver is None:
            return False
        headers = self.driver.find_elements(
            By.CSS_SELECTOR,
            '#main header [data-testid="conversation-info-header"], #main header',
        )
        return any(header.is_displayed() for header in headers)

    def _is_main_panel_loading(self) -> bool:
        """True when chat header shows but footer/composer is not ready yet."""
        if self.driver is None:
            return False
        if self._preview_is_open() or self._attach_menu_is_open():
            return False
        if self._find_message_composers() or self._find_attach_buttons():
            return False
        if not self._has_chat_header():
            return False
        return not self._has_chat_footer()

    def _wait_for_chat_fully_loaded(self, timeout: int = 60) -> None:
        if self.driver is None:
            return

        def chat_ready(_driver: webdriver.Chrome) -> bool:
            if self._preview_is_open():
                return True
            if self._is_main_panel_loading():
                return False
            if self._find_message_composers() or self._find_attach_buttons():
                return True
            return self._is_conversation_open() and not self._is_main_panel_loading()

        try:
            WebDriverWait(self.driver, timeout).until(chat_ready)
        except TimeoutException as exc:
            raise TimeoutException(
                "WhatsApp chat is still loading (spinner). "
                "Keep the Chrome window maximized and wait, then try again."
            ) from exc

        if self._is_main_panel_loading():
            raise TimeoutException(
                "WhatsApp chat footer did not load. Close other WhatsApp tabs and try again."
            )

    def _click_continue_to_chat_if_present(self) -> None:
        if self.driver is None:
            return

        continue_xpaths = [
            "//a[contains(@href,'send?phone')]",
            "//span[normalize-space()='Continue to chat']/ancestor::div[@role='button'][1]",
            "//span[normalize-space()='Continue to Chat']/ancestor::div[@role='button'][1]",
            "//div[@role='button']//span[contains(normalize-space(),'Continue to chat')]",
            "//div[@role='button']//span[contains(normalize-space(),'Continue to Chat')]",
            "//button[contains(normalize-space(),'Continue')]",
            "//div[@role='button'][.//span[contains(normalize-space(),'Chat')]]",
        ]
        for _ in range(3):
            clicked = False
            for xpath in continue_xpaths:
                for element in self.driver.find_elements(By.XPATH, xpath):
                    if element.is_displayed():
                        self._click_element_or_parent(element)
                        time.sleep(UI_PAUSE_MED)
                        clicked = True
                        break
                if clicked:
                    break
            if not clicked:
                break
            if self._is_conversation_open():
                return

    def _is_whatsapp_landing(self) -> bool:
        if self.driver is None:
            return False
        if self._has_chat_header() or self._find_message_composers():
            return False
        landing_markers = self.driver.find_elements(
            By.XPATH,
            "//*[contains(text(),'Download WhatsApp for Windows') "
            "or contains(text(),'Send document')]",
        )
        return any(marker.is_displayed() for marker in landing_markers)

    def _click_first_search_result(self) -> bool:
        if self.driver is None:
            return False
        for item in self.driver.find_elements(
            By.CSS_SELECTOR, "#pane-side div[role='listitem']"
        ):
            if not item.is_displayed():
                continue
            self._click_element_or_parent(item)
            time.sleep(UI_PAUSE_MED)
            return True
        return False

    def _open_conversation_via_search(self, mobile_number: str) -> None:
        if self.driver is None:
            return

        self._ensure_on_whatsapp_home()
        self._focus_browser_window()
        time.sleep(UI_PAUSE_MED)

        search_selectors = [
            '#side div[contenteditable="true"][data-tab="3"]',
            '[data-testid="chat-list-search"] div[contenteditable="true"]',
            '#pane-side div[contenteditable="true"][data-tab="3"]',
            'div[contenteditable="true"][data-tab="3"]',
        ]
        search_box: WebElement | None = None
        for selector in search_selectors:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if element.is_displayed():
                    search_box = element
                    break
            if search_box:
                break

        if search_box is None:
            raise RuntimeError("WhatsApp search box not found.")

        self._javascript_click(search_box)
        search_box.send_keys(Keys.CONTROL, "a")
        search_box.send_keys(Keys.BACKSPACE)

        phone = phone_for_url(mobile_number)
        search_terms = [mobile_number, f"+{phone}", phone[-10:]]
        seen_terms: set[str] = set()
        for term in search_terms:
            if not term or term in seen_terms:
                continue
            seen_terms.add(term)
            search_box.send_keys(Keys.CONTROL, "a")
            search_box.send_keys(Keys.BACKSPACE)
            search_box.send_keys(term)
            time.sleep(1.5)

            phone_tail = phone[-10:]
            result_xpaths = [
                f"//div[@role='listitem'][.//span[@title='{mobile_number}']]",
                f"//div[@role='listitem'][.//span[@title='+{phone}']]",
                f"//div[@role='listitem'][.//span[contains(@title,'{phone_tail}')]]",
                f"//div[@role='listitem'][.//span[contains(text(),'{phone_tail}')]]",
                f"//span[@title='{mobile_number}']/ancestor::div[@role='listitem'][1]",
                f"//span[contains(@title,'{phone_tail}')]/ancestor::div[@role='listitem'][1]",
            ]
            for xpath in result_xpaths:
                for element in self.driver.find_elements(By.XPATH, xpath):
                    if element.is_displayed():
                        self._click_element_or_parent(element)
                        time.sleep(UI_PAUSE_MED)
                        if not self._is_whatsapp_landing():
                            return

            if self._click_first_search_result() and not self._is_whatsapp_landing():
                return

            search_box.send_keys(Keys.ENTER)
            time.sleep(UI_PAUSE_MED)
            if not self._is_whatsapp_landing() and (
                self._is_conversation_open() or self._has_chat_header()
            ):
                return

        if self._is_whatsapp_landing():
            raise RuntimeError(
                f"Could not open chat for {mobile_number}. "
                "Save the number as a WhatsApp contact first, or message them once manually."
            )
        raise RuntimeError(f"Could not find {mobile_number} in WhatsApp search.")

    def _open_conversation(self, mobile_number: str) -> None:
        """Open chat via search — avoids full-page reloads from direct links."""
        if self.driver is None:
            return

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                self._ensure_on_whatsapp_home()
                self._wait_for_app_ready()
                self._open_conversation_via_search(mobile_number)
                self._ensure_valid_number(mobile_number)
                self._wait_for_chat_fully_loaded(timeout=90)
                self._focus_chat_footer()
                self._wait_for_footer_attach_button()
                return
            except Exception as exc:
                last_error = exc
                if self._has_attachment_overlay():
                    self.dismiss_stale_ui()
                time.sleep(UI_PAUSE_MED)

        raise RuntimeError(
            f"Could not open WhatsApp chat for {mobile_number}. "
            f"Keep the automation Chrome window visible and try again. ({last_error})"
        )

    def _wait_for_app_ready(self) -> None:
        """Wait until WhatsApp finishes splash-screen loading."""
        if self.driver is None:
            return

        def app_ready(_driver: webdriver.Chrome) -> bool:
            return self._is_logged_in()

        try:
            WebDriverWait(self.driver, 90).until(app_ready)
        except TimeoutException as exc:
            raise TimeoutException(
                "WhatsApp Web is still on the loading screen. "
                "Keep Chrome open, wait for your chats to appear, then try again."
            ) from exc

    def _open_conversation_via_direct_link(self, mobile_number: str) -> None:
        if self.driver is None:
            return

        chat_url = conversation_url(mobile_number)
        self.driver.get(chat_url)
        self._focus_browser_window()
        self._wait_for_starting_chat_to_finish()

        for _ in range(4):
            self._click_continue_to_chat_if_present()
            if self._is_conversation_open():
                return
            time.sleep(1.5)

        if not self._is_conversation_open():
            self.driver.execute_script(f"window.location.href = {chat_url!r};")
            self._wait_for_starting_chat_to_finish()
            for _ in range(3):
                self._click_continue_to_chat_if_present()
                if self._is_conversation_open():
                    return
                time.sleep(1.5)

    def _wait(self, timeout: int = CHAT_WAIT_SECONDS) -> WebDriverWait:
        if self.driver is None:
            raise RuntimeError("WhatsApp browser session is not started.")
        return WebDriverWait(self.driver, timeout)

    def _wait_until_logged_in(self) -> None:
        if self.driver is None:
            return

        def logged_in(driver: webdriver.Chrome) -> bool:
            return bool(
                driver.find_elements(By.CSS_SELECTOR, "#pane-side")
                or driver.find_elements(By.CSS_SELECTOR, '[data-testid="chat-list"]')
                or driver.find_elements(By.CSS_SELECTOR, '[data-testid="chat-list-search"]')
            )

        try:
            WebDriverWait(self.driver, LOGIN_WAIT_SECONDS).until(logged_in)
        except TimeoutException as exc:
            raise TimeoutException(
                "WhatsApp Web did not finish loading. "
                "Scan the QR code in the automation Chrome window, then try again."
            ) from exc

    def _wait_for_chat_ready(self) -> None:
        if self.driver is None:
            return

        self._wait_for_starting_chat_to_finish()
        self._click_continue_to_chat_if_present()
        self._wait_for_chat_fully_loaded(timeout=40)

    def _wait_for_footer_attach_button(self) -> None:
        if self.driver is None:
            return

        def footer_ready(_driver: webdriver.Chrome) -> bool:
            return bool(self._find_attach_buttons())

        try:
            WebDriverWait(self.driver, 25).until(footer_ready)
        except TimeoutException:
            pass

    def _focus_chat_footer(self) -> None:
        if self.driver is None:
            return
        for selector in ("#main footer", "#main", '[data-testid="conversation-panel-wrapper"]'):
            footers = self.driver.find_elements(By.CSS_SELECTOR, selector)
            if footers:
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'end', inline: 'nearest'});",
                        footers[-1],
                    )
                except WebDriverException:
                    pass
                break
        time.sleep(0.5)

    def _wait_for_starting_chat_to_finish(self) -> None:
        if self.driver is None:
            return

        def chat_not_loading(driver: webdriver.Chrome) -> bool:
            loading_markers = driver.find_elements(
                By.XPATH,
                "//*[contains(text(),'Starting chat') or contains(text(),'Loading chat')]",
            )
            return not any(marker.is_displayed() for marker in loading_markers)

        try:
            WebDriverWait(self.driver, CHAT_WAIT_SECONDS).until(chat_not_loading)
        except TimeoutException:
            pass

        time.sleep(1)

    def _ensure_valid_number(self, mobile_number: str) -> None:
        if self.driver is None:
            return

        page_source = self.driver.page_source.lower()
        if "phone number shared via url is invalid" in page_source:
            raise ValueError(f"WhatsApp rejected this number: {mobile_number}")

    def _whatsapp_error_visible(self) -> bool:
        if self.driver is None:
            return False

        error_phrases = (
            "not supported",
            "file you tried",
            "couldn't be sent",
            "could not be sent",
        )
        page = self.driver.page_source.lower()
        if any(phrase in page for phrase in error_phrases):
            return True

        for element in self.driver.find_elements(
            By.XPATH,
            "//*[contains(@role,'alert') or contains(@data-testid,'toast')]",
        ):
            if not element.is_displayed():
                continue
            text = element.text.lower()
            if any(phrase in text for phrase in error_phrases):
                return True
        return False

    def _javascript_click(self, element: WebElement) -> None:
        if self.driver is None:
            return
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center', inline: 'center'});",
            element,
        )
        time.sleep(0.4)
        try:
            element.click()
        except (ElementClickInterceptedException, WebDriverException):
            self.driver.execute_script("arguments[0].click();", element)

    def _click_element_or_parent(self, element: WebElement) -> None:
        if self.driver is None:
            return

        candidates = [element]
        for xpath in ("./ancestor::button[1]", "./ancestor::div[@role='button'][1]", "./ancestor::li[1]"):
            try:
                parent = element.find_element(By.XPATH, xpath)
                if parent not in candidates:
                    candidates.insert(0, parent)
            except WebDriverException:
                pass

        for candidate in candidates:
            try:
                if candidate.is_displayed():
                    self._javascript_click(candidate)
                    return
            except StaleElementReferenceException:
                continue

        self._javascript_click(element)

    def _press_escape(self) -> None:
        if self.driver is None:
            return
        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
        time.sleep(0.5)

    def _find_attach_buttons(self) -> list[WebElement]:
        """Find attach (+) controls only inside the open chat footer."""
        if self.driver is None:
            return []

        if not self._has_chat_footer():
            return []

        attach_selectors = [
            '#main footer span[data-icon="plus-rounded"]',
            '#main footer span[data-icon="plus"]',
            '#main footer span[data-icon="clip"]',
            '#main footer span[data-icon="attach-menu-plus"]',
            '#main footer [data-testid="attach-menu-plus"]',
            '#main footer button[aria-label="Attach"]',
            '#main footer div[title="Attach"]',
        ]
        attach_xpaths = [
            "//*[@id='main']//footer//span[@data-icon='plus-rounded' or @data-icon='plus' or @data-icon='clip']",
            "//*[@id='main']//footer//div[@role='button' and (@title='Attach' or @aria-label='Attach')]",
            "//*[@id='main']//footer//button[contains(@aria-label,'Attach')]",
        ]

        seen: set[str] = set()
        results: list[WebElement] = []

        for selector in attach_selectors:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if element.id not in seen and element.is_displayed():
                    seen.add(element.id)
                    results.append(element)

        for xpath in attach_xpaths:
            for element in self.driver.find_elements(By.XPATH, xpath):
                if element.id not in seen and element.is_displayed():
                    seen.add(element.id)
                    results.append(element)

        return results

    def _open_attach_menu(self) -> None:
        if self.driver is None:
            return

        if not self._is_conversation_open() and not self._has_chat_footer():
            raise RuntimeError(
                "WhatsApp chat is not open — cannot attach files on the home screen."
            )

        if self._attach_menu_is_open():
            return

        self._focus_browser_window()
        self._focus_chat_footer()
        time.sleep(0.8)

        attach_buttons = self._find_attach_buttons()
        if not attach_buttons:
            try:
                message_box = self._get_message_box()
                ActionChains(self.driver).move_to_element(message_box).click().perform()
                time.sleep(0.8)
            except RuntimeError:
                pass
            attach_buttons = self._find_attach_buttons()

        for button in attach_buttons:
            try:
                self._click_element_or_parent(button)
                time.sleep(UI_PAUSE_MED)
                if self._attach_menu_is_open():
                    return
            except StaleElementReferenceException:
                continue

        raise RuntimeError("Could not find the WhatsApp attach (+) button in the chat footer.")

    def _attach_menu_is_open(self) -> bool:
        if self.driver is None or not self._has_chat_footer():
            return False

        menu_markers = [
            '[data-testid="mi-document"]',
            '[data-testid="mi-attach-media"]',
            '[data-testid="attach-document"]',
            '[data-testid="attach-media"]',
        ]
        for selector in menu_markers:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if element.is_displayed():
                    return True

        menu_texts = self.driver.find_elements(
            By.XPATH,
            "//span[normalize-space()='Document' or contains(normalize-space(),'Photos') "
            "or normalize-space()='Camera' or normalize-space()='Audio']",
        )
        return any(item.is_displayed() for item in menu_texts)

    def _wait_for_attach_menu(self) -> None:
        if self.driver is None:
            return

        try:
            WebDriverWait(self.driver, 15).until(
                lambda _driver: self._attach_menu_is_open()
            )
        except TimeoutException as exc:
            raise TimeoutException(
                "WhatsApp attach menu did not open. Keep the Chrome window maximized."
            ) from exc
        time.sleep(UI_PAUSE_SHORT)

    def _prepare_file_input(self, file_input: WebElement) -> None:
        if self.driver is None:
            return
        self.driver.execute_script(
            """
            const input = arguments[0];
            input.removeAttribute('hidden');
            input.style.display = 'block';
            input.style.visibility = 'visible';
            input.style.opacity = '1';
            input.style.height = '1px';
            input.style.width = '1px';
            input.style.position = 'fixed';
            input.style.top = '0px';
            input.style.left = '0px';
            input.style.zIndex = '9999';
            """,
            file_input,
        )

    def _try_send_file_to_input(self, file_input: WebElement, attachment_path: str) -> bool:
        if self.driver is None:
            return False

        file_path = selenium_file_path(attachment_path)
        if not os.path.isfile(file_path):
            return False

        try:
            self._prepare_file_input(file_input)
            file_input.send_keys(file_path)
            time.sleep(UI_PAUSE_MED)
            if self._whatsapp_error_visible():
                return False
            return True
        except WebDriverException:
            return False

    def _is_document_only_input(self, file_input: WebElement) -> bool:
        accept = (file_input.get_attribute("accept") or "").lower()
        if not accept or accept in {"*", "*/*"}:
            return False
        if "pdf" in accept or "application" in accept:
            return True
        return "image" not in accept and "video" not in accept and "mp4" not in accept

    def _inject_file_into_menu_input(self, attachment_path: str, kind: str) -> bool:
        """Send file to hidden input in attach menu — avoids Windows file dialog."""
        if self.driver is None:
            return False

        if kind == "document":
            selectors = [
                'li[data-testid="mi-document"] input[type="file"]',
                '[data-testid="attach-document"] input[type="file"]',
                'input[type="file"][accept*=".pdf"]',
                'input[type="file"][accept*="application"]',
            ]
        else:
            selectors = [
                'li[data-testid="mi-attach-media"] input[type="file"]',
                '[data-testid="attach-media"] input[type="file"]',
                'input[type="file"][accept*="video"]',
                'input[type="file"][accept*="image"]',
                'input[type="file"][accept*="mp4"]',
            ]

        for selector in selectors:
            for file_input in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if self._try_send_file_to_input(file_input, attachment_path):
                    return True

        for file_input in self._collect_file_inputs():
            if kind == "document":
                if self._file_input_matches_kind(file_input, kind):
                    if self._try_send_file_to_input(file_input, attachment_path):
                        return True
            elif not self._is_document_only_input(file_input):
                if self._try_send_file_to_input(file_input, attachment_path):
                    return True

        return False

    def _file_input_matches_kind(self, file_input: WebElement, kind: str) -> bool:
        accept = (file_input.get_attribute("accept") or "").lower()

        if kind == "document":
            if "image" in accept or "video" in accept:
                return False
            return (
                accept in {"*", "*/*"}
                or "pdf" in accept
                or "application" in accept
                or not accept
            )

        if accept in {"*", "*/*"}:
            return False
        if "pdf" in accept or "application" in accept:
            return False
        return "image" in accept or "video" in accept or "mp4" in accept or "quicktime" in accept

    def _collect_file_inputs(self) -> list[WebElement]:
        if self.driver is None:
            return []
        return self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')

    def _click_attach_menu_item_by_text(self, labels: tuple[str, ...]) -> bool:
        """Click an attach-menu row by visible label (WhatsApp often drops test IDs)."""
        if self.driver is None:
            return False

        for label in labels:
            xpaths = [
                f"//span[normalize-space()='{label}']/ancestor::li[1]",
                f"//span[contains(normalize-space(),'{label}')]/ancestor::li[1]",
                f"//div[@role='button'][.//span[contains(normalize-space(),'{label}')]]",
                f"//*[@role='menuitem'][.//span[contains(normalize-space(),'{label}')]]",
                f"//span[contains(normalize-space(),'{label}')]/ancestor::*[@role='button'][1]",
            ]
            for xpath in xpaths:
                for item in self.driver.find_elements(By.XPATH, xpath):
                    if item.is_displayed():
                        self._click_element_or_parent(item)
                        time.sleep(UI_PAUSE_MED)
                        return True

        if self.driver is None:
            return False

        label_fragment = labels[0].split()[0]
        clicked = self.driver.execute_script(
            """
            const labels = arguments[0];
            const candidates = document.querySelectorAll(
                'li, div[role="button"], [role="menuitem"], span'
            );
            for (const el of candidates) {
                const text = (el.textContent || '').trim();
                if (!text) continue;
                for (const label of labels) {
                    if (text === label || text.includes(label)) {
                        const clickTarget =
                            el.closest('li') ||
                            el.closest('[role="button"]') ||
                            el.closest('[role="menuitem"]') ||
                            el;
                        if (clickTarget && clickTarget.offsetParent !== null) {
                            clickTarget.click();
                            return true;
                        }
                    }
                }
            }
            return false;
            """,
            list(labels),
        )
        if clicked:
            time.sleep(UI_PAUSE_MED)
            return True

        return False

    def _click_attach_menu_item(self, kind: str) -> bool:
        if self.driver is None:
            return False

        if kind == "document":
            text_labels = ("Document",)
            selectors = [
                '[data-testid="attach-document"]',
                '[data-testid="mi-document"]',
                'li[data-testid="mi-document"]',
            ]
            xpaths = [
                "//li[@data-testid='mi-document']",
                "//span[@data-testid='attach-document']",
            ]
        else:
            text_labels = ("Photos & videos", "Photos and videos", "Photos")
            selectors = [
                '[data-testid="attach-media"]',
                '[data-testid="mi-attach-media"]',
                'li[data-testid="mi-attach-media"]',
                'span[data-icon="attach-image"]',
                'span[data-icon="media"]',
            ]
            xpaths = [
                "//li[@data-testid='mi-attach-media']",
                "//span[@data-testid='attach-media']",
            ]

        if self._click_attach_menu_item_by_text(text_labels):
            return True

        for selector in selectors:
            for item in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if item.is_displayed():
                    self._click_element_or_parent(item)
                    time.sleep(UI_PAUSE_MED)
                    return True

        for xpath in xpaths:
            for item in self.driver.find_elements(By.XPATH, xpath):
                if item.is_displayed():
                    self._click_element_or_parent(item)
                    time.sleep(UI_PAUSE_MED)
                    return True

        return False

    def _wait_for_file_input(self, kind: str, timeout: int = 12) -> list[WebElement]:
        if self.driver is None:
            return []

        def inputs_ready(_driver: webdriver.Chrome) -> bool:
            return bool(self._file_inputs_for_kind(kind))

        try:
            WebDriverWait(self.driver, timeout).until(inputs_ready)
        except TimeoutException:
            pass
        return self._file_inputs_for_kind(kind)

    def _file_inputs_for_kind(self, kind: str) -> list[WebElement]:
        matched: list[WebElement] = []
        for file_input in self._collect_file_inputs():
            if self._file_input_matches_kind(file_input, kind):
                matched.append(file_input)
        return matched

    def _upload_via_menu_inputs(self, attachment_path: str, kind: str) -> None:
        if self.driver is None:
            return

        if self._inject_file_into_menu_input(attachment_path, kind):
            return

        if not self._click_attach_menu_item(kind):
            raise RuntimeError(
                f"Could not click Photos & videos in the attach menu "
                f"(needed for {kind} files)."
            )

        time.sleep(UI_PAUSE_MED)
        file_inputs = self._wait_for_file_input(kind, timeout=8)

        for file_input in file_inputs:
            if self._try_send_file_to_input(file_input, attachment_path):
                return

        for file_input in self._collect_file_inputs():
            if kind == "document":
                if not self._file_input_matches_kind(file_input, kind):
                    continue
            elif self._is_document_only_input(file_input):
                continue
            if self._try_send_file_to_input(file_input, attachment_path):
                return

        raise RuntimeError(
            "Could not upload the file. WhatsApp may have opened a file picker — "
            "keep the automation Chrome window focused and try again."
        )

    def _upload_via_hidden_input(self, attachment_path: str, kind: str) -> None:
        if self.driver is None:
            return

        if not os.path.isfile(attachment_path):
            raise FileNotFoundError(f"Attachment file not found: {attachment_path}")

        last_error: Exception | None = None

        for _attempt in range(3):
            try:
                if self._preview_is_open():
                    return

                self._wait_for_chat_fully_loaded(timeout=45)

                self._focus_browser_window()
                self._focus_chat_footer()

                if self._has_attachment_overlay() and not self._preview_is_open():
                    self.dismiss_stale_ui()
                    time.sleep(UI_PAUSE_SHORT)
                    self._wait_for_chat_fully_loaded(timeout=30)

                try:
                    message_box = self._get_message_box()
                    ActionChains(self.driver).move_to_element(message_box).click().perform()
                    time.sleep(UI_PAUSE_SHORT)
                except RuntimeError:
                    pass

                self._wait_for_footer_attach_button()
                self._open_attach_menu()
                self._wait_for_attach_menu()
                self._upload_via_menu_inputs(attachment_path, kind)

                time.sleep(UI_PAUSE_MED)
                if self._whatsapp_error_visible():
                    raise RuntimeError(
                        "WhatsApp rejected the file. Videos must use Photos & videos, not Document."
                    )
                return
            except Exception as exc:
                last_error = exc
                if self._has_attachment_overlay():
                    self.dismiss_stale_ui()
                time.sleep(UI_PAUSE_MED)

        raise RuntimeError(
            f"Could not upload the attachment after multiple attempts: {last_error}"
        )

    def _upload_wait_seconds(self, attachment_path: str, kind: str) -> int:
        size_mb = os.path.getsize(attachment_path) / (1024 * 1024)
        if kind == "video":
            return max(20, min(WHATSAPP_MAX_UPLOAD_WAIT_SECONDS, int(size_mb * WHATSAPP_UPLOAD_SECONDS_PER_MB + 15)))
        if kind == "document":
            return max(WHATSAPP_AFTER_ATTACH_SECONDS, min(90, int(size_mb * 2 + 8)))
        return WHATSAPP_AFTER_ATTACH_SECONDS

    def _preview_is_open(self) -> bool:
        if self.driver is None:
            return False

        if self._whatsapp_error_visible():
            return False

        page = self.driver.page_source.lower()
        if "no preview available" in page and (".mp4" in page or "mp4" in page):
            return True

        preview_selectors = [
            '[data-testid="media-caption-input-container"]',
            '[data-testid="media-viewer"]',
            '[data-testid="media-preview"]',
            '[data-animate-media-viewer="true"]',
        ]
        for selector in preview_selectors:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if element.is_displayed():
                    return True

        send_buttons = self._find_preview_send_buttons()
        return bool(send_buttons)

    def _wait_for_attachment_preview(self) -> None:
        if self.driver is None:
            return

        WebDriverWait(self.driver, UPLOAD_WAIT_SECONDS).until(lambda _driver: self._preview_is_open())

        if self._whatsapp_error_visible():
            raise RuntimeError(
                "WhatsApp rejected the file. Videos must use Photos & videos and stay under 100 MB."
            )

        time.sleep(UI_PAUSE_MED)

    def _wait_until_preview_send_ready(self, attachment_path: str, kind: str) -> None:
        if self.driver is None:
            return

        deadline = time.time() + self._upload_wait_seconds(attachment_path, kind)
        filename = Path(attachment_path).name.lower()

        while time.time() < deadline:
            if self._whatsapp_error_visible():
                raise RuntimeError(
                    "WhatsApp rejected the file. Videos must use Photos & videos and stay under 100 MB."
                )
            if self._find_preview_send_buttons():
                return
            if self._preview_is_open():
                page = self.driver.page_source.lower()
                if filename in page or "no preview available" in page:
                    return
            time.sleep(1)

        if self._preview_is_open():
            return

        raise RuntimeError(
            "The attachment preview did not open. "
            "Keep the Chrome window maximized and try again."
        )

    def _get_preview_caption_box(self) -> WebElement | None:
        if self.driver is None:
            return None

        for root in self._media_overlay_roots():
            for box in root.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'):
                if box.is_displayed():
                    return box

        for container in self.driver.find_elements(
            By.CSS_SELECTOR, '[data-testid="media-caption-input-container"]'
        ):
            if not container.is_displayed():
                continue
            for box in container.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'):
                if box.is_displayed():
                    return box

        for box in self.driver.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'):
            if not box.is_displayed():
                continue
            in_main = self.driver.execute_script(
                "return arguments[0].closest('#main footer') !== null;", box
            )
            if not in_main:
                return box

        return None

    def _try_set_preview_caption(self, message: str) -> None:
        """Add caption if possible — video still sends without it."""
        if not message.strip() or self.driver is None:
            return

        self._clear_main_composer()
        caption_box = self._get_preview_caption_box()
        if caption_box is None:
            return

        try:
            self._javascript_click(caption_box)
            caption_box.send_keys(Keys.CONTROL, "a")
            caption_box.send_keys(Keys.BACKSPACE)
            import pyperclip

            pyperclip.copy(message)
            caption_box.send_keys(Keys.CONTROL, "v")
            self._clear_main_composer()
            time.sleep(UI_PAUSE_SHORT)
        except WebDriverException:
            pass

    def _clear_main_composer(self) -> None:
        """Remove stray text in the main chat box — prevents text-only sends."""
        if self.driver is None:
            return
        try:
            for box in self._find_message_composers():
                self._javascript_click(box)
                box.send_keys(Keys.CONTROL, "a")
                box.send_keys(Keys.BACKSPACE)
        except WebDriverException:
            pass

    def _media_overlay_roots(self) -> list[WebElement]:
        if self.driver is None:
            return []
        selectors = [
            '[data-animate-media-viewer="true"]',
            '[data-testid="media-viewer"]',
            '[data-testid="media-caption-input-container"]',
            '[data-testid="media-editor"]',
        ]
        roots: list[WebElement] = []
        seen: set[str] = set()
        for selector in selectors:
            for element in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if element.id not in seen and element.is_displayed():
                    seen.add(element.id)
                    roots.append(element)
        return roots

    def _find_preview_send_buttons(self) -> list[WebElement]:
        """Send on the video/document preview — never the main chat footer."""
        if self.driver is None:
            return []

        send_icon_css = (
            'span[data-icon="wds-ic-send-filled"], '
            'span[data-icon="send"], '
            'span[data-icon="send-light"]'
        )
        results: list[WebElement] = []
        seen: set[str] = set()

        for root in self._media_overlay_roots():
            for button in root.find_elements(By.CSS_SELECTOR, send_icon_css):
                if button.id not in seen and button.is_displayed():
                    seen.add(button.id)
                    results.append(button)

        for footer in self.driver.find_elements(By.CSS_SELECTOR, "footer"):
            if not footer.is_displayed():
                continue
            in_main = self.driver.execute_script(
                "return arguments[0].closest('#main') !== null;", footer
            )
            if in_main:
                continue
            for button in footer.find_elements(By.CSS_SELECTOR, send_icon_css):
                if button.id not in seen and button.is_displayed():
                    seen.add(button.id)
                    results.append(button)

        for button in self.driver.find_elements(By.CSS_SELECTOR, send_icon_css):
            if button.id in seen or not button.is_displayed():
                continue
            in_main = self.driver.execute_script(
                "return arguments[0].closest('#main footer') !== null;", button
            )
            if not in_main:
                seen.add(button.id)
                results.append(button)

        return results

    def _click_overlay_send_via_js(self) -> bool:
        if self.driver is None:
            return False
        clicked = self.driver.execute_script(
            """
            const icons = document.querySelectorAll(
                'span[data-icon="send"], span[data-icon="wds-ic-send-filled"], span[data-icon="send-light"]'
            );
            for (const icon of icons) {
                if (icon.closest('#main footer')) continue;
                const btn = icon.closest('[role="button"]') || icon.parentElement;
                if (btn && btn.offsetParent !== null) {
                    btn.click();
                    return true;
                }
            }
            const footers = document.querySelectorAll('footer');
            for (const footer of footers) {
                if (footer.closest('#main')) continue;
                const icon = footer.querySelector(
                    'span[data-icon="send"], span[data-icon="wds-ic-send-filled"], span[data-icon="send-light"]'
                );
                if (!icon) continue;
                const btn = icon.closest('[role="button"]') || icon.parentElement;
                if (btn) { btn.click(); return true; }
            }
            return false;
            """
        )
        return bool(clicked)

    def _click_preview_send_pyautogui(self) -> bool:
        """Last resort: click bottom-right where WhatsApp puts the green Send."""
        if system().lower() != "windows" or self.driver is None:
            return False
        try:
            import pyautogui

            pyautogui.FAILSAFE = False
            rect = self.driver.get_window_rect()
            x = rect["x"] + rect["width"] - 55
            y = rect["y"] + rect["height"] - 55
            pyautogui.click(x, y)
            time.sleep(1)
            return True
        except Exception:
            return False

    def _set_preview_caption(self, message: str) -> None:
        self._try_set_preview_caption(message)

    def _click_preview_send_button(self) -> None:
        if self.driver is None:
            return

        self._clear_main_composer()
        self._focus_browser_window()

        for _attempt in range(15):
            if not self._preview_is_open():
                return

            if self._click_overlay_send_via_js():
                time.sleep(1.5)
                if not self._preview_is_open():
                    return

            for button in self._find_preview_send_buttons():
                try:
                    self._click_element_or_parent(button)
                    time.sleep(1.5)
                    if not self._preview_is_open():
                        return
                except StaleElementReferenceException:
                    continue

            if _attempt >= 5 and self._click_preview_send_pyautogui():
                time.sleep(2)
                if not self._preview_is_open():
                    return

            time.sleep(2)

        if self._preview_is_open():
            raise RuntimeError(
                "Video preview is open but Send was not clicked. "
                "Keep Chrome maximized — do not touch the window during Auto Send."
            )

    def _last_outgoing_message_is_media(self) -> bool:
        if self.driver is None:
            return False

        outgoing = self.driver.find_elements(By.CSS_SELECTOR, "#main div.message-out")
        if not outgoing:
            return False

        last = outgoing[-1]
        media_selectors = (
            "video, "
            'span[data-icon="media-play"], '
            'span[data-icon="video-pip"], '
            'span[data-icon="document"], '
            'img[src*="blob:"], '
            '[data-testid="media-content"], '
            '[data-testid="video-thumb"]'
        )
        if last.find_elements(By.CSS_SELECTOR, media_selectors):
            return True

        blob = (last.text or "").lower()
        if any(ext in blob for ext in (".mp4", ".mov", ".pdf", ".jpg", ".png")):
            return True
        if "wedding invite" in blob:
            return True

        text = blob.strip()
        return not text

    def _verify_attachment_sent(self) -> None:
        if self.driver is None:
            return

        def send_complete(_driver: webdriver.Chrome) -> bool:
            if self._preview_is_open():
                return False
            return self._last_outgoing_message_is_media()

        try:
            WebDriverWait(self.driver, 90).until(send_complete)
        except TimeoutException as exc:
            if self._preview_is_open():
                raise RuntimeError(
                    "The video preview is still open — the attachment was not sent. "
                    "Large videos need more time. Keep the Chrome window maximized."
                ) from exc
            raise RuntimeError(
                "Only the text message was sent — the video did not go through. "
                "Try Auto Send again with the Chrome window maximized."
            ) from exc

    def _click_send_button(self) -> None:
        if self.driver is None:
            return

        main_footer_sends = self.driver.find_elements(
            By.CSS_SELECTOR,
            '#main footer span[data-icon="wds-ic-send-filled"], '
            '#main footer span[data-icon="send"]',
        )
        for button in main_footer_sends:
            if button.is_displayed():
                self._click_element_or_parent(button)
                time.sleep(1)
                return

        for button in self._find_preview_send_buttons():
            self._click_element_or_parent(button)
            time.sleep(1)
            return

        message_box = self._get_message_box()
        message_box.send_keys(Keys.ENTER)

    def _get_message_box(self) -> WebElement:
        if self.driver is None:
            raise RuntimeError("WhatsApp browser session is not started.")

        composers = self._find_message_composers()
        if composers:
            return composers[-1]
        raise RuntimeError("WhatsApp message box not found — chat may not be open.")

    def _send_attachment(self, attachment_path: str, message: str) -> None:
        kind = attachment_kind(attachment_path)
        self._clear_main_composer()
        self._upload_via_hidden_input(attachment_path, kind)
        self._wait_for_attachment_preview()
        self._wait_until_preview_send_ready(attachment_path, kind)
        self._set_preview_caption(message)
        self._click_preview_send_button()
        self._verify_attachment_sent()

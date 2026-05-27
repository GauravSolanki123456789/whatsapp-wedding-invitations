"""Reliable WhatsApp Web automation using Selenium element selectors."""

from __future__ import annotations

import os
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

CHROME_PROFILE_DIR = os.path.abspath(".chrome-whatsapp-profile")
CHAT_WAIT_SECONDS = WHATSAPP_PAGE_WAIT_SECONDS
LOGIN_WAIT_SECONDS = 180
UPLOAD_WAIT_SECONDS = WHATSAPP_MAX_UPLOAD_WAIT_SECONDS


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


def normalize_file_path(attachment_path: str) -> str:
    return os.path.abspath(attachment_path).replace("\\", "/")


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
    if "chat is not open" in message or "could not open whatsapp chat" in message:
        return (
            "WhatsApp chat did not open for this number. "
            "Close any extra WhatsApp tabs, keep the automation Chrome window "
            "maximized, and try again."
        )
    if "attach" in message and ("+" in message or "button" in message):
        return (
            "Could not find the WhatsApp attach (+) button. "
            "Close any open preview in the Chrome window, keep it maximized, "
            "wait for the chat to fully load, then try again."
        )
    if "click intercepted" in message or "starting chat" in message:
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


class WhatsAppSession:
    """One Chrome window reused for an entire send batch."""

    def __init__(self) -> None:
        self.driver: webdriver.Chrome | None = None

    def start(self) -> None:
        if self.driver is not None:
            return

        os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
        options = Options()
        options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1400,900")
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.maximize_window()
        self._hide_automation_flags()
        self.driver.get("https://web.whatsapp.com")
        self._wait_until_logged_in()

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
        if self.driver is not None:
            try:
                self.driver.quit()
            except WebDriverException:
                pass
            self.driver = None

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

        if attachment_path:
            self._open_conversation(mobile_number)
            self._focus_browser_window()
            self._focus_chat_footer()
            time.sleep(1.5)
        else:
            self.driver.get(conversation_url(mobile_number, message))
            self._wait_for_chat_ready()
            self._ensure_valid_number(mobile_number)

        if attachment_path:
            self._send_attachment(normalize_file_path(attachment_path), message)
        else:
            self._click_send_button()

        time.sleep(1.5)

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

    def _is_conversation_open(self) -> bool:
        """True when the main panel shows an active chat (composer or footer attach)."""
        if self.driver is None:
            return False

        if self._find_message_composers():
            return True

        if not self._has_chat_footer():
            return False

        attach_in_footer = self.driver.find_elements(
            By.CSS_SELECTOR,
            '#main footer span[data-icon="plus-rounded"], '
            '#main footer span[data-icon="plus"], '
            '#main footer span[data-icon="clip"]',
        )
        return any(button.is_displayed() for button in attach_in_footer)

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
                        time.sleep(2)
                        clicked = True
                        break
                if clicked:
                    break
            if not clicked:
                break
            if self._is_conversation_open():
                return

    def _open_conversation_via_search(self, mobile_number: str) -> None:
        if self.driver is None:
            return

        self.driver.get("https://web.whatsapp.com")
        self._focus_browser_window()
        time.sleep(2)

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
        search_box.send_keys(mobile_number)
        time.sleep(2.5)

        phone = phone_for_url(mobile_number)
        result_xpaths = [
            f"//span[@title='{mobile_number}']",
            f"//span[@title='+{phone}']",
            f"//span[contains(@title,'{phone[-10:]}')]",
            "//div[@role='listitem']//span[@dir='auto']",
            "//div[@role='listitem']",
        ]
        for xpath in result_xpaths:
            for element in self.driver.find_elements(By.XPATH, xpath):
                if element.is_displayed():
                    self._click_element_or_parent(element)
                    time.sleep(2)
                    if self._is_conversation_open():
                        return

        search_box.send_keys(Keys.ENTER)
        time.sleep(2)
        if self._is_conversation_open():
            return

        raise RuntimeError(f"Could not find {mobile_number} in WhatsApp search.")

    def _open_conversation(self, mobile_number: str) -> None:
        """Navigate to a phone number and ensure the chat composer is open."""
        if self.driver is None:
            return

        strategies = (
            self._open_conversation_via_direct_link,
            self._open_conversation_via_search,
        )
        last_error: Exception | None = None

        for strategy in strategies:
            for attempt in range(2):
                try:
                    strategy(mobile_number)
                    self._ensure_valid_number(mobile_number)
                    WebDriverWait(self.driver, 45).until(
                        lambda _driver: self._is_conversation_open()
                    )
                    self._focus_chat_footer()
                    time.sleep(2)
                    self._wait_for_footer_attach_button()
                    return
                except Exception as exc:
                    last_error = exc
                    if self._has_attachment_overlay():
                        self.dismiss_stale_ui()
                    time.sleep(2)

        raise RuntimeError(
            f"Could not open WhatsApp chat for {mobile_number}. "
            f"Keep the automation Chrome window visible and try again. ({last_error})"
        )

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

        try:
            WebDriverWait(self.driver, 40).until(
                lambda _driver: self._is_conversation_open()
            )
        except TimeoutException as exc:
            raise TimeoutException(
                "WhatsApp chat did not open. Keep the automation Chrome window "
                "maximized and wait for the conversation to load."
            ) from exc

        self._focus_chat_footer()
        time.sleep(2)
        self._wait_for_footer_attach_button()

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

        if not self._is_conversation_open():
            raise RuntimeError(
                "WhatsApp chat is not open — cannot attach files on the home screen."
            )

        self._focus_browser_window()
        self._focus_chat_footer()
        time.sleep(0.8)

        attach_buttons = self._find_attach_buttons()
        if not attach_buttons:
            message_box = self._get_message_box()
            ActionChains(self.driver).move_to_element(message_box).click().perform()
            time.sleep(0.8)
            attach_buttons = self._find_attach_buttons()

        for button in attach_buttons:
            try:
                self._click_element_or_parent(button)
                time.sleep(1.5)
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
            "//span[normalize-space()='Document' or contains(normalize-space(),'Photos')]",
        )
        return any(item.is_displayed() for item in menu_texts)

    def _wait_for_attach_menu(self) -> None:
        if self.driver is None:
            return

        menu_selectors = (
            '[data-testid="mi-document"], '
            '[data-testid="mi-attach-media"], '
            '[data-testid="attach-document"], '
            '[data-testid="attach-media"]'
        )
        WebDriverWait(self.driver, 12).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, menu_selectors))
        )
        time.sleep(0.5)

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

        try:
            self._prepare_file_input(file_input)
            file_input.send_keys(attachment_path)
            time.sleep(1.5)
            if self._whatsapp_error_visible():
                return False
            return True
        except WebDriverException:
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

    def _click_attach_menu_item(self, kind: str) -> bool:
        if self.driver is None or not self._is_conversation_open():
            return False

        footer_elements = self.driver.find_elements(By.CSS_SELECTOR, "#main footer")
        search_roots: list[WebElement] = footer_elements if footer_elements else []
        if self.driver:
            search_roots.append(self.driver.find_element(By.TAG_NAME, "body"))

        if kind == "document":
            selectors = [
                '[data-testid="attach-document"]',
                '[data-testid="mi-document"]',
                'li[data-testid="mi-document"]',
            ]
            xpaths = [
                "//li[@data-testid='mi-document']",
                "//span[@data-testid='attach-document']",
                "//span[normalize-space()='Document']/ancestor::li[1]",
            ]
        else:
            selectors = [
                '[data-testid="attach-media"]',
                '[data-testid="mi-attach-media"]',
                'li[data-testid="mi-attach-media"]',
            ]
            xpaths = [
                "//li[@data-testid='mi-attach-media']",
                "//span[@data-testid='attach-media']",
                "//span[contains(normalize-space(),'Photos')]/ancestor::li[1]",
                "//span[contains(normalize-space(),'Photos & videos')]/ancestor::li[1]",
            ]

        for root in search_roots:
            for selector in selectors:
                for item in root.find_elements(By.CSS_SELECTOR, selector):
                    if item.is_displayed():
                        self._click_element_or_parent(item)
                        time.sleep(1.5)
                        return True

        for xpath in xpaths:
            for item in self.driver.find_elements(By.XPATH, xpath):
                if item.is_displayed():
                    self._click_element_or_parent(item)
                    time.sleep(1.5)
                    return True

        return False

    def _upload_via_menu_inputs(self, attachment_path: str, kind: str) -> None:
        if self.driver is None:
            return

        if not self._click_attach_menu_item(kind):
            raise RuntimeError(f"Could not open the WhatsApp {kind} picker in the attach menu.")

        time.sleep(1.2)

        if kind == "document":
            selectors = [
                '[data-testid="attach-document"] input[type="file"]',
                '[data-testid="mi-document"] input[type="file"]',
                'li[data-testid="mi-document"] input[type="file"]',
                'input[type="file"][accept="*"]',
                'input[type="file"][accept*=".pdf"]',
                'input[type="file"][accept*="application"]',
            ]
            xpaths = [
                "//li[@data-testid='mi-document']//input[@type='file']",
                "//span[@data-testid='attach-document']/following::input[@type='file'][1]",
                "//span[normalize-space()='Document']/ancestor::li[1]//input[@type='file']",
            ]
        else:
            selectors = [
                '[data-testid="attach-media"] input[type="file"]',
                '[data-testid="mi-attach-media"] input[type="file"]',
                'li[data-testid="mi-attach-media"] input[type="file"]',
                'input[type="file"][accept*="image"]',
                'input[type="file"][accept*="video"]',
            ]
            xpaths = [
                "//li[@data-testid='mi-attach-media']//input[@type='file']",
                "//span[@data-testid='attach-media']/following::input[@type='file'][1]",
                "//span[contains(normalize-space(),'Photos')]/ancestor::li[1]//input[@type='file']",
            ]

        for selector in selectors:
            for file_input in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if self._file_input_matches_kind(file_input, kind):
                    if self._try_send_file_to_input(file_input, attachment_path):
                        return

        for xpath in xpaths:
            for file_input in self.driver.find_elements(By.XPATH, xpath):
                if self._file_input_matches_kind(file_input, kind):
                    if self._try_send_file_to_input(file_input, attachment_path):
                        return

        for file_input in self._collect_file_inputs():
            if self._file_input_matches_kind(file_input, kind):
                if self._try_send_file_to_input(file_input, attachment_path):
                    return

        raise RuntimeError("Could not find a WhatsApp file input in the attach menu.")

    def _upload_via_windows_dialog(self, attachment_path: str, kind: str) -> None:
        if system().lower() != "windows":
            raise RuntimeError("Native file dialog fallback is only supported on Windows.")

        import pyautogui
        import pyperclip

        if self.driver is None:
            return

        pyautogui.FAILSAFE = False

        if not self._click_attach_menu_item(kind):
            raise RuntimeError("Could not open the WhatsApp file picker menu item.")

        time.sleep(2.5)
        pyperclip.copy(normalize_file_path(attachment_path))
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.6)
        pyautogui.press("enter")
        time.sleep(2.5)

        if self._whatsapp_error_visible():
            raise RuntimeError("WhatsApp rejected the file after selecting it in the file dialog.")

    def _upload_via_hidden_input(self, attachment_path: str, kind: str) -> None:
        if self.driver is None:
            return

        if not os.path.isfile(attachment_path):
            raise FileNotFoundError(f"Attachment file not found: {attachment_path}")

        last_error: Exception | None = None

        for attempt in range(3):
            try:
                if not self._is_conversation_open():
                    raise RuntimeError("WhatsApp chat is not open.")

                self._focus_browser_window()
                self._focus_chat_footer()
                time.sleep(0.8)

                message_box = self._get_message_box()
                ActionChains(self.driver).move_to_element(message_box).click().perform()
                time.sleep(0.5)

                self._wait_for_footer_attach_button()
                self._open_attach_menu()
                self._wait_for_attach_menu()
                self._upload_via_menu_inputs(attachment_path, kind)
                time.sleep(2)
                if self._whatsapp_error_visible():
                    raise RuntimeError(
                        "WhatsApp rejected the file. Videos must use Photos & videos, not Document."
                    )
                return
            except Exception as exc:
                last_error = exc
                if self._has_attachment_overlay():
                    self.dismiss_stale_ui()
                time.sleep(1.5)

        try:
            if self._has_attachment_overlay():
                self.dismiss_stale_ui()
            self._focus_chat_footer()
            self._open_attach_menu()
            self._wait_for_attach_menu()
            self._upload_via_windows_dialog(attachment_path, kind)
            time.sleep(2)
            if self._whatsapp_error_visible():
                raise RuntimeError(
                    "WhatsApp rejected the file. Videos must use Photos & videos, not Document."
                )
            return
        except Exception as exc:
            last_error = exc

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

        time.sleep(2)

    def _wait_until_preview_send_ready(self, attachment_path: str, kind: str) -> None:
        if self.driver is None:
            return

        deadline = time.time() + self._upload_wait_seconds(attachment_path, kind)

        while time.time() < deadline:
            if self._whatsapp_error_visible():
                raise RuntimeError(
                    "WhatsApp rejected the file. Videos must use Photos & videos and stay under 100 MB."
                )
            if self._find_preview_send_buttons():
                return
            time.sleep(2)

        if self._find_preview_send_buttons():
            return

        raise RuntimeError(
            "The attachment preview opened but WhatsApp did not finish preparing the file. "
            "Large videos can take a few minutes — keep the Chrome window open and try again."
        )

    def _get_preview_caption_box(self) -> WebElement:
        if self.driver is None:
            raise RuntimeError("WhatsApp browser session is not started.")

        main_chat_boxes = self.driver.find_elements(
            By.CSS_SELECTOR, '#main footer div[contenteditable="true"]'
        )
        main_chat_box = main_chat_boxes[0] if main_chat_boxes else None

        containers = self.driver.find_elements(
            By.CSS_SELECTOR, '[data-testid="media-caption-input-container"]'
        )
        for container in containers:
            if not container.is_displayed():
                continue
            for box in container.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"]'):
                if box.is_displayed():
                    return box

        overlay_xpaths = [
            '//div[contains(@data-testid,"media")]//footer//div[@contenteditable="true"]',
            '//footer[.//span[@data-icon="send" or @data-icon="wds-ic-send-filled"]]//div[@contenteditable="true"]',
            '//div[contains(@class,"copyable")]//div[@contenteditable="true"]',
        ]
        for xpath in overlay_xpaths:
            for box in self.driver.find_elements(By.XPATH, xpath):
                if box.is_displayed() and box != main_chat_box:
                    return box

        raise RuntimeError("Attachment preview opened but caption box was not found.")

    def _set_preview_caption(self, message: str) -> None:
        if not message.strip() or self.driver is None:
            return

        caption_box = self._get_preview_caption_box()
        self._javascript_click(caption_box)
        caption_box.send_keys(Keys.CONTROL, "a")
        caption_box.send_keys(Keys.BACKSPACE)
        caption_box.send_keys(message)
        time.sleep(0.5)

    def _find_preview_send_buttons(self) -> list[WebElement]:
        if self.driver is None:
            return []

        send_selectors = [
            'span[data-icon="wds-ic-send-filled"]',
            'span[data-icon="send"]',
            '[data-testid="send"]',
            'button[aria-label="Send"]',
            'div[aria-label="Send"]',
        ]
        xpaths = [
            '//div[contains(@data-testid,"media")]//span[@data-icon="send" or @data-icon="wds-ic-send-filled"]',
            '//footer[.//span[@data-icon="send" or @data-icon="wds-ic-send-filled"]]//span[@data-icon="send" or @data-icon="wds-ic-send-filled"]',
            '//span[@data-icon="send" or @data-icon="wds-ic-send-filled"]',
        ]

        results: list[WebElement] = []
        seen: set[str] = set()

        for selector in send_selectors:
            for button in self.driver.find_elements(By.CSS_SELECTOR, selector):
                if button.id not in seen and button.is_displayed():
                    seen.add(button.id)
                    results.append(button)

        for xpath in xpaths:
            for button in self.driver.find_elements(By.XPATH, xpath):
                if button.id not in seen and button.is_displayed():
                    seen.add(button.id)
                    results.append(button)

        return results

    def _click_preview_send_button(self) -> None:
        if self.driver is None:
            return

        for attempt in range(6):
            buttons = self._find_preview_send_buttons()
            for button in reversed(buttons):
                try:
                    self._click_element_or_parent(button)
                    time.sleep(2)
                    if not self._preview_is_open():
                        return
                except StaleElementReferenceException:
                    continue

            try:
                caption_box = self._get_preview_caption_box()
                caption_box.send_keys(Keys.ENTER)
                time.sleep(2)
                if not self._preview_is_open():
                    return
            except RuntimeError:
                pass

            time.sleep(3)

        raise RuntimeError(
            "Could not click the send button in the attachment preview. "
            "Keep the Chrome window maximized and try again."
        )

    def _verify_attachment_sent(self) -> None:
        if self.driver is None:
            return

        def preview_closed(_driver: webdriver.Chrome) -> bool:
            if self._preview_is_open():
                return False
            return True

        try:
            WebDriverWait(self.driver, 60).until(preview_closed)
        except TimeoutException as exc:
            raise RuntimeError(
                "The file preview is still open — the attachment was not sent. "
                "Large videos need more time. Keep the Chrome window maximized and try again."
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
        self._upload_via_hidden_input(attachment_path, kind)
        self._wait_for_attachment_preview()
        self._wait_until_preview_send_ready(attachment_path, kind)
        self._set_preview_caption(message)
        self._click_preview_send_button()
        self._verify_attachment_sent()

import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pytest
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DATAMB_EMAIL = os.getenv("DATAMB_EMAIL")
DATAMB_PASSWORD = os.getenv("DATAMB_PASSWORD")


def _kill_stale_chrome() -> None:
    if sys.platform == "darwin":
        for proc in ("chromedriver", "Google Chrome for Testing"):
            try:
                subprocess.run(["pkill", "-9", "-f", proc], capture_output=True, timeout=5)
            except Exception:
                pass
    elif sys.platform.startswith("linux"):
        for proc in ("chromedriver", "chrome", "chromium"):
            try:
                subprocess.run(["pkill", "-9", "-f", proc], capture_output=True, timeout=5)
            except Exception:
                pass
    time.sleep(0.5)


def _make_fresh_driver(*, headless: bool = True, window_size: Tuple[int, int] = (1200, 900)) -> webdriver.Chrome:
    _kill_stale_chrome()
    tmp_profile = tempfile.mkdtemp(prefix="selenium_buffer_")
    chrome_options = Options()
    chrome_options.add_argument(f"--user-data-dir={tmp_profile}")
    chrome_options.add_argument("--no-first-run")
    chrome_options.add_argument("--no-default-browser-check")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--force-device-scale-factor=2")
    if headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(*window_size)
    driver._tmp_profile = tmp_profile
    return driver


def _quit_driver(driver) -> None:
    try:
        driver.quit()
    except Exception:
        pass
    tmp = getattr(driver, "_tmp_profile", None)
    if tmp and os.path.isdir(tmp):
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


def buffer_schedule_datetime_plus_two_minutes() -> Tuple[str, str]:
    now = datetime.now() + timedelta(minutes=2)
    schedule_date = now.strftime("%Y-%m-%d")
    hours = now.hour
    minutes = now.strftime("%M")
    ampm = "PM" if hours >= 12 else "AM"
    h12 = hours % 12
    if h12 == 0:
        h12 = 12
    schedule_time = f"{h12}:{minutes} {ampm}"
    return schedule_date, schedule_time


def check_post_scheduled_success(driver, timeout: int = 90) -> Tuple[bool, Optional[str]]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = driver.execute_script(
                """
                var body = document.body ? document.body.innerText.toLowerCase() : '';
                var keywords = ['are scheduled', 'is scheduled', 'has been sent',
                                'has been shared', 'has been published',
                                'added to queue', 'all done', 'hooray',
                                'post scheduled', 'post sent', 'post shared', 'post published',
                                'successfully scheduled', 'successfully sent',
                                'successfully shared', 'successfully published'];
                for (var i = 0; i < keywords.length; i++) {
                    if (body.indexOf(keywords[i]) !== -1) {
                        var link = document.querySelector('a[href*="/posts/"]');
                        var url = link ? link.getAttribute('href') : null;
                        return {success: true, url: url};
                    }
                }
                return null;
                """
            )
            if result and result.get("success"):
                view_post_url = result.get("url")
                if view_post_url and not view_post_url.startswith("http"):
                    view_post_url = "https://publish.buffer.com" + view_post_url
                return True, view_post_url
        except Exception:
            pass
        time.sleep(0.5)
    return False, None


def set_buffer_schedule_time_combobox_input(driver, time_input_el, time_str: str) -> None:
    cmd_key = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", time_input_el)
    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(time_input_el))
    time_input_el.click()
    time.sleep(0.2)
    try:
        driver.execute_script(
            """
            var el = arguments[0];
            el.focus();
            var v = el.value || '';
            try { el.setSelectionRange(v.length, v.length); } catch (e) {}
            """,
            time_input_el,
        )
        prev = time_input_el.get_attribute("value") or ""
        n_erase = max(len(prev) + 12, 32)
        actions = ActionChains(driver)
        for _ in range(min(n_erase, 64)):
            actions.send_keys(Keys.BACKSPACE)
        actions.perform()
    except Exception:
        pass
    time.sleep(0.1)
    try:
        leftover = (time_input_el.get_attribute("value") or "").strip()
        if leftover:
            ac = ActionChains(driver)
            ac.click(time_input_el)
            ac.key_down(cmd_key).send_keys("a").key_up(cmd_key)
            for _ in range(48):
                ac.send_keys(Keys.BACKSPACE)
            ac.perform()
    except Exception:
        pass
    time.sleep(0.05)
    try:
        driver.execute_script(
            """
            var el = arguments[0];
            el.focus();
            try {
                var desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (desc && desc.set) { desc.set.call(el, ''); }
                else { el.value = ''; }
            } catch (e) { el.value = ''; }
            try {
                el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteContentBackward', data: null }));
            } catch (e) {
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            time_input_el,
        )
    except Exception:
        pass
    time.sleep(0.1)
    time_input_el.click()
    time_input_el.send_keys(time_str)
    time.sleep(0.3)
    try:
        listbox_id = time_input_el.get_attribute("aria-controls") or ""
        option_clicked = False
        if listbox_id:
            try:
                options = driver.find_elements(By.CSS_SELECTOR, f"#{listbox_id} [role='option']")
                for opt in options:
                    if opt.is_displayed() and opt.text.strip() == time_str.strip():
                        opt.click()
                        option_clicked = True
                        break
            except Exception:
                pass
        if not option_clicked:
            options = driver.find_elements(By.CSS_SELECTOR, "[role='option']")
            for opt in options:
                if opt.is_displayed() and opt.text.strip() == time_str.strip():
                    opt.click()
                    option_clicked = True
                    break
        if not option_clicked:
            time_input_el.send_keys(Keys.ENTER)
    except Exception:
        try:
            time_input_el.send_keys(Keys.ENTER)
        except Exception:
            pass
    time.sleep(0.2)


def _login_buffer(driver, email: str, password: str) -> None:
    driver.get("https://login.buffer.com/login")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body, input[name='email'], button"))
        )
    except Exception:
        pass
    try:
        accept = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Accept All') or contains(text(), 'Accept')]")
            )
        )
        accept.click()
        time.sleep(0.3)
    except Exception:
        pass

    email_field = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.NAME, "email")))
    email_field.clear()
    email_field.click()
    email_field.send_keys(email)

    password_field = WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.NAME, "password")))
    password_field.clear()
    password_field.click()
    password_field.send_keys(password)

    login_button = None
    for xpath in (
        "//button[@type='submit']",
        "//button[contains(text(), 'Log In')]",
        "//button[contains(text(), 'Log in')]",
    ):
        try:
            login_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            if login_button:
                break
        except Exception:
            continue
    if not login_button:
        raise RuntimeError("Buffer login button not found")
    login_button.click()
    WebDriverWait(driver, 45).until(EC.url_contains("publish.buffer.com"))


def _open_composer(driver) -> None:
    if "publish.buffer.com" not in driver.current_url:
        driver.get("https://publish.buffer.com")
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "body, button, [data-testid*='new-post'], .new-post-button")
            )
        )
    except Exception:
        pass
    try:
        new_post = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'New Post')]"))
        )
        driver.execute_script(
            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", new_post
        )
        time.sleep(0.3)
        new_post.click()
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button.publish_channelItem_BUVOd"))
        )
    except Exception:
        driver.get("https://publish.buffer.com/composer")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "button.publish_channelItem_BUVOd, textarea, .composer")
            )
        )


def _select_twitter_only(driver) -> None:
    for btn in driver.find_elements(By.CSS_SELECTOR, "button.publish_channelItem_BUVOd[aria-pressed='true']"):
        try:
            btn.click()
        except Exception:
            pass
    time.sleep(0.2)
    channel_buttons = driver.find_elements(By.CSS_SELECTOR, "button.publish_channelItem_BUVOd")
    for button in channel_buttons:
        try:
            button.find_element(By.CSS_SELECTOR, "div[data-channel='twitter']")
            if button.get_attribute("aria-pressed") != "true":
                button.click()
                try:
                    WebDriverWait(driver, 2).until(
                        lambda d, b=button: b.get_attribute("aria-pressed") == "true"
                    )
                except Exception:
                    pass
            return
        except Exception:
            continue
    try:
        alt_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='twitter channel']")
        if alt_btn.get_attribute("aria-pressed") != "true":
            alt_btn.click()
    except Exception as exc:
        raise RuntimeError("Could not select Twitter channel in Buffer") from exc


def _copy_text_to_clipboard(text: str, driver=None) -> bool:
    """
    Set clipboard contents so Ctrl+V triggers a real paste event.
    Primary: CDP command (works in headless CI with no OS clipboard).
    Fallback: OS clipboard tools (pbcopy/xclip/xsel).
    """
    if driver is not None:
        try:
            driver.execute_cdp_cmd(
                "Browser.setPermission",
                {"permission": {"name": "clipboard-read"}, "setting": "granted",
                 "origin": driver.execute_script("return window.location.origin")},
            )
            driver.execute_cdp_cmd(
                "Browser.setPermission",
                {"permission": {"name": "clipboard-write"}, "setting": "granted",
                 "origin": driver.execute_script("return window.location.origin")},
            )
        except Exception:
            pass
        try:
            driver.execute_script(
                "await navigator.clipboard.writeText(arguments[0]);", text
            )
            return True
        except Exception:
            pass
        try:
            driver.execute_cdp_cmd(
                "Runtime.evaluate",
                {"expression": f"navigator.clipboard.writeText({repr(text)})",
                 "awaitPromise": True},
            )
            return True
        except Exception:
            pass
    try:
        raw = text.encode("utf-8")
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=raw, check=True)
        elif sys.platform == "win32":
            subprocess.run(["clip"], input=text, text=True, shell=True, check=True)
        else:
            for argv in (["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
                try:
                    subprocess.run(argv, input=raw, check=True)
                    return True
                except FileNotFoundError:
                    continue
            return False
        return True
    except Exception:
        return False


def _composer_read_text(driver, el) -> str:
    return (
        driver.execute_script(
            """
            const root = arguments[0];
            function read(n) {
                if (!n) return '';
                if (n.tagName === 'TEXTAREA' || n.tagName === 'INPUT') return (n.value || '').trim();
                return (n.innerText || n.textContent || '').trim();
            }
            let t = read(root);
            if (t.length > 0) return t;
            const a = document.activeElement;
            if (a && root && (root === a || root.contains(a))) {
                const u = read(a);
                if (u.length > 0) return u;
            }
            return t;
            """,
            el,
        )
        or ""
    )


def _composer_text_looks_ok(driver, el, expected: str) -> bool:
    got = _composer_read_text(driver, el).strip()
    exp = expected.strip()
    if not exp:
        return True
    if len(exp) <= 12:
        return got == exp
    return len(got) >= max(12, int(0.35 * len(exp)))


def _find_primary_composer(driver):
    """Largest editable in/near composer; pierces shadow roots; prefers composer/editor ancestors."""
    el = driver.execute_script(
        """
        function badHint(el) {
            var p = ((el.getAttribute('placeholder') || '') + ' ' + (el.getAttribute('aria-label') || ''))
                .toLowerCase();
            return p.indexOf('search') >= 0 || p.indexOf('filter') >= 0;
        }
        function composerWeight(el) {
            var n = el;
            for (var i = 0; i < 18 && n; i++) {
                var cls = (n.className && String(n.className).toLowerCase()) || '';
                var tid = ((n.getAttribute && n.getAttribute('data-testid')) || '').toLowerCase();
                if (tid.indexOf('composer') >= 0 || cls.indexOf('composer') >= 0) return 4;
                if (cls.indexOf('draft') >= 0 || cls.indexOf('editor') >= 0 || cls.indexOf('slate') >= 0) return 3;
                if (cls.indexOf('publish') >= 0) return 2;
                n = n.parentElement;
            }
            return 1;
        }
        var nodes = [];
        document.querySelectorAll('textarea, [contenteditable="true"]').forEach(function(el) {
            if (badHint(el)) return;
            var r = el.getBoundingClientRect();
            if (r.width < 40 || r.height < 16) return;
            var st = window.getComputedStyle(el);
            if (st.display === 'none' || st.visibility === 'hidden' || parseFloat(st.opacity || '1') === 0) return;
            if (r.bottom <= 2 || r.top >= window.innerHeight - 2) return;
            var area = r.width * r.height;
            if (area < 300) return;
            var w = composerWeight(el);
            nodes.push({ el: el, score: area * w });
        });
        nodes.sort(function(a, b) { return b.score - a.score; });
        return nodes.length ? nodes[0].el : null;
        """
    )
    if el is not None:
        return el
    scored = []
    for sel in ("textarea", "[contenteditable='true']"):
        for cand in driver.find_elements(By.CSS_SELECTOR, sel):
            try:
                if not cand.is_displayed():
                    continue
                r = cand.rect
                area = r.get("height", 0) * r.get("width", 0)
                if area < 800:
                    continue
                scored.append((area, cand))
            except Exception:
                continue
    if not scored:
        raise RuntimeError("Buffer: could not find main composer text field")
    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def _set_native_textarea_react(driver, el, text: str) -> None:
    """React-controlled textareas ignore raw .value unless _valueTracker is synced."""
    driver.execute_script(
        """
        const el = arguments[0], value = arguments[1];
        const last = el.value;
        const desc = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value');
        if (desc && desc.set) { desc.set.call(el, value); }
        else { el.value = value; }
        try {
            const tracker = el._valueTracker;
            if (tracker) { tracker.setValue(last); }
        } catch (e) {}
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        el,
        text,
    )


def _js_synthetic_paste(driver, el, text: str) -> bool:
    """Fire a synthetic paste event with DataTransfer — works in headless without OS clipboard."""
    try:
        driver.execute_script(
            """
            const el = arguments[0], text = arguments[1];
            el.focus();
            const dt = new DataTransfer();
            dt.setData('text/plain', text);
            const pe = new ClipboardEvent('paste', {
                bubbles: true, cancelable: true, clipboardData: dt
            });
            el.dispatchEvent(pe);
            """,
            el,
            text,
        )
        return True
    except Exception:
        return False


def _set_composer_text(driver, post_text: str) -> None:
    el = _find_primary_composer(driver)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable(el))
    cmd = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL

    def focus_clear() -> None:
        el.click()
        time.sleep(0.35)
        ActionChains(driver).click(el).key_down(cmd).send_keys("a").key_up(cmd).pause(0.1).send_keys(Keys.BACKSPACE).perform()
        time.sleep(0.2)

    focus_clear()

    # Method 1: CDP clipboard + Ctrl/Cmd+V
    if _copy_text_to_clipboard(post_text, driver=driver):
        driver.execute_script("arguments[0].focus(); arguments[0].click();", el)
        time.sleep(0.15)
        ActionChains(driver).key_down(cmd).send_keys("v").key_up(cmd).perform()
        time.sleep(0.55)
        if _composer_text_looks_ok(driver, el, post_text):
            return

    # Method 2: synthetic paste event (headless-friendly, no OS clipboard needed)
    focus_clear()
    _js_synthetic_paste(driver, el, post_text)
    time.sleep(0.4)
    if _composer_text_looks_ok(driver, el, post_text):
        return

    # Method 3: execCommand insertText (works for contenteditable)
    focus_clear()
    driver.execute_script(
        """
        const el = arguments[0], t = arguments[1];
        el.focus();
        document.execCommand('selectAll', false, null);
        document.execCommand('insertText', false, t);
        """,
        el,
        post_text,
    )
    time.sleep(0.3)
    if _composer_text_looks_ok(driver, el, post_text):
        return

    # Method 4: React textarea setter
    tag = (el.tag_name or "").lower()
    if tag == "textarea":
        focus_clear()
        _set_native_textarea_react(driver, el, post_text)
        time.sleep(0.3)
        if _composer_text_looks_ok(driver, el, post_text):
            return

    # Method 5: direct send_keys
    focus_clear()
    el.send_keys(post_text)
    time.sleep(0.35)
    if not _composer_text_looks_ok(driver, el, post_text):
        raise RuntimeError(
            "Buffer: main composer text did not stick after all methods; "
            "check composer selectors or run with visible Chrome to see focus."
        )


def _upload_single_image(driver, image_path: str) -> None:
    abs_path = os.path.abspath(image_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(abs_path)
    file_input = None
    for sel in (
        "input[type='file']",
        "[data-testid*='media-upload'] input[type='file']",
        "[data-testid*='image-upload'] input[type='file']",
    ):
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if el.get_attribute("type") == "file":
                    file_input = el
                    break
            if file_input:
                break
        except Exception:
            continue
    if not file_input:
        raise RuntimeError("Buffer: no file input found for image upload")
    file_input.send_keys(abs_path)
    time.sleep(2.5)
    try:
        WebDriverWait(driver, 20).until(
            EC.any_of(
                EC.presence_of_element_located((By.XPATH, "//button[.//span[contains(text(), 'Add description')]]")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='blob'], img[src*='buffer']")),
            )
        )
    except Exception:
        pass


def _add_alt_text(driver, alt_text: str) -> None:
    if not alt_text.strip():
        return
    try:
        target_image = None
        for selector in (
            "img[src*='blob']", "img[src*='data:']", "img[src*='buffer']",
            ".publish_mediaContainer img", "[class*='media'] img", "img",
        ):
            try:
                for img in driver.find_elements(By.CSS_SELECTOR, selector):
                    if img.is_displayed() and img.size.get("width", 0) > 50 and img.size.get("height", 0) > 50:
                        target_image = img
                        break
                if target_image:
                    break
            except Exception:
                continue
        if not target_image:
            return

        driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", target_image)
        time.sleep(0.3)

        driver.execute_script(
            """
            var img = arguments[0];
            var container = img.closest('[class*="media"], [class*="Media"], [class*="publish_media"]');
            if (!container) container = img.parentElement;
            ['mouseenter','mouseover','mousemove'].forEach(function(t){
                var ev = new MouseEvent(t,{bubbles:true,cancelable:true,view:window});
                container.dispatchEvent(ev);
                img.dispatchEvent(ev);
            });
            """,
            target_image,
        )
        time.sleep(0.5)

        alt_button = driver.execute_script(
            """
            var allButtons = document.querySelectorAll('button.publish_action_ZlY7D');
            for (var i = 0; i < allButtons.length; i++) {
                var btn = allButtons[i];
                var span = btn.querySelector('span.publish_base_D9VRM');
                if (span && span.textContent.includes('Add description')) {
                    var st = window.getComputedStyle(btn);
                    if (st.display !== 'none' && st.visibility !== 'hidden' && st.opacity !== '0') return btn;
                }
            }
            return null;
            """
        )
        if not alt_button:
            for b in driver.find_elements(By.XPATH, "//button[.//span[contains(text(), 'Add description')]]"):
                try:
                    vis = driver.execute_script(
                        "var s=window.getComputedStyle(arguments[0]);"
                        "return s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0';",
                        b,
                    )
                    if vis:
                        alt_button = b
                        break
                except Exception:
                    continue
        if not alt_button:
            for b in driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='Alt'], button[aria-label*='alt'], button.publish_actionButton_hpIK-"):
                if b.is_displayed():
                    alt_button = b
                    break
        if not alt_button:
            return

        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", alt_button)
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable(alt_button))
            alt_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", alt_button)
        time.sleep(0.5)

        cmd = Keys.COMMAND if sys.platform == "darwin" else Keys.CONTROL
        alt_input = None
        try:
            alt_input = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "textarea[placeholder*='description'], textarea[placeholder*='alt'], "
                    "input[placeholder*='description'], input[placeholder*='alt'], "
                    "[aria-label*='alt'] textarea, [aria-label*='description'] textarea"
                ))
            )
        except Exception:
            pass
        if not alt_input:
            try:
                alt_input = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//div[@role='dialog']//textarea | "
                        "//div[@role='dialog']//*[@contenteditable='true']"
                    ))
                )
            except Exception:
                pass

        if alt_input:
            alt_input.click()
            time.sleep(0.15)
            try:
                alt_input.clear()
            except Exception:
                pass
            typed = False
            if _copy_text_to_clipboard(alt_text, driver=driver):
                driver.execute_script("arguments[0].focus(); arguments[0].click();", alt_input)
                time.sleep(0.1)
                ActionChains(driver).key_down(cmd).send_keys("v").key_up(cmd).perform()
                time.sleep(0.4)
                typed = True
            if not typed:
                _js_synthetic_paste(driver, alt_input, alt_text)
                time.sleep(0.3)
                typed = True
            got = driver.execute_script(
                "return (arguments[0].value || arguments[0].textContent || '').trim();",
                alt_input,
            )
            if not got:
                _set_native_textarea_react(driver, alt_input, alt_text)
                time.sleep(0.2)
            got = driver.execute_script(
                "return (arguments[0].value || arguments[0].textContent || '').trim();",
                alt_input,
            )
            if not got:
                alt_input.send_keys(alt_text)
        else:
            ActionChains(driver).send_keys(alt_text).perform()

        time.sleep(0.3)

        for selector_type, selector in (
            (By.CSS_SELECTOR, "button.publish_saveButton_iFO4s"),
            (By.CSS_SELECTOR, "button[class*='publish_saveButton']"),
            (By.XPATH, "//button[contains(text(), 'Save')]"),
        ):
            try:
                save_btn = WebDriverWait(driver, 4).until(EC.element_to_be_clickable((selector_type, selector)))
                if save_btn and save_btn.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", save_btn)
                    save_btn.click()
                    time.sleep(0.5)
                    return
            except Exception:
                continue
        ActionChains(driver).send_keys(Keys.ENTER).perform()
    except Exception:
        pass


def _add_thread_reply(driver, reply_text: str) -> None:
    if not reply_text.strip():
        return
    thread_button = None
    for sel in (
        (By.CSS_SELECTOR, "button[data-testid='add-post-to-thread-button']"),
        (By.XPATH, "//button[contains(., 'Start Thread')]"),
        (By.XPATH, "//button[contains(., 'Add another post')]"),
    ):
        try:
            thread_button = driver.find_element(sel[0], sel[1])
            if thread_button.is_displayed():
                break
        except Exception:
            thread_button = None
    if not thread_button:
        return
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", thread_button)
    WebDriverWait(driver, 10).until(EC.element_to_be_clickable(thread_button))
    try:
        thread_button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", thread_button)
    time.sleep(0.65)
    tboxes = [t for t in driver.find_elements(By.CSS_SELECTOR, "textarea") if t.is_displayed()]
    if len(tboxes) >= 2:
        thread_el = tboxes[-1]
    elif tboxes:
        thread_el = tboxes[0]
    else:
        boxes = [b for b in driver.find_elements(By.CSS_SELECTOR, "[contenteditable='true']") if b.is_displayed()]
        thread_el = boxes[-1] if boxes else None
    if not thread_el:
        return
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", thread_el)
    thread_el.click()
    time.sleep(0.2)
    thread_el.send_keys(reply_text)
    time.sleep(0.2)


def _publish_now(driver) -> None:
    """Click 'Next Available' dropdown → 'Now' → then 'Publish Now' button."""
    dd = driver.execute_script(
        """
        var btns = document.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            var t = (btns[i].innerText || '').trim();
            if (t.indexOf('Next Available') >= 0) {
                var r = btns[i].getBoundingClientRect();
                if (r.width > 0 && r.height > 0) return btns[i];
            }
        }
        return null;
        """
    )
    if not dd:
        for xp in (
            "//button[contains(., 'Next Available')]",
            "//*[@role='button'][contains(., 'Next Available')]",
        ):
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        dd = el
                        break
                if dd:
                    break
            except Exception:
                continue
    if not dd:
        raise RuntimeError("Buffer: 'Next Available' dropdown not found")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", dd)
    dd.click()
    time.sleep(0.6)

    now_btn = None
    for xp in (
        "//button[normalize-space(.)='Now']",
        "//div[normalize-space(.)='Now' and not(descendant::div)]",
        "//span[normalize-space(.)='Now']",
        "//*[normalize-space(.)='Now' and string-length(normalize-space(.))<=4]",
        "//button[contains(., 'Share now')]",
        "//button[contains(., 'right away')]",
    ):
        try:
            for el in driver.find_elements(By.XPATH, xp):
                if el.is_displayed():
                    now_btn = el
                    break
            if now_btn:
                break
        except Exception:
            continue
    if not now_btn:
        raise RuntimeError("Buffer: 'Now' option not found in schedule dropdown")
    now_btn.click()
    time.sleep(0.6)

    pub = driver.execute_script(
        """
        var btns = document.querySelectorAll('button');
        var targets = ['Publish Now', 'Share Now', 'Send Now', 'Post Now'];
        for (var i = 0; i < btns.length; i++) {
            var t = (btns[i].innerText || '').trim();
            for (var j = 0; j < targets.length; j++) {
                if (t === targets[j]) {
                    var r = btns[i].getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) return btns[i];
                }
            }
        }
        return null;
        """
    )
    if not pub:
        for xp in (
            "//button[contains(text(), 'Publish Now')]",
            "//button[contains(text(), 'Share Now')]",
            "//button[contains(text(), 'Send Now')]",
            "//button[contains(text(), 'Post Now')]",
            "//button[contains(text(), 'Publish')]",
        ):
            try:
                el = driver.find_element(By.XPATH, xp)
                if el and el.is_displayed():
                    pub = el
                    break
            except Exception:
                continue
    if not pub:
        raise RuntimeError("Buffer: 'Publish Now' button not found")
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", pub)
    try:
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable(pub))
        pub.click()
    except Exception:
        driver.execute_script("arguments[0].click();", pub)
    time.sleep(1)


def schedule_twitter_post_via_buffer(
    driver,
    post_text: str,
    image_path: str,
    alt_text: Optional[str] = None,
    reply_text: Optional[str] = None,
) -> None:
    email = os.environ.get("BUFFER_EMAIL", "").strip()
    password = os.environ.get("BUFFER_PASSWORD", "").strip()
    if not email or not password:
        raise RuntimeError("Set BUFFER_EMAIL and BUFFER_PASSWORD for Buffer posting")

    _login_buffer(driver, email, password)
    _open_composer(driver)
    _select_twitter_only(driver)
    _upload_single_image(driver, image_path)
    _set_composer_text(driver, post_text)
    if alt_text:
        _add_alt_text(driver, alt_text)
    if reply_text:
        _add_thread_reply(driver, reply_text)
    _publish_now(driver)

    ok, _url = check_post_scheduled_success(driver, timeout=90)
    if not ok:
        raise RuntimeError("Buffer: success confirmation not detected after scheduling")


class TestUntitled:
    def setup_method(self, method):
        self.driver = _make_fresh_driver(headless=True)

    def teardown_method(self):
        _quit_driver(self.driver)
        
    def capture_first_five_lines(self):
        body_element = self.driver.find_element(By.TAG_NAME, "body")
        body_text = body_element.text
    # Split the text into lines and capture the first 5 lines
        lines = body_text.splitlines()
        specific_lines = "\n".join(lines[4:9])
    
    # Replace the specified text
        replacements = {
        "1. ": "🥇 ",
        "2. ": "🥈 ",
        "3. ": "🥉 ",
        "4. ": "🏅 ",
        "5. ": "🏅 ",
        ") ": ") — "
    }
    
        for old, new in replacements.items():
            specific_lines = specific_lines.replace(old, new)

        return specific_lines

    
    def test_untitled(self):
        self.driver.get("https://datamb.football/proindex/")
        time.sleep(1)
        self.driver.set_window_size(976, 797)
        assert DATAMB_EMAIL and DATAMB_PASSWORD, (
            "Set DATAMB_EMAIL and DATAMB_PASSWORD (e.g. GitHub repo secrets)."
        )
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "eml"))
        ).send_keys(DATAMB_EMAIL)

        self.driver.find_element(By.NAME, "pwd").send_keys(DATAMB_PASSWORD)
        self.driver.find_element(By.CSS_SELECTOR, ".SFfrm button").click()
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "metric"))
        )



        position_options = ["Goalkeeper", "Centre-back", "Full-back", "Midfielder", "Winger", "Striker", "All positions"]
        weights2 = [0.03, 0.09, 0.09, 0.21, 0.18, 0.17, 0.23]  # Adjust position weights

        selected_position = random.choices(position_options, weights=weights2, k=1)[0]
        # Adjust metrics
        if selected_position == "Goalkeeper":
            metric_options = [
                "Possessions won per 90", "Sliding tackles per 90", "Sliding tackles (PAdj)",
                "Interceptions per 90", "Interceptions (PAdj)",
                "Aerial duels won %", "Defensive duels won per 90", "Progressive passes per 90",
                "Passes completed per 90", "Short passes completed per 90",
                "Pass completion %", "Short pass completion %", "Long pass accuracy %",
                "Aerial duels won per 90", "Saves per 90", "Shots conceded per 90",
                "xG conceded per 90", "Prevented goals per 90", "Save percentage %"
            ]
        elif selected_position == "Centre-back":
            metric_options = [
                "Possessions won per 90", "Sliding tackles per 90", "Sliding tackles (PAdj)",
                "Interceptions per 90", "Interceptions (PAdj)", "Defensive duels won %",
                "Aerial duels won %", "Defensive duels won per 90", "Aerial duels won per 90",
                "Possession +/-", "Possessions won - lost per 90", "Progressive actions per 90",
                "Progressive action rate", "Key passes per 90", "Progressive carries per 90",
                "Ball-carrying frequency", "Through passes per 90", "Passes to final third per 90",
                "Passes completed per 90", "Forward passes completed per 90", "Long passes completed per 90",
                "Progressive passes completed per 90", "Pass completion %", "Forward pass completion %",
                "Progressive pass accuracy %"
            ]
        elif selected_position == "Full-back":
            metric_options = [
                "Possessions won per 90", "Sliding tackles per 90", "Sliding tackles (PAdj)",
                "Interceptions per 90", "Interceptions (PAdj)", "Defensive duels won %",
                "Aerial duels won %", "Defensive duels won per 90", "Aerial duels won per 90",
                "xG per 90", "xG per 100 touches", "Duels won %", "Duels won per 90",
                "Possession +/-", "Possessions won - lost per 90", "Progressive actions per 90",
                "Touches per 90", "Progressive action rate", "xG+xA per 90", "npxG+xA per 90",
                "xA per 90", "xA per 100 passes", "Shot assists per 90", "Key passes per 90",
                "Deep completions per 90", "Chance creation ratio", "Crosses per 90",
                "Accurate crosses per 90", "Offensive duels won per 90", "Offensive duels won %",
                "Successful dribbles per 90", "Dribble success rate %", "Dribbles per 100 touches",
                "Progressive carries per 90", "Ball-carrying frequency", "Pass completion %",
                "Forward pass completion %", "Pass completion (to final third) %",
                "Pass completion (to penalty box) %", "Progressive pass accuracy %",
                "Progressive passes (PAdj)", "Passes to penalty box per 90", "Passes per 90",
                "Forward passes per 90", "Passes to final third per 90",
                "Progressive passes per 90", "Passes completed per 90", "Forward passes completed per 90",
                "Accurate passes to final third per 90",
                "Through passes completed per 90", "Progressive passes completed per 90"
            ]
        elif selected_position == "Midfielder":
            metric_options = [
                "Possessions won per 90", "Sliding tackles per 90", "Sliding tackles (PAdj)",
                "Interceptions per 90", "Interceptions (PAdj)", "Defensive duels won %",
                "Aerial duels won %", "Defensive duels won per 90", "Aerial duels won per 90",
                "Duels won %", "Duels won per 90", "Possession +/-", "Possessions won - lost per 90",
                "Progressive actions per 90", "Touches per 90", "Progressive action rate",
                "xG+xA per 90", "npxG+xA per 90", "xA per 90", "xA per 100 passes",
                "Shot assists per 90", "Key passes per 90", "Deep completions per 90",
                "Chance creation ratio", "Crosses per 90", "Accurate crosses per 90",
                "Assists - xA per 90", "Pre-assists per 90", "Fouls suffered per 90",
                "Successful dribbles per 90", "Dribble success rate %", "Progressive carries per 90",
                "Ball-carrying frequency", "xG per 90", "npxG per 90", "Goals per 100 touches",
                "NPG+A per 90", "Pass completion %", "Forward pass completion %",
                "Pass completion (to final third) %", "Pass completion (to penalty box) %",
                "Progressive pass accuracy %", "Forward pass ratio", "Backward pass ratio",
                "Progressive passes (PAdj)", "Passes to penalty box per 90", "Passes per 90",
                "Forward passes per 90", "Long passes per 90", "Passes to final third per 90",
                "Through passes per 90", "Progressive passes per 90", "Passes completed per 90",
                "Forward passes completed per 90", "Long passes completed per 90",
                "Accurate passes to final third per 90", "Through passes completed per 90",
                "Progressive passes completed per 90"
            ]
        elif selected_position == "Winger":
            metric_options = [
                "Progressive actions per 90", "Touches per 90", "Progressive action rate",
                "xG+xA per 90", "npxG+xA per 90", "xA per 90", "xA per 100 passes",
                "Shot assists per 90", "Key passes per 90", "Deep completions per 90",
                "Chance creation ratio", "Crosses per 90", "Accurate crosses per 90",
                "Assists - xA per 90", "Pre-assists per 90", "Fouls suffered per 90",
                "Offensive duels won per 90", "Offensive duels won %", "Successful dribbles per 90",
                "Dribble success rate %", "Dribbles per 100 touches", "Progressive carries per 90",
                "Ball-carrying frequency", "Passes to penalty box per 90", "Through passes per 90",
                "Progressive passes per 90", "Through passes completed per 90", "Progressive pass accuracy %",
                "Shots per 90", "Shots on target per 90", "xG per 90", "npxG per 90",
                "xG per 100 touches", "Goals per 100 touches",
                "NPG+A per 90", "Goals - xG per 90", "Shot frequency", "Touches in box per 90"
            ]
        elif selected_position == "Striker":
            metric_options = [
                "Aerial duels won %", "Aerial duels won per 90", "Duels won %",
                "xG+xA per 90", "npxG+xA per 90", "xA per 90", "xA per 100 passes",
                "Successful dribbles per 90", "Dribbles per 100 touches", "Progressive carries per 90",
                "Ball-carrying frequency", "Pass completion %", "Pass completion (to penalty box) %",
                "Shots per 90", "Shots on target per 90", "xG per 90", "npxG per 90",
                "xG per 100 touches", "xG/Shot", "npxG/Shot", "Goals per 100 touches",
                "NPG+A per 90", "Goal conversion %",
                "Goals - xG per 90", "Shot frequency", "Touches in box per 90"
            ]
        elif selected_position == "All positions":
            metric_options = [
                "Possessions won per 90","Sliding tackles per 90","Sliding tackles (PAdj)","Interceptions per 90","Interceptions (PAdj)","Defensive duels won per 90","Aerial duels won per 90","Duels won per 90","Possession +/-","Possessions won - lost per 90","Progressive actions per 90","Touches per 90","Progressive action rate","xG+xA per 90","npxG+xA per 90","Assists per 90","xA per 90","xA per 100 passes","Shot assists per 90","Key passes per 90","Deep completions per 90","Chance creation ratio","Crosses per 90","Accurate crosses per 90","Assists - xA per 90","Pre-assists per 90","Fouls suffered per 90","Offensive duels won per 90","Offensive duels won %","Successful dribbles per 90","Dribble success rate %","Dribbles per 100 touches","Progressive carries per 90","Ball-carrying frequency","Passes per 90","Forward passes per 90","Passes to penalty box per 90","Through passes per 90","Progressive passes per 90","Passes completed per 90","Forward passes completed per 90","Accurate passes to final third per 90","Through passes completed per 90","Progressive passes completed per 90","Pass completion %","Forward pass completion %","Progressive passes (PAdj)","Shots per 90","Shots on target per 90","xG per 90","npxG per 90","xG per 100 touches","Goals per 100 touches","NPG+A per 90","Goals - xG per 90","Shot frequency","Touches in box per 90"
            ]
            
        selected_metric = random.choice(metric_options)

        league_options = [
    "Top 7 Leagues",
    "Top 5 Leagues",
    "All Leagues",
    "Outside Top 7",
    "South America",
    "Premier League",
    "La Liga"
]

        weights = [0.28, 0.45, 0.16, 0, 0, 0.07, 0.04] # Adjust league weights
        assert len(weights) == len(league_options), "Weights length must match the league options length"
        selected_league = random.choices(league_options, weights=weights, k=1)[0]

        if selected_league in ["Top 7 Leagues", "Top 5 Leagues", "All Leagues", "Outside Top 7"]:
            if selected_league == "Top 5 Leagues" and selected_position == "Striker":
                age_options = ["Age", "U23"]
            elif selected_league in ["All Leagues", "Outside Top 7"]:
                if selected_position == "All positions":
                    age_options = ["Age", "U18", "U19", "U20", "U21", "U23"]
                elif selected_position != "Goalkeeper":
                    age_options = ["Age", "U19", "U20", "U21", "U23"]
                else:
                    age_options = ["Age", "U21", "U24"]
            else: 
                if selected_position == "All positions":
                    age_options = ["Age", "U19", "U20", "U21", "U23"]
                elif selected_position != "Goalkeeper":
                    age_options = ["Age", "U21", "U23"]
                else:
                    age_options = ["Age", "U24"]
        else:
            age_options = ["Age"]

        selected_age = random.choice(age_options)

        # Select metric using custom selector
        self.driver.execute_script(f"""
            var metricTrigger = document.getElementById('metric-select-trigger');
            if (metricTrigger) {{
                metricTrigger.click();
            }}
            setTimeout(function() {{
                var options = document.querySelectorAll('#metric-select-options .custom-select-option');
                for (var i = 0; i < options.length; i++) {{
                    if (options[i].textContent.trim() === '{selected_metric}') {{
                        options[i].click();
                        break;
                    }}
                }}
            }}, 100);
        """)

        self.driver.execute_script(f"""
            var positionTrigger = document.getElementById('position-select-trigger');
            if (positionTrigger) {{
                positionTrigger.click();
            }}
            setTimeout(function() {{
                var options = document.querySelectorAll('#position-select-options .custom-select-option');
                for (var i = 0; i < options.length; i++) {{
                    if (options[i].textContent.trim() === '{selected_position}') {{
                        options[i].click();
                        break;
                    }}
                }}
            }}, 100);
        """)

        # Select league using custom selector
        self.driver.execute_script(f"""
            var leagueTrigger = document.getElementById('league-select-trigger');
            if (leagueTrigger) {{
                leagueTrigger.click();
            }}
            setTimeout(function() {{
                var options = document.querySelectorAll('#league-select-options .custom-select-option');
                for (var i = 0; i < options.length; i++) {{
                    if (options[i].textContent.trim() === '{selected_league}') {{
                        options[i].click();
                        break;
                    }}
                }}
            }}, 100);
        """)

        # Select age using custom selector
        if selected_age != "Age":
            self.driver.execute_script(f"""
                var ageTrigger = document.getElementById('age-select-trigger');
                if (ageTrigger) {{
                    ageTrigger.click();
                }}
                setTimeout(function() {{
                    var options = document.querySelectorAll('#age-select-options .custom-select-option');
                    for (var i = 0; i < options.length; i++) {{
                        if (options[i].textContent.trim() === '{selected_age}') {{
                            options[i].click();
                            break;
                        }}
                    }}
                }}, 100);
            """)

        # Check if we need to handle the toggle sort checkbox
        if selected_metric in ["Goals - xG per 90", "Assists - xA per 90"]:
            # Randomly decide whether to click the toggle
            if random.choice([True, False]):
                try:
                    toggle_sort = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.ID, "toggleSort"))
                    )
                    self.driver.execute_script("arguments[0].click();", toggle_sort)
                except Exception as e:
                    print(f"Could not click toggle sort: {e}")

        # Wait for the toggle metrics button to be visible and scroll into view
        toggle_metrics_btn = WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, "toggleMetrics"))
        )
        self.driver.execute_script("arguments[0].scrollIntoView(true);", toggle_metrics_btn)

        # Use JavaScript to click the button
        try:
            self.driver.execute_script("arguments[0].click();", toggle_metrics_btn)
            time.sleep(0.5)  # Wait for the toggle state to update visually
        except Exception as e:
            raise e
        
        self.driver.execute_script("""
    document.documentElement.style.overflow = 'hidden';  // Hide horizontal and vertical scroll bars
    document.body.style.overflow = 'hidden';  // Hide scroll bars on body
    var resultContainer = document.querySelector('.result-container');
    if (resultContainer) {
        resultContainer.style.overflow = 'hidden';  // Hide scroll bars on result-container div
    }
""")

        # Inject a dummy div at the top left and move mouse to it to avoid hover effect
        self.driver.execute_script("""
            if (!document.getElementById('dummy-mouse-target')) {
                var d = document.createElement('div');
                d.id = 'dummy-mouse-target';
                d.style.position = 'fixed';
                d.style.left = '0px';
                d.style.top = '0px';
                d.style.width = '1px';
                d.style.height = '1px';
                d.style.zIndex = '99999';
                d.style.background = 'transparent';
                document.body.appendChild(d);
            }
        """)
        dummy = self.driver.find_element(By.ID, "dummy-mouse-target")
        ActionChains(self.driver).move_to_element(dummy).perform()

        # Hide the dark-mode-toggle before taking the screenshot
        self.driver.execute_script("""
            var dmt = document.querySelector('.dark-mode-toggle');
            if (dmt) dmt.style.display = 'none';
        """)

        # Save screenshot
        self.driver.save_screenshot('screenshot.png')
        specific_text = self.capture_first_five_lines()

        # Crop 5px from top, left, and right
        img = Image.open('screenshot.png')
        width, height = img.size
        cropped = img.crop((11, 0, width - 11, height - 5))
        cropped.save('screenshot.png')
        
        selected_metric = selected_metric.replace(" per 90", "")
        selected_position = selected_position.replace("er", "ers")
        selected_position = selected_position.replace("ack", "acks")
        selected_position = selected_position.replace("All positions", "Players")
        selected_age = selected_age.replace("Age", "")
        tweet_text = f"{selected_league} {selected_age} {selected_position} : {selected_metric}\n\n{specific_text}\n\n📊 Free trial: datamb.football"
        tweet_text = tweet_text.replace("  ", " ")
        tweet_text = tweet_text.replace(" Wanderers", "")
        tweet_text = tweet_text.replace("Borussia ", "")
        tweet_text = tweet_text.replace("Deportivo ", "")
        tweet_text = tweet_text.replace("Manchester", "Man")
        tweet_text = tweet_text.replace(" Hotspur", "")
        tweet_text = tweet_text.replace("West Ham United", "West Ham")
        tweet_text = tweet_text.replace("Celta de", "Celta")
        tweet_text = tweet_text.replace("Olympique Lyonnais", "Lyon")
        tweet_text = tweet_text.replace("Olympique Marseille", "Marseille")
        tweet_text = tweet_text.replace("Fortuna ", "")
        tweet_text = tweet_text.replace("Eintracht ", "")
        tweet_text = tweet_text.replace("Newcastle United", "Newcastle")
        tweet_text = tweet_text.replace("Wingers", "Wingers & Att Mid")
        tweet_text = tweet_text.replace("Goals - xG", "Goals minus xG")
        tweet_text = tweet_text.replace("All Leagues", "🌍 All Leagues")
        tweet_text = tweet_text.replace("Outside Top 7", "🌍 Outside Top 7")
        tweet_text = tweet_text.replace("South America", "🌎 South America")
        tweet_text = tweet_text.replace("Top 7 Leagues", "🇪🇺 Top 7 League")
        tweet_text = tweet_text.replace("Top 5 Leagues", "🇪🇺 Top 5 League")
        tweet_text = tweet_text.replace("Premier League", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League")
        tweet_text = tweet_text.replace("La Liga", "🇪🇸 La Liga")
        tweet_text = tweet_text.replace("Bundesliga", "🇩🇪 Bundesliga")
        tweet_text = tweet_text.replace("Serie A", "🇮🇹 Serie A")
        
        alt_text = (
            "This is an automated tweet 🤖\n\nPosition, league, age and metrics were chosen randomly in the 2025/26 dataset.\n\n"
            "Player age and team refer to their age and team during the season.\n\nPositions are determined via the player's average heat map.\n\n"
            "Join the free trial for more leagues and tools!"
        )
        follow_up_text = "Compare Top 7 League players, or join the free trial for more leagues, metrics, and tools ⤵️ datamb.football"
        screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot.png")
        time.sleep(170 * 60)
        schedule_twitter_post_via_buffer(
            self.driver,
            tweet_text,
            screenshot_path,
            alt_text=alt_text,
            reply_text=follow_up_text,
        )
        print("Post scheduled in Buffer (~2 minutes).")

        


if __name__ == "__main__":
    pytest.main()

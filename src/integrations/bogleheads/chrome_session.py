"""Drive Google Chrome for Bogleheads login/browse via AppleScript + JS.

Uses Keychain credentials. Never prints the password.
"""

from __future__ import annotations

import json
import logging
import subprocess  # nosec B404
import time
from typing import Any

from src.integrations.bogleheads.credentials import load_credentials

logger = logging.getLogger(__name__)

LOGIN_URL = "https://www.bogleheads.org/forum/ucp.php?mode=login"
FORUM_HOME = "https://www.bogleheads.org/forum/index.php"
VIEWTOPIC_PREFIX = "https://www.bogleheads.org/forum/viewtopic.php"


def _osascript(script: str, *, timeout: int = 60) -> str:
    result = subprocess.run(  # nosec B603 B607
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"osascript failed: {err[:500]}")
    return (result.stdout or "").strip()


def _js_escape(s: str) -> str:
    """Escape a Python string for embedding inside a JS single-quoted string."""
    return (
        s.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "")
        .replace("\u2028", "")
        .replace("\u2029", "")
    )


def open_url_in_chrome(url: str) -> str:
    """Open URL in existing Google Chrome (inherits profile cookies)."""
    # open(1) is more reliable than inventing tabs when many windows exist
    subprocess.run(  # nosec B603 B607
        ["open", "-a", "Google Chrome", url],
        check=False,
        capture_output=True,
        timeout=15,
    )
    time.sleep(1.5)
    # Activate the tab that matches the URL (best-effort)
    needle = url.split("?")[0].replace("https://", "").replace("http://", "")
    safe_needle = needle.replace('"', '\\"')[:80]
    script = f'''
tell application "Google Chrome"
  activate
  repeat with w in windows
    set i to 0
    repeat with t in tabs of w
      set i to i + 1
      if (URL of t as text) contains "{safe_needle}" then
        set active tab index of w to i
        set index of w to 1
        return URL of t
      end if
    end repeat
  end repeat
  if (count of windows) > 0 then
    return URL of active tab of front window
  end if
  return ""
end tell
'''
    try:
        return _osascript(script)
    except Exception:
        return chrome_active_url()


def chrome_active_url() -> str:
    script = '''
tell application "Google Chrome"
  if (count of windows) = 0 then return ""
  return URL of active tab of front window
end tell
'''
    return _osascript(script)


def chrome_exec_js(js: str, *, timeout: int = 60) -> str:
    """Execute JavaScript in Chrome active tab. JS must not contain unescaped quotes carefully.

    We pass JS via a temp approach: AppleScript string with escaped quotes.
    """
    # Escape for AppleScript double-quoted string
    as_js = js.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Google Chrome"
  if (count of windows) = 0 then error "no chrome window"
  set r to execute active tab of front window javascript "{as_js}"
  return r
end tell
'''
    return _osascript(script, timeout=timeout)


def is_logged_in() -> bool:
    """Best-effort: open forum home and look for logout / username markers.

    Bogleheads shows the username (e.g. eazyigz) and a logout ucp link when
    authenticated; login mode redirects to index when already logged in.
    """
    try:
        open_url_in_chrome(FORUM_HOME)
        time.sleep(2.5)
        js = """
(() => {
  const t = document.body ? document.body.innerText : '';
  const html = document.documentElement ? document.documentElement.innerHTML : '';
  const hasLogout = /mode=logout/i.test(html) || /Log out/i.test(t) || /Logout/i.test(t);
  const hasPM = /Private messages/i.test(t) || /ucp\\.php\\?i=pm/i.test(html);
  const hasUserChrome = /eazyigz/i.test(t) || /User Control Panel/i.test(t);
  const loggedOutForm = /mode=login/i.test(html) && document.querySelector('input[name="username"]');
  const loggedIn = !loggedOutForm && (hasLogout || (hasPM && hasUserChrome) || hasLogout);
  return JSON.stringify({
    loggedIn: !!loggedIn,
    hasLogout: !!hasLogout,
    hasPM: !!hasPM,
    hasUserChrome: !!hasUserChrome,
    title: document.title,
    url: location.href
  });
})()
"""
        raw = chrome_exec_js(js)
        data = json.loads(raw) if raw else {}
        logger.info("login probe: %s", data)
        return bool(data.get("loggedIn"))
    except Exception as exc:
        logger.warning("is_logged_in check failed: %s", exc)
        return False


def ensure_logged_in(*, force_login: bool = False) -> dict[str, Any]:
    """Ensure Chrome session is logged into Bogleheads as Keychain user.

    Returns status dict (never includes password).
    Requires Chrome: View → Developer → Allow JavaScript from Apple Events.
    """
    creds = load_credentials()
    status: dict[str, Any] = {
        "username": creds.username,
        "email": creds.email,
        "already_logged_in": False,
        "login_attempted": False,
        "ok": False,
    }

    if not force_login and is_logged_in():
        status["already_logged_in"] = True
        status["ok"] = True
        return status

    # Login URL redirects to index when already authenticated — treat as success
    open_url_in_chrome(LOGIN_URL)
    time.sleep(3.5)
    status["login_attempted"] = True
    status["url_after_open"] = chrome_active_url()

    try:
        probe = chrome_exec_js(
            "(() => JSON.stringify({"
            "title: document.title, "
            "hasUser: !!document.querySelector('input[name=username]'), "
            "hasLogout: /mode=logout/i.test(document.documentElement.innerHTML), "
            "userVisible: /eazyigz/i.test(document.body?document.body.innerText:''), "
            "url: location.href}))()"
        )
        status["probe"] = json.loads(probe) if probe.startswith("{") else {"raw": probe[:200]}
        p = status.get("probe") or {}
        if p.get("hasLogout") or (p.get("userVisible") and not p.get("hasUser")):
            status["ok"] = True
            status["already_logged_in"] = True
            status["note"] = "session cookie present (login form not shown)"
            return status
    except Exception as exc:
        status["probe_error"] = str(exc)[:200]

    user_js = _js_escape(creds.username)
    pass_js = _js_escape(creds.password)

    # phpBB login form: username, password, optionally autologin
    fill_js = f"""
(() => {{
  const user = document.querySelector('input[name="username"], input#username, input[type="text"][id*="user"]');
  const pass = document.querySelector('input[name="password"], input#password, input[type="password"]');
  if (!user || !pass) {{
    return JSON.stringify({{
      ok: false,
      reason: 'login_fields_missing',
      title: document.title,
      url: location.href,
      inputs: Array.from(document.querySelectorAll('input')).map(i => i.name||i.id||i.type).slice(0,20)
    }});
  }}
  user.focus();
  user.value = '';
  user.value = '{user_js}';
  user.dispatchEvent(new Event('input', {{bubbles: true}}));
  user.dispatchEvent(new Event('change', {{bubbles: true}}));
  pass.focus();
  pass.value = '';
  pass.value = '{pass_js}';
  pass.dispatchEvent(new Event('input', {{bubbles: true}}));
  pass.dispatchEvent(new Event('change', {{bubbles: true}}));
  const auto = document.querySelector('input[name="autologin"]');
  if (auto) auto.checked = true;
  const form = user.closest('form') || document.querySelector('form#login, form');
  if (form) {{
    form.submit();
    return JSON.stringify({{ok: true, submitted: true, url: location.href}});
  }}
  const btn = document.querySelector('input[name="login"], input[type="submit"], button[type="submit"]');
  if (btn) {{ btn.click(); return JSON.stringify({{ok: true, clicked: true}}); }}
  return JSON.stringify({{ok: false, reason: 'no_submit'}});
}})()
"""
    try:
        raw = chrome_exec_js(fill_js)
        status["fill_result"] = json.loads(raw) if raw.startswith("{") else {"raw": raw[:300]}
    except Exception as exc:
        status["error"] = str(exc)[:300]
        status["hint"] = (
            "Enable Chrome: View → Developer → Allow JavaScript from Apple Events"
        )
        return status

    time.sleep(4.0)
    status["ok"] = is_logged_in()
    status["final_url"] = chrome_active_url()
    if not status["ok"]:
        status["hint"] = (
            "If form was filled but login failed: check captcha/2FA, or enable "
            "Chrome 'Allow JavaScript from Apple Events'."
        )
    return status


def fetch_topic_text(topic_url: str) -> dict[str, Any]:
    """Open a topic in Chrome and extract visible post text (requires session for some views)."""
    open_url_in_chrome(topic_url)
    time.sleep(2.0)
    js = """
(() => {
  const posts = Array.from(document.querySelectorAll('.post, .postbody, .content'))
    .map(el => (el.innerText || '').trim())
    .filter(t => t.length > 40)
    .slice(0, 8);
  return JSON.stringify({
    url: location.href,
    title: document.title,
    posts: posts,
    text_len: posts.join('\\n').length
  });
})()
"""
    raw = chrome_exec_js(js)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"url": topic_url, "posts": [], "error": "parse_failed", "raw": raw[:300]}

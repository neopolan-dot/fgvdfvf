"""Bounded cloud browser comparisons, without proxies or paid services."""
import json
import re
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
from joybuy.scanner import read_slot, body_block

def dismiss_banners(page):
    for role in (True, False):
        try:
            control = page.get_by_role("button", name="Alle ablehnen", exact=True) if role else page.get_by_text("Alle ablehnen", exact=True)
            if control.count() == 1 and control.is_visible():
                control.click(timeout=2500)
                return
        except Exception:
            pass


def error_excerpt(response):
    try:
        raw = response.text()
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {k: str(data[k])[:400] for k in ("code","message","msg","error","error_description") if k in data}
        except ValueError:
            pass
        text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", "", raw, flags=re.S|re.I)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", text)).strip()[:500]
    except Exception:
        return "body unavailable"

def main():
    import time
    results = []
    variants = [
        ("desktop_chrome", None, True, "https://m.joybuy.de/marketing/happy-hour", False),
        ("android_chrome", "Pixel 7", True, "https://m.joybuy.de/marketing/happy-hour", False),
        ("iphone_windowed_homepage_first", "iPhone 13", False, "https://m.joybuy.de/marketing/happy-hour", True),
        ("desktop_www", None, False, "https://www.joybuy.de/marketing/happy-hour", True),
        ("firefox_desktop", None, True, "https://m.joybuy.de/marketing/happy-hour", False),
        ("firefox_iphone_profile", "iPhone 13", True, "https://m.joybuy.de/marketing/happy-hour", False),
    ]
    with sync_playwright() as p:
        for name, device, headless, url, home_first in variants:
            result = {"variant":name,"at":datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds"),"errors":[]}
            browser = None
            try:
                is_firefox = name.startswith("firefox")
                browser = p.firefox.launch(headless=True) if is_firefox else p.chromium.launch(channel="chrome", headless=headless)
                options = dict(p.devices[device]) if device else {"viewport":{"width":1366,"height":900}}
                if is_firefox:
                    options.pop("is_mobile", None)
                context = browser.new_context(**options, locale="de-DE", timezone_id="Europe/Berlin")
                page = context.new_page()
                page.set_default_timeout(10000)
                def record(response):
                    parsed = urlsplit(response.url)
                    if response.status >= 400 and (parsed.hostname or "").endswith("joybuy.de") and len(result["errors"]) < 8:
                        result["errors"].append({"status":response.status,"host":parsed.hostname,"path":parsed.path,"detail":error_excerpt(response)})
                page.on("response", record)
                if home_first:
                    root = "https://" + urlsplit(url).netloc + "/"
                    page.goto(root, wait_until="domcontentloaded", timeout=35000)
                    page.wait_for_timeout(6000)
                    dismiss_banners(page)
                response = page.goto(url, wait_until="domcontentloaded", timeout=35000)
                result["http_status"] = response.status if response else None
                try:
                    result["initial_html_product_links"] = len(re.findall(r"/dp/", response.text())) if response else 0
                except Exception:
                    result["initial_html_product_links"] = None
                page.wait_for_timeout(7000)
                dismiss_banners(page)
                result["final_url"] = page.url
                result["user_agent"] = page.evaluate("navigator.userAgent")
                result["blocked"] = body_block(page)
                result["page_excerpt"] = page.locator("body").inner_text()[:1600]
                result["product_link_count"] = page.locator('a[href*="/dp/"]').count()
                if not result["blocked"]:
                    result["slots"] = []
                    deadline = time.monotonic() + 300
                    for hour,label in ((20,"8:00pm"),(21,"9:00pm"),(22,"10:00pm")):
                        try:
                            slot = read_slot(page,hour,label,deadline,5500,18)
                            result["slots"].append(slot)
                        except Exception as exc:
                            result["slots"].append({"hour":hour,"status":"error","reason":str(exc)[:300]})
                    if all(s.get("status") == "read" for s in result["slots"]):
                        result["status"] = "all_three_tabs_read"
            except Exception as exc:
                result["error"] = str(exc)[:600]
            finally:
                if browser:
                    browser.close()
            results.append(result)
            print("JOYBUY_ALTERNATIVE " + json.dumps(result, ensure_ascii=False), flush=True)
    print("JOYBUY_COMPARISON_FINISHED", flush=True)

if __name__ == "__main__":
    main()

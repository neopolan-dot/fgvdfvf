"""Inspect the public server-rendered page without running website scripts."""
import json
from playwright.sync_api import sync_playwright
from joybuy.scanner import CARDS_JS, parse_card, get_tab, all_tab_states
with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome",headless=True)
    context = browser.new_context(**p.devices["iPhone 13"],java_script_enabled=False,locale="de-DE",timezone_id="Europe/Berlin")
    page = context.new_page()
    response = page.goto("https://m.joybuy.de/marketing/happy-hour",wait_until="domcontentloaded",timeout=45000)
    result={"method":"public_html_without_website_javascript","http_status":response.status,"final_url":page.url}
    page.wait_for_timeout(5500)
    result["page_text"]=page.locator("body").inner_text()[:14000]
    cards=page.evaluate(CARDS_JS)
    result["products"]=[parse_card(c) for c in cards]
    result["before_tab_states"]=all_tab_states(page)
    try:
        get_tab(page,21).click(timeout=10000)
        page.wait_for_timeout(5500)
        result["after_tab_states"]=all_tab_states(page)
        after=page.evaluate(CARDS_JS)
        result["product_ids_changed"]=sorted(c["id"] for c in after)!=sorted(c["id"] for c in cards)
    except Exception as exc:
        result["tab_error"]=str(exc)[:500]
    print("JOYBUY_STATIC_TEST "+json.dumps(result,ensure_ascii=False),flush=True)
    browser.close()

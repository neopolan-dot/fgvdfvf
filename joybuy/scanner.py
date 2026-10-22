"""Read public Happy Hour tabs in a mobile WebKit browser.

Only confirmed tab selections receive a time slot. A stable loaded list is
reported as such, never as proof of all products that Joybuy might publish.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
URL = "https://m.joybuy.de/marketing/happy-hour"
OUT = Path(os.environ.get("JOYBUY_OUTPUT", "results"))
SLOTS = ((20, "8:00pm"), (21, "9:00pm"), (22, "10:00pm"))
PRICE = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}\s*€")
REFERENCE = re.compile(r"(UVP|WAR|statt)\s*:?\s*((?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})\s*€", re.I)


def now_iso():
    return datetime.now(BERLIN).isoformat(timespec="seconds")


def tab_pattern(hour):
    twelve = {20: 8, 21: 9, 22: 10}[hour]
    return re.compile(rf"^\s*(?:{twelve}:00\s*pm|{hour}:00(?:\s*Uhr)?)\s*$", re.I)


def normalize_link(link):
    parsed = urlsplit(link)
    if parsed.scheme != "https" or parsed.hostname not in ("joybuy.de", "www.joybuy.de", "m.joybuy.de"):
        return None
    if not parsed.path.startswith("/dp/"):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def parse_card(card):
    raw = " ".join(card.get("text", "").split())[:3000]
    ref = REFERENCE.search(raw)
    candidates = [m for m in PRICE.finditer(raw) if ref is None or not (ref.start() <= m.start() < ref.end())]
    price = candidates[0].group().replace(" ", "") if candidates else None
    stock = re.search(r"(?:Nur noch|noch)\s*(\d+)\s*(?:Artikel|Stück)", raw, re.I)
    discount = re.search(r"(\d{1,3})\s*%\s*(?:Rabatt|sparen)", raw, re.I)
    name = card.get("name", "").strip()
    if not name:
        name = re.sub(r"^\d+\s*%\s*Rabatt\s*", "", raw, flags=re.I)
        name = re.split(r"Nur noch|\d+,\d{2}\s*€|Jetzt kaufen|Erinnern", name, maxsplit=1, flags=re.I)[0].strip()
    return {
        "id": card["id"], "name": name[:500], "url": normalize_link(card.get("url", "")),
        "displayed_price": price,
        "reference_type": ref.group(1).upper() if ref else None,
        "reference_price": ref.group(2) + "€" if ref else None,
        "displayed_discount_percent": int(discount.group(1)) if discount else None,
        "displayed_stock": int(stock.group(1)) if stock else None,
        "raw_text": raw, "price_verification": "page_display_only",
    }


CARDS_JS = r"""() => {
 const visible = e => {
   const s = getComputedStyle(e);
   return s.display !== 'none' && s.visibility !== 'hidden' && e.getClientRects().length > 0;
 };
 const result = new Map();
 for (const link of document.querySelectorAll('a[href]')) {
   if (!visible(link)) continue;
   let u; try { u = new URL(link.href); } catch { continue; }
   if (!['joybuy.de','www.joybuy.de','m.joybuy.de'].includes(u.hostname) || !u.pathname.startsWith('/dp/')) continue;
   let card = link;
   // Expand an image-only link to its product card, stopping before a grid
   // containing multiple different products.
   for (let n = 0, p = link.parentElement; p && n < 7; p = p.parentElement, n++) {
     const urls = new Set([...p.querySelectorAll('a[href]')].map(a => {
       try { const x = new URL(a.href); return x.pathname.startsWith('/dp/') ? x.pathname : ''; } catch { return ''; }
     }).filter(Boolean));
     if (urls.size > 1) break;
     if ((p.innerText || '').trim().length > (card.innerText || '').trim().length) card = p;
   }
   const text = (card.innerText || link.innerText || '').replace(/\s+/g,' ').trim();
   const id = u.pathname.split('/').filter(Boolean).at(-1);
   const title = card.querySelector('h2,h3,h4,[class*="title"],[class*="name"]');
   const name = title?.innerText?.trim() || link.querySelector('img')?.alt || '';
   const row = {id, url:u.origin+u.pathname, text, name};
   if (!result.has(id) || text.length > result.get(id).text.length) result.set(id,row);
 }
 return [...result.values()];
}"""

TAB_STATE_JS = r"""e => {
 const out = [];
 const ownText = e.innerText.trim();
 for (let n=0,p=e; p && n<4; p=p.parentElement,n++) {
   if (n && p.innerText.trim() !== ownText) break;
   const s=getComputedStyle(p);
   out.push({tag:p.tagName, cls:p.className?.toString() || '',
     selected:p.getAttribute('aria-selected'), state:p.getAttribute('data-state'),
     current:p.getAttribute('aria-current'), controls:p.getAttribute('aria-controls'),
     borders:['Top','Right','Bottom','Left'].map(x=>({w:parseFloat(s['border'+x+'Width'])||0,
       c:s['border'+x+'Color'], style:s['border'+x+'Style']})),
     background:s.backgroundColor, weight:s.fontWeight});
 }
 return out;
}"""


def selected_evidence(states, hour):
    def semantic(chain):
        for element in chain:
            if element.get("selected") == "true" or element.get("state") in ("active", "selected"):
                return "semantic selected state"
            if element.get("current") in ("true", "page", "step"):
                return "aria-current"
            if re.search(r"(?:^|[-_\s])(active|selected|current)(?:$|[-_\s])", element.get("cls", ""), re.I):
                return "active class"
        return None
    marked = {h: semantic(chain) for h, chain in states.items()}
    if marked.get(hour) and sum(bool(x) for x in marked.values()) == 1:
        return marked[hour]
    # Joybuy's selected tab in the supplied screenshot has a visible border.
    def bordered(chain):
        return any(sum(b.get("w", 0) > 0 and b.get("style") not in ("none", "hidden")
                       and b.get("c") not in ("transparent", "rgba(0, 0, 0, 0)")
                       for b in element.get("borders", [])) >= 3 for element in chain)
    borders = {h: bordered(chain) for h, chain in states.items()}
    if borders.get(hour) and sum(borders.values()) == 1:
        return "unique visible tab border"
    return None


def get_tab(page, hour):
    locators = page.get_by_text(tab_pattern(hour)).all()
    visible = [item for item in locators if item.is_visible()]
    if len(visible) != 1:
        raise RuntimeError(f"{hour}:00: expected one today's tab, found {len(visible)}")
    return visible[0]


def all_tab_states(page):
    states = {}
    for hour, _ in SLOTS:
        try:
            states[hour] = get_tab(page, hour).evaluate(TAB_STATE_JS)
        except Exception:
            states[hour] = []
    return states


def body_block(page):
    text = page.locator("body").inner_text(timeout=10000)
    for pattern, reason in (
        (r"verify you are human|checking your browser|unusual traffic|access denied", "security_or_access_block"),
        (r"Diese Veranstaltung ist beendet", "ended_message_in_this_browser"),
        (r"Vorübergehende Dienstunterbrechung", "temporary_service_interruption"),
    ):
        if re.search(pattern, text, re.I):
            return reason
    return None


def dismiss_banners(page):
    for label in ("Alle ablehnen", "Nur notwendige", "close"):
        controls = page.get_by_role("button", name=label, exact=True)
        if controls.count() == 1 and controls.is_visible():
            controls.click(timeout=3000)


SCROLL_JS = r"""() => {
 const links=[...document.querySelectorAll('a[href*="/dp/"]')].filter(e=>e.getClientRects().length);
 const anchor=links.at(-1);
 let target=document.scrollingElement;
 for(let p=anchor?.parentElement;p && p!==document.body;p=p.parentElement) {
   const s=getComputedStyle(p);
   if (/(auto|scroll)/.test(s.overflowY) && p.scrollHeight>p.clientHeight+8) {target=p;break;}
 }
 const doc = target===document.scrollingElement;
 const pos=doc?window.scrollY:target.scrollTop;
 const height=target.scrollHeight;
 const viewport=doc?window.innerHeight:target.clientHeight;
 const next=Math.min(pos+viewport*0.85,height);
 if(doc) window.scrollTo(0,next); else target.scrollTo(0,next);
 return {pos:doc?window.scrollY:target.scrollTop,height,viewport,
   bottom:pos+viewport>=height-12};
}"""


def read_slot(page, hour, label, deadline, wait_ms, max_rounds):
    row = {"hour": hour, "label": label, "status": "unconfirmed", "products": [],
           "selection_verified": False, "scroll_rounds": 0, "completeness": "partial"}
    page.evaluate("window.scrollTo(0,0)")
    tab = get_tab(page, hour)
    row["before_tab_states"] = all_tab_states(page)
    tab.click(timeout=12000)
    page.wait_for_timeout(wait_ms)
    states = all_tab_states(page)
    row["after_tab_states"] = states
    proof = selected_evidence(states, hour)
    row["selection_evidence"] = proof
    if not proof:
        row["reason"] = "Clicked the label but could not verify the selected state; products not assigned"
        row["unassigned_cards"] = page.evaluate(CARDS_JS)
        return row
    row["selection_verified"] = True
    seen, stable, previous_height = {}, 0, None
    for step in range(max_rounds + 1):
        if time.monotonic() >= deadline:
            row["reason"] = "scan_time_limit"
            break
        cards = page.evaluate(CARDS_JS)
        before_count = len(seen)
        for card in cards:
            if normalize_link(card.get("url", "")):
                if card["id"] not in seen or len(card["text"]) > len(seen[card["id"]]["text"]):
                    seen[card["id"]] = card
        new_count = len(seen) - before_count
        scroll = page.evaluate(SCROLL_JS)
        if scroll["bottom"] and new_count == 0 and scroll["height"] == previous_height:
            stable += 1
        else:
            stable = 0
        previous_height = scroll["height"]
        if stable >= 3:
            row["completeness"] = "no_new_products_after_three_bottom_waits" if seen else "empty_list"
            row["reason"] = "No additional product IDs or page growth after three bottom scroll/wait rounds"
            break
        more = page.get_by_text(re.compile(r"^\s*Mehr laden\s*$", re.I))
        if more.count() == 1 and more.is_visible():
            # Only click if it is a semantic control, not a passive loading label.
            interactive = more.evaluate("e => ['BUTTON','A'].includes(e.tagName) || e.getAttribute('role')==='button'")
            if interactive:
                more.click(timeout=5000)
                stable = 0
        if step == max_rounds:
            row["reason"] = "scroll_round_limit"
            break
        page.wait_for_timeout(wait_ms)
        row["scroll_rounds"] += 1
    row["products"] = [parse_card(card) for card in seen.values()]
    row["count"] = len(row["products"])
    row["product_signature"] = hashlib.sha256("\n".join(sorted(seen)).encode()).hexdigest()
    row["status"] = "read" if seen and row["completeness"].startswith("no_new_") else "partial"
    return row


def main():
    # Import only here, allowing validation of parsing/selection without browsers.
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": 1, "date": datetime.now(BERLIN).date().isoformat(),
              "timezone": "Europe/Berlin", "started_at": now_iso(), "source": URL,
              "status": "incomplete", "slots": [], "market_prices_verified": False,
              "orderability_verified": False}
    wait_ms = max(5500, int(os.environ.get("JOYBUY_WAIT_MS", "5500")))
    max_rounds = min(35, max(3, int(os.environ.get("JOYBUY_MAX_ROUNDS", "30"))))
    deadline = time.monotonic() + 600
    try:
        with sync_playwright() as playwright:
            browser = playwright.webkit.launch(headless=True)
            context = browser.new_context(**playwright.devices["iPhone 13"], locale="de-DE", timezone_id="Europe/Berlin")
            try:
                page = context.new_page()
                page.set_default_timeout(12000)
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(wait_ms)
                dismiss_banners(page)
                report["browser"] = {"engine": "webkit", "device": "iPhone 13",
                    "user_agent": page.evaluate("navigator.userAgent"), "final_url": page.url}
                print("JOYBUY_BROWSER " + json.dumps(report["browser"], ensure_ascii=False), flush=True)
                block = body_block(page)
                if block:
                    page.reload(wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(wait_ms)
                    block = body_block(page)
                if block:
                    report["reason"] = block
                    report["page_text"] = page.locator("body").inner_text()[:5000]
                    raise RuntimeError(block)
                for hour, label in SLOTS:
                    try:
                        slot = read_slot(page, hour, label, deadline, wait_ms, max_rounds)
                    except Exception as exc:
                        slot = {"hour":hour, "label":label, "status":"error", "selection_verified":False,
                                "completeness":"partial", "products":[], "reason":str(exc)[:700]}
                    report["slots"].append(slot)
                    print("JOYBUY_SLOT " + json.dumps(slot, ensure_ascii=False), flush=True)
                if all(slot["status"] == "read" for slot in report["slots"]):
                    report["status"] = "all_three_tabs_read"
                # Shared products are valid, identical entire lists are flagged for review.
                signatures = [s.get("product_signature") for s in report["slots"] if s.get("products")]
                report["identical_lists_need_review"] = len(signatures) > 1 and len(set(signatures)) == 1
            finally:
                context.close()
                browser.close()
    except Exception as exc:
        report["error"] = str(exc)[:1000]
        print("JOYBUY_ERROR " + report["error"], flush=True)
    report["finished_at"] = now_iso()
    (OUT / "latest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (OUT / "deals.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["hour", "name", "displayed_price", "reference_type", "reference_price", "displayed_stock", "url"], delimiter=";")
        writer.writeheader()
        for slot in report["slots"]:
            for product in slot.get("products", []):
                writer.writerow({key: slot["hour"] if key == "hour" else product.get(key) for key in writer.fieldnames})
    summary = [f"# Joybuy Happy Hour {report['date']}", "", f"Status: {report['status']}", "",
        "| Uhr | Auswahl bestätigt | Produkte | Ergebnis |", "|---|---|---:|---|"]
    for slot in report["slots"]:
        summary.append(f"| {slot['hour']}:00 | {slot.get('selection_verified', False)} | {len(slot.get('products', []))} | {slot['status']} |")
    if report.get("error"):
        summary += ["", report["error"].replace("\n", " ")]
    summary += ["", "Preise sind Seitenanzeigen. Kaufbarkeit und unabhängige Marktpreise sind ungeprüft."]
    (OUT / "summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("JOYBUY_FINISHED " + report["status"], flush=True)
    return 0 if report["status"] == "all_three_tabs_read" and not report.get("identical_lists_need_review") else 1


if __name__ == "__main__":
    sys.exit(main())

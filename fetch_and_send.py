#!/usr/bin/env python3
"""
ارسال آنی اخبار فوتبال ایران به کانال تلگرام - هر خبر در یک پیام جدا
با اجرای هر چند دقیقه (از طریق GitHub Actions)، فقط اخبار واقعاً جدید ارسال می‌شوند.
وضعیت اخبار قبلاً ارسال‌شده در sent_links.json نگه‌داری می‌شود.
"""

import os
import sys
import json
import time
from datetime import datetime, timezone

import feedparser
import requests

RSS_SOURCES = [
    {"url": "https://www.varzesh3.com/rss/all", "name": "ورزش۳"},
]

STATE_FILE = "sent_links.json"
MAX_STATE_ENTRIES = 500
SEND_DELAY_SECONDS = 1.2

FOOTBALL_KEYWORDS = [
    "فوتبال", "لیگ برتر", "لیگ قهرمانان", "جام حذفی", "تیم ملی",
    "استقلال", "پرسپولیس", "تراکتور", "سپاهان", "ذوب‌آهن", "فولاد",
    "گل‌گهر", "نساجی", "آلومینیوم", "مس رفسنجان", "پیکان", "هوادار",
    "لیگ آزادگان", "فدراسیون فوتبال", "بازیکن", "مربی", "نقل و انتقالات",
    "دربی", "AFC", "باشگاه", "لیگ",
]


def is_football_related(title: str, summary: str) -> bool:
    text = f"{title} {summary}"
    return any(keyword in text for keyword in FOOTBALL_KEYWORDS)


def load_sent_links():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_sent_links(links):
    trimmed = links[-MAX_STATE_ENTRIES:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def fetch_all_football_items():
    items = []
    seen_links = set()
    for source in RSS_SOURCES:
        feed = feedparser.parse(source["url"])
        if feed.bozo and not feed.entries:
            print(f"هشدار: خواندن {source['url']} با خطا مواجه شد: {feed.bozo_exception}")
            continue
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            summary = entry.get("summary", "")
            if not title or not link or link in seen_links:
                continue
            if not is_football_related(title, summary):
                continue
            items.append((title, link, source["name"]))
            seen_links.add(link)
    return items


def send_telegram_message(token: str, chat_id: str, title: str, link: str, source_name: str):
    safe_title = title.replace("<", "‹").replace(">", "›")
    text = f'⚽️ <a href="{link}">{safe_title}</a>\n<i>منبع: {source_name}</i>'
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, data=payload, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"ارسال پیام تلگرام ناموفق بود: {resp.status_code} - {resp.text}")


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("خطا: متغیرهای TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID تنظیم نشده‌اند.")
        sys.exit(1)

    try:
        items = fetch_all_football_items()
    except Exception as e:
        print(f"خطا در دریافت اخبار: {e}")
        sys.exit(1)

    if not items:
        print("هیچ خبر فوتبالی‌ای در فیدها پیدا نشد.")
        return

    previously_sent = load_sent_links()

    if previously_sent is None:
        save_sent_links([link for _, link, _ in items])
        print(f"اولین اجرا: {len(items)} خبر موجود ذخیره شد، پیامی ارسال نشد.")
        return

    previously_sent_set = set(previously_sent)
    new_items = [(t, l, s) for t, l, s in items if l not in previously_sent_set]

    if not new_items:
        print("خبر جدیدی از اجرای قبلی پیدا نشد.")
        return

    updated_sent = list(previously_sent)
    sent_count = 0
    for title, link, source_name in reversed(new_items):
        try:
            send_telegram_message(token, chat_id, title, link, source_name)
            updated_sent.append(link)
            sent_count += 1
            time.sleep(SEND_DELAY_SECONDS)
        except Exception as e:
            print(f"خطا در ارسال «{title}»: {e}")

    save_sent_links(updated_sent)
    print(f"{sent_count} خبر جدید ارسال شد.")


if __name__ == "__main__":
    main()

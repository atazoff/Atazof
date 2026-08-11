#!/usr/bin/env python3
"""
ارسال روزانه اخبار فوتبال ایران به کانال تلگرام
منبع: RSS ورزش سه (varzesh3.com) با فیلتر کلیدواژه فوتبال
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import feedparser
import requests

RSS_URL = "https://www.varzesh3.com/rss/all"
MAX_ITEMS = 8
HOURS_WINDOW = 26  # پنجره «خبر امروز» - کمی بیشتر از ۲۴ ساعت برای اطمینان
MAX_MESSAGE_LEN = 3900  # زیر سقف ۴۰۹۶ کاراکتری تلگرام

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


def parse_pubdate(entry):
    if getattr(entry, "published_parsed", None):
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return None


def fetch_football_news():
    feed = feedparser.parse(RSS_URL)
    if feed.bozo and not feed.entries:
        raise RuntimeError(f"خطا در خواندن RSS: {feed.bozo_exception}")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=HOURS_WINDOW)

    fresh_items, all_items = [], []

    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        summary = entry.get("summary", "")
        if not title or not link or not is_football_related(title, summary):
            continue

        all_items.append((title, link))
        pub_date = parse_pubdate(entry)
        if pub_date and pub_date >= cutoff:
            fresh_items.append((title, link))

    if fresh_items:
        return fresh_items[:MAX_ITEMS], True
    # اگر خبر تازه‌ای در بازه زمانی نبود، آخرین اخبار فوتبالی موجود را نشان بده
    return all_items[:MAX_ITEMS], False


def build_message(items, is_fresh: bool) -> str:
    header = "⚽️ <b>اخبار فوتبال ایران</b>"
    if not is_fresh:
        header += "\n<i>(خبر جدیدی در ۲۴ ساعت اخیر پیدا نشد؛ این‌ها آخرین اخبار موجودند)</i>"

    lines = [header, ""]
    for i, (title, link) in enumerate(items, start=1):
        safe_title = title.replace("<", "‹").replace(">", "›")
        lines.append(f'{i}. <a href="{link}">{safe_title}</a>')

    message = "\n".join(lines)
    if len(message) > MAX_MESSAGE_LEN:
        message = message[:MAX_MESSAGE_LEN] + "\n…"
    return message


def send_telegram_message(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, data=payload, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"ارسال پیام تلگرام ناموفق بود: {resp.status_code} - {resp.text}")
    return resp.json()


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("خطا: متغیرهای TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID تنظیم نشده‌اند.")
        sys.exit(1)

    try:
        items, is_fresh = fetch_football_news()
    except Exception as e:
        print(f"خطا در دریافت اخبار: {e}")
        sys.exit(1)

    if not items:
        print("هیچ خبر فوتبالی‌ای در فید پیدا نشد؛ پیامی ارسال نشد.")
        return

    message = build_message(items, is_fresh)

    try:
        send_telegram_message(token, chat_id, message)
        print(f"پیام با موفقیت ارسال شد ({len(items)} خبر, fresh={is_fresh}).")
    except Exception as e:
        print(f"خطا در ارسال پیام: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

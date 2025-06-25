import sys
import hashlib
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

URL = "https://www.agco.ca/en/views/ajax"

PARAMS = {
    "_wrapper_format": "drupal_ajax",
    "keys": "",
    "field_news_type": "All",
    "field_line_of_business": "2091",  # Lottery and Gaming
    "sort_bef_combine": "field_published_date_DESC",
    "view_name": "search_news",
    "view_display_id": "block_1",
    "view_path": "/node/376811",
    "pager_element": 0,
    "_drupal_ajax": 1,
}

def scrape_agco():
    print("🌐 Fetching filtered AGCO news via direct request...")
    try:
        response = requests.get(URL, params=PARAMS, timeout=15)
        response.raise_for_status()

        ajax_chunks = response.json()
        html_payloads = [
            chunk["data"]
            for chunk in ajax_chunks
            if isinstance(chunk, dict) and isinstance(chunk.get("data"), str)
        ]
        if not html_payloads:
            print("❌ No HTML chunks found in AJAX response.")
            sys.exit(1)

        soup = BeautifulSoup("".join(html_payloads), "html.parser")
        return soup

    except Exception as e:
        print(f"❌ Failed to fetch AGCO news: {e}")
        sys.exit(1)

def parse_feed(soup):
    items = soup.select("div.views-row")
    if not items:
        print("⚠️ No filtered news items found.")
        sys.exit(1)

    fg = FeedGenerator()
    fg.id("https://www.agco.ca/en/general/news")
    fg.title("AGCO News – Lottery and Gaming")
    fg.link(href="https://www.agco.ca/en/general/news", rel="alternate")
    fg.description("Filtered AGCO Ontario news (Lottery and Gaming)")
    fg.language("en")

    for item in items:
        title_tag = item.find("h3")
        link_tag = title_tag.find("a") if title_tag else None
        date_tag = item.find("span", class_="date-display-single")

        if not (title_tag and link_tag and date_tag):
            continue

        title = link_tag.get_text(strip=True)
        href = link_tag["href"]
        full_link = "https://www.agco.ca" + href
        date_text = date_tag.get_text(strip=True)

        try:
            dt = datetime.strptime(date_text, "%B %d, %Y")
            pub_date = datetime(dt.year, dt.month, dt.day, 23, 59, 0, tzinfo=timezone.utc)
        except Exception as e:
            print(f"⚠️ Date parse issue for: {title} — {e}")
            pub_date = datetime.now(timezone.utc)

        guid = hashlib.md5((title + full_link).encode("utf-8")).hexdigest()

        entry = fg.add_entry()
        entry.id(guid)
        entry.guid(guid, permalink=False)
        entry.title(title)
        entry.link(href=full_link)
        entry.pubDate(pub_date)
        entry.updated(pub_date)

        print(f"✅ {title} — {pub_date.date()}")

    fg.rss_file("agco_feed.xml")
    print("📄 Saved AGCO RSS to agco_feed.xml")

if __name__ == "__main__":
    soup = scrape_agco()
    parse_feed(soup)

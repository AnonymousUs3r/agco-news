import sys
import hashlib
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

def scrape_agco():
    try:
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)
            page = browser.new_page()
            print("🌐 Navigating to AGCO news page...")
            page.goto("https://www.agco.ca/en/general/news", timeout=60000)

            print("⏳ Waiting for 'Line of Business' dropdown...")
            page.wait_for_selector('select[name="field_line_of_business"]', timeout=10000)

            print("✅ Dropdown found — selecting 'Lottery and Gaming'...")
            page.select_option('select[name="field_line_of_business"]', value="2091")

            selected = page.eval_on_selector(
                'select[name="field_line_of_business"]',
                'el => el.options[el.selectedIndex].textContent.trim()'
            )
            if selected != "Lottery and Gaming":
                print(f"❌ Selection failed — got: {selected}")
                sys.exit(1)
            print(f"🎯 Successfully selected: {selected}")

            print("🔍 Locating dynamic 'Search' button...")
            search_btn = page.query_selector('input[data-drupal-selector^="edit-submit-search-news"]')
            if not search_btn:
                print("❌ 'Search' button not found.")
                sys.exit(1)
            print("✅ 'Search' button found.")

            print("🧪 Capturing results container before filtering...")
            container_selector = "div.view-content"
            initial_content = page.inner_html(container_selector)

            print("🖱️ Clicking 'Search'...")
            page.evaluate("""() => {
                const btn = document.querySelector('input[data-drupal-selector^="edit-submit-search-news"]');
                if (btn) btn.click();
            }""")

            print("⏳ Waiting for results container to change...")
            page.wait_for_function(
                """([sel, html]) => {
                    const curr = document.querySelector(sel)?.innerHTML ?? '';
                    return curr !== html;
                }""",
                arg=[container_selector, initial_content],
                timeout=30000
            )

            print("✅ Filtered results loaded. Extracting page HTML...")
            html = page.content()
            browser.close()
            return html

    except PlaywrightTimeout:
        print("❌ Timeout: Filtered results did not change.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Scraper error: {e}")
        sys.exit(1)

def parse_feed(html: str):
    try:
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("div.views-row")
        if not items:
            print("⚠️ No news items found after filtering.")
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

    except Exception as e:
        print(f"❌ Feed generation error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    html = scrape_agco()
    parse_feed(html)

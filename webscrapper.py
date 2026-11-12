# Web scrapper using MicroSoft PlayWright. User can input the desired search query in line 54 such as "lawyers in Portland" then the code will go into Google Map, query based on the input, find the businesses websites listed in the Google Map location and then go to the website and scrape the listed email on the website
# use case: local small cleaning company can use it to find leads who could be reached out for cleaning services  

import asyncio
import random
import re
import urllib.parse
from bs4 import BeautifulSoup
import pandas as pd
from playwright.async_api import async_playwright
import requests

EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
IGNORED = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")


def find_email(url):
    if not url or url == "N/A":
        return "No Website"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        r = requests.get(url, headers=headers, timeout=6)
        emails = {
            e.lower()
            for e in re.findall(EMAIL_REGEX, r.text)
            if not e.lower().endswith(IGNORED)
        }
        if not emails:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if "contact" in a["href"].lower() or "about" in a["href"].lower():
                    link = urllib.parse.urljoin(url, a["href"])
                    sub_r = requests.get(link, headers=headers, timeout=5)
                    emails.update(
                        {
                            e.lower()
                            for e in re.findall(EMAIL_REGEX, sub_r.text)
                            if not e.lower().endswith(IGNORED)
                        }
                    )
                    if emails:
                        break
        return ", ".join(list(emails)[:2]) if emails else "None Found"
    except Exception:
        return "Failed to Fetch"


async def main():
    query = "lawyers in Portland, OR"
    target_count = 20
    scraped = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        print(f"Searching Google Maps for: {query}")
        await page.goto(
            f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
        )

        feed = 'div[role="feed"]'
        await page.wait_for_selector(feed, timeout=15000)

        while len(scraped) < target_count:
            cards = await page.locator('div[role="article"]').all()
            if len(cards) >= target_count:
                break
            await page.hover(feed)
            await page.mouse.wheel(0, 2000)
            await page.wait_for_timeout(1500)

        cards = await page.locator('div[role="article"]').all()
        for i, card in enumerate(cards[:target_count]):
            try:
                name_el = card.locator("div.fontHeadlineSmall").first
                name = (
                    await name_el.inner_text()
                    if await name_el.count() > 0
                    else "N/A"
                )

                site_el = card.locator('a[data-value="Website"]').first
                site = (
                    await site_el.get_attribute("href")
                    if await site_el.count() > 0
                    else "N/A"
                )

                scraped.append({"Name": name, "Website": site})
                print(f"[{i+1}] Found: {name}")
            except Exception:
                continue

        await browser.close()

    print("\nScanning websites for emails...")
    for item in scraped:
        item["Email"] = find_email(item["Website"])
        print(f"{item['Name']} -> {item['Email']}")

    df = pd.DataFrame(scraped)
    df.to_csv("results.csv", index=False)
    print("\nDone! Saved to results.csv")


if __name__ == "__main__":
    asyncio.run(main())

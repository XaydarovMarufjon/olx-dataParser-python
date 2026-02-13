# scraper.py
import asyncio
import random
from datetime import datetime
from typing import List, Dict, Any

from playwright.async_api import async_playwright, BrowserContext, Page
# from playwright_stealth.stealth import stealth_async
from bs4 import BeautifulSoup
from loguru import logger
from rich.console import Console

from db import db
from config import settings


console = Console()


async def read_keywords(file_path: str = settings.keyword_file) -> List[Dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        keywords = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue

            if '[' in line and ']' in line:
                try:
                    parts = line.rsplit('[', 1)
                    keyword = parts[0].strip()
                    limit = int(parts[1].strip(']'))
                    keywords.append({"keyword": keyword, "limit": limit})
                    console.print(f"[green]Parsed: {keyword} → limit {limit}[/green]")
                except:
                    keywords.append({"keyword": line, "limit": 100})
            else:
                keywords.append({"keyword": line, "limit": 100})
                console.print(f"[green]Parsed: {line} → limit 100[/green]")

        return keywords
    except Exception as e:
        console.print(f"[red]keyword.txt xatosi: {e}[/red]")
        return []


async def parse_ads(html: str, keyword: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    ads = []

    candidates = soup.select(
        'a[href*="/d/"], '
        'div[data-testid*="ad"], '
        'article, '
        'li[data-testid], '
        'div[class*="css-"], '
        'div.offer-wrapper'
    )

    for item in candidates:
        link_tag = item.find("a", href=True) or item
        href = link_tag.get("href", "")
        if not href:
            continue

        link = href if href.startswith("http") else f"https://www.olx.uz{href}"
        if "/d/" not in link:
            continue

        title = (
            item.select_one('h6, h4, [data-testid="adTitle"], .css-1wxaaoj, strong') or
            item
        ).get_text(strip=True) or "Sarlavha yo'q"

        price = (
            item.select_one('[data-testid="adPrice"], .css-13aawz3, strong, p strong') or
            item.select_one('[class*="price"]')
        ).get_text(strip=True) if item.select_one('[data-testid="adPrice"], [class*="price"]') else "Kelishiladi"

        location = (
            item.select_one('[data-testid="location"], .css-1g5b0v8, span:last-child') or
            item.select_one('p > span > span')
        ).get_text(strip=True) if item.select_one('[data-testid="location"], [class*="location"]') else "Joy yo'q"

        img = item.select_one("img")
        image = img["src"] if img and img.get("src") else ""

        ads.append({
            "keyword": keyword,
            "title": title,
            "price": price,
            "location": location,
            "link": link,
            "image": image,
            "scraped_at": datetime.utcnow().isoformat(),
        })

    return ads


async def goto_with_retry(page: Page, url: str, retries: int = 3):
    for attempt in range(retries):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=settings.goto_timeout)
            await page.wait_for_selector("body", timeout=30000)
            return
        except Exception as e:
            console.print(f"[yellow]Retry {attempt+1}/{retries}: {str(e)[:80]}[/yellow]")
            await asyncio.sleep(5)
    raise Exception(f"Sahifa yuklanmadi: {url}")


async def scrape_keyword(keyword: str, limit: int) -> int:
    total = 0
    page_num = 1
    seen = set()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
            locale="uz-UZ",
        )

        while total < limit and page_num <= settings.max_pages_per_keyword:
            page = await context.new_page()
            # await stealth_async(page)

            url = f"https://www.olx.uz/q-{keyword}/?page={page_num}&search%5Border%5D=created_at%3Adesc"
            console.print(f"[cyan]Page {page_num} → {url}[/cyan]")

            try:
                await goto_with_retry(page, url)

                await asyncio.sleep(random.uniform(2, 6))

                html = await page.content()
                new_ads = await parse_ads(html, keyword)

                added = 0
                for ad in new_ads:
                    if ad["link"] in seen:
                        continue
                    seen.add(ad["link"])
                    total += 1
                    added += 1

                    console.print(f"[green]{total}/{limit} | {ad['title'][:50]}...[/green]")

                    if total >= limit:
                        break

                if added == 0:
                    console.print("[yellow]Yangi e'lon yo'q → to'xtaymiz[/yellow]")
                    break

            except Exception as e:
                console.print(f"[red]Xato (page {page_num}): {str(e)[:100]}[/red]")
                break

            finally:
                await page.close()

            page_num += 1
            await asyncio.sleep(random.uniform(settings.request_delay_min, settings.request_delay_max))

        await context.close()
        await browser.close()

    # MongoDB saqlash
    if seen:
        ops = [
            {
                "updateOne": {
                    "filter": {"link": ad["link"]},
                    "update": {"$set": ad},
                    "upsert": True,
                }
            }
            for ad in new_ads if ad["link"] in seen
        ]

        if ops:
            try:
                await db.ads.bulk_write(ops)
                console.print(f"[bold green]{len(ops)} ta saqlandi → {keyword}[/bold green]")
            except Exception as e:
                console.print(f"[red]Saqlash xatosi: {e}[/red]")

    return total
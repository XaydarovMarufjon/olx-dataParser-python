# scraper.py
import asyncio
import random
from datetime import datetime
from typing import List, Dict, Any, Tuple
from urllib.parse import quote_plus
from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup
from rich.console import Console
from pymongo import UpdateOne
from db import db
from config import settings

console = Console()

async def read_keywords(file_path: str = settings.keyword_file) -> List[Dict[str, Any]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        keywords: List[Dict[str, Any]] = []
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("//"):
                continue

            if "[" in line and line.endswith("]"):
                try:
                    parts = line.rsplit("[", 1)
                    keyword = parts[0].strip()
                    limit = int(parts[1].strip("]").strip())
                except Exception:
                    keyword = line
                    limit = 100
            else:
                keyword = line
                limit = 100

            keywords.append({"keyword": keyword, "limit": limit})
            console.print(f"[green]Parsed: {keyword} → limit {limit}[/green]")

        return keywords
    except Exception as e:
        console.print(f"[red]keywords.txt o‘qishda xato: {e}[/red]")
        return []


def _extract_text(el, selector: str) -> str:
    node = el.select_one(selector)
    return node.get_text(strip=True) if node else ""

async def parse_ads(html: str, keyword: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    ads: List[Dict[str, Any]] = []

    for a in soup.select("a[href*='/d/']"):
        href = a.get("href") or ""
        if not href or "/d/" not in href:
            continue

        link = href if href.startswith("http") else f"https://www.olx.uz{href}"

        container = a
        # title
        title = a.get_text(strip=True)
        if not title:
            title = _extract_text(container, "h6") or _extract_text(container, "h4")
        title = title or "Sarlavha yo'q"

        # price
        parent = a
        for _ in range(3):
            if parent and getattr(parent, "parent", None):
                parent = parent.parent
            else:
                break

        price = (
            _extract_text(parent, "[data-testid='ad-price']")
            or _extract_text(parent, "[data-testid='adPrice']")
            or _extract_text(parent, "[class*='price']")
        )
        price = price or "Kelishiladi"

        # location
        location = (
            _extract_text(parent, "[data-testid='location']")
            or _extract_text(parent, "[class*='location']")
        )
        location = location or "Joy yo'q"
        
        # img
        img = parent.select_one("img")
        image = ""
        if img:
            image = img.get("src") or img.get("data-src") or ""

        ads.append(
            {
                "keyword": keyword,
                "title": title,
                "price": price,
                "location": location,
                "link": link,
                "image": image,
                "scraped_at": datetime.utcnow().isoformat(),
            }
        )

    unique: Dict[str, Dict[str, Any]] = {}
    for ad in ads:
        unique[ad["link"]] = ad
    return list(unique.values())


async def goto_with_retry(page: Page, url: str, retries: int = 3) -> None:
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=settings.goto_timeout)
            await page.wait_for_selector("body", timeout=settings.selector_timeout)
            return
        except Exception as e:
            last_err = e
            console.print(f"[yellow]Retry {attempt}/{retries}: {str(e)[:120]}[/yellow]")
            await asyncio.sleep(3 + attempt)
    raise Exception(f"Sahifa yuklanmadi: {url} | oxirgi xato: {last_err}")


async def _save_ads(ads: List[Dict[str, Any]]) -> Tuple[int, int]:
    if not ads:
        return 0, 0

    ops = [
        UpdateOne({"link": ad["link"]}, {"$set": ad}, upsert=True)
        for ad in ads
        if ad.get("link")
    ]
    if not ops:
        return 0, 0

    result = await db.ads.bulk_write(ops, ordered=False)

    inserted = int(getattr(result, "upserted_count", 0) or 0)
    updated = int(getattr(result, "modified_count", 0) or 0)
    return inserted, updated


async def scrape_keyword(keyword: str, limit: int) -> Dict[str, int]:

    total_found = 0
    page_num = 1

    seen_links: set[str] = set()
    collected_ads: List[Dict[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.headless)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/132.0.0.0 Safari/537.36"
            ),
            locale="uz-UZ",
        )

        while total_found < limit and page_num <= settings.max_pages_per_keyword:
            page = await context.new_page()

            q = quote_plus(keyword)
            url = f"https://www.olx.uz/q-{q}/?page={page_num}&search%5Border%5D=created_at%3Adesc"
            console.print(f"[cyan]Page {page_num} → {url}[/cyan]")

            try:
                await goto_with_retry(page, url)
                await asyncio.sleep(random.uniform(2, 5))

                html = await page.content()
                page_ads = await parse_ads(html, keyword)

                new_count = 0
                for ad in page_ads:
                    if ad["link"] in seen_links:
                        continue
                    seen_links.add(ad["link"])
                    collected_ads.append(ad)
                    total_found += 1
                    new_count += 1

                    console.print(f"[green]{total_found}/{limit} | {ad['title'][:70]}[/green]")
                    if total_found >= limit:
                        break

                if new_count == 0:
                    console.print("[yellow]Yangi e'lon topilmadi → to'xtaymiz[/yellow]")
                    break

            except Exception as e:
                console.print(f"[red]Xato (page {page_num}): {str(e)[:160]}[/red]")
                break
            finally:
                await page.close()

            page_num += 1
            await asyncio.sleep(random.uniform(settings.request_delay_min, settings.request_delay_max))

        await context.close()
        await browser.close()

    inserted, updated = 0, 0
    try:
        inserted, updated = await _save_ads(collected_ads)
        console.print(
            f"[bold green]Saqlash yakunlandi → keyword='{keyword}' | found={len(collected_ads)} | inserted={inserted} | updated={updated}[/bold green]"
        )
    except Exception as e:
        console.print(f"[bold red]Saqlash xatosi: {e}[/bold red]")

    return {"found": len(collected_ads), "inserted": inserted, "updated": updated}

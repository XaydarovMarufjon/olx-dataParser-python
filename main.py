# main.py
import asyncio
from rich.console import Console
from rich.table import Table

from scraper import read_keywords, scrape_keyword
from db import db


console = Console()


async def main():
    await db.connect()

    tasks = await read_keywords()
    if not tasks:
        console.print("[bold red]Hech qanday keyword topilmadi![/bold red]")
        await db.close()
        return

    table = Table(title="Scraping Natijalari")
    table.add_column("Keyword", style="cyan")
    table.add_column("Limit", style="magenta")
    table.add_column("Topildi", style="green")
    table.add_column("Status", style="bold")

    for task in tasks:
        keyword = task["keyword"]
        limit = task["limit"]

        console.rule(f"[blue]{keyword} (limit: {limit})[/blue]")

        try:
            count = await scrape_keyword(keyword, limit)
            status = "[green]Muvaffaqiyat[/green]" if count > 0 else "[yellow]Topilmadi[/yellow]"
        except Exception as e:
            count = 0
            status = f"[red]Xato: {str(e)[:50]}[/red]"

        table.add_row(keyword, str(limit), str(count), status)

    console.print(table)
    await db.close()


if __name__ == "__main__":
    console.print("[bold green]OLX Scraper ishga tushmoqda...[/bold green]\n")
    asyncio.run(main())
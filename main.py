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

    table = Table(title="Scraping Natijalari: Mongo DB")
    table.add_column("Keyword", style="cyan")
    table.add_column("Limit", style="magenta")
    table.add_column("Topildi", style="green")
    table.add_column("Yangi", style="green")
    table.add_column("Yangilandi", style="yellow")
    table.add_column("Status", style="bold")

    total_found = total_inserted = total_updated = 0

    for task in tasks:
        keyword = task["keyword"]
        limit = task["limit"]

        console.rule(f"[blue]{keyword} (limit: {limit})[/blue]")

        try:
            stats = await scrape_keyword(keyword, limit)
            found = int(stats.get("found", 0))
            inserted = int(stats.get("inserted", 0))
            updated = int(stats.get("updated", 0))

            total_found += found
            total_inserted += inserted
            total_updated += updated

            status = "[green]Muvaffaqiyatli[/green]" if found > 0 else "[yellow]Topilmadi[/yellow]"
        except Exception as e:
            found = inserted = updated = 0
            status = f"[red]Xato: {str(e)[:70]}[/red]"

        table.add_row(keyword, str(limit), str(found), str(inserted), str(updated), status)

    console.print(table)
    console.print(
        f"[bold]Jami:[/bold] found={total_found} | inserted={total_inserted} | updated={total_updated}"
    )

    await db.close()

if __name__ == "__main__":
    console.print("[bold green]OLX Scraper ishga tushmoqda...[/bold green]\n")
    asyncio.run(main())

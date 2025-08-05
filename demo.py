#!/usr/bin/env python3
"""
Market Maven Demo Script

This script demonstrates the key features of the Market Maven stock analysis system.
"""

import asyncio
import sys
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from market_maven.agents.market_maven import StockMarketAgent
from market_maven.tools.data_fetcher import data_fetcher

console = Console()


async def demo_stock_data_fetching():
    """Demonstrate real-time stock data fetching."""
    console.print("\n[bold blue]1. Real-Time Stock Data Fetching[/bold blue]")
    console.print("[dim]Fetching live market data from Alpha Vantage API...[/dim]\n")
    
    symbols = ["AAPL", "GOOGL", "TSLA"]
    
    for symbol in symbols:
        console.print(f"Fetching data for [bold cyan]{symbol}[/bold cyan]...")
        
        # Fetch quote data
        quote = await data_fetcher.fetch_stock_quote(symbol)
        
        if not quote.get('error'):
            table = Table(title=f"{symbol} Quote Data", show_header=True, header_style="bold magenta")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("Current Price", f"${quote.get('price', 'N/A')}")
            table.add_row("Change", f"{quote.get('change', 'N/A')} ({quote.get('change_percent', 'N/A')}%)")
            table.add_row("Volume", f"{quote.get('volume', 'N/A'):,}")
            table.add_row("High", f"${quote.get('high', 'N/A')}")
            table.add_row("Low", f"${quote.get('low', 'N/A')}")
            
            console.print(table)
            console.print()
        else:
            console.print(f"[red]Error: {quote.get('message')}[/red]\n")
        
        # Small delay to respect rate limits
        await asyncio.sleep(1)


async def demo_ai_analysis():
    """Demonstrate AI-powered stock analysis."""
    console.print("\n[bold blue]2. AI-Powered Stock Analysis[/bold blue]")
    console.print("[dim]Using Google Gemini 2.0 Flash for intelligent analysis...[/dim]\n")
    
    agent = StockMarketAgent()
    
    # Quick analysis demo
    console.print("Performing quick analysis of [bold cyan]NVDA[/bold cyan]...")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        task = progress.add_task("Analyzing...", total=None)
        
        result = await agent.quick_analysis("NVDA")
        
        progress.update(task, completed=True)
    
    if result["status"] == "success":
        data = result["data"]
        
        # Display summary
        summary_table = Table(title="Analysis Summary", show_header=False)
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="white")
        
        summary_table.add_row("Symbol", data["symbol"])
        summary_table.add_row("Recommendation", f"[bold yellow]{data['recommendation']}[/bold yellow]")
        summary_table.add_row("Confidence Score", f"{data['confidence_score']}/100")
        summary_table.add_row("Risk Level", data["risk_level"])
        
        console.print(summary_table)
        console.print()
        
        # Show analysis excerpt
        analysis_text = data["analysis"][:500] + "..." if len(data["analysis"]) > 500 else data["analysis"]
        console.print(Panel(analysis_text, title="Analysis Excerpt", border_style="green"))
    else:
        console.print(f"[red]Analysis failed: {result.get('error')}[/red]")


async def demo_portfolio_features():
    """Demonstrate portfolio management features."""
    console.print("\n[bold blue]3. Portfolio Management (Demo)[/bold blue]")
    console.print("[dim]Portfolio tracking and management capabilities...[/dim]\n")
    
    agent = StockMarketAgent()
    
    # Get portfolio summary
    portfolio = agent.get_portfolio_summary()
    
    if portfolio["status"] == "success":
        console.print(Panel(
            portfolio["data"]["message"],
            title="Portfolio Status",
            border_style="yellow"
        ))
    
    # Demo position tracking
    console.print("\n[dim]Position tracking for individual stocks:[/dim]")
    position = agent.get_position("AAPL")
    
    if position["status"] == "success":
        console.print(f"AAPL Position: {position['data']['message']}")


async def main():
    """Run the demo."""
    console.print(Panel.fit(
        "[bold green]Market Maven Demo[/bold green]\n"
        "AI-Powered Stock Market Analysis System",
        border_style="green"
    ))
    
    try:
        # Demo 1: Data Fetching
        await demo_stock_data_fetching()
        
        # Demo 2: AI Analysis
        await demo_ai_analysis()
        
        # Demo 3: Portfolio Features
        await demo_portfolio_features()
        
        console.print("\n[bold green]✅ Demo completed successfully![/bold green]")
        console.print("[dim]To use Market Maven, run: python -m market_maven.cli --help[/dim]\n")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error during demo: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
"""
Main CLI interface for the Stock Market Agent using Google ADK.
"""

import click
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON

from market_maven.agents.market_maven import market_maven

console = Console()

@click.group()
def cli():
    """AI Stock Market Agent - Analyze stocks and execute trades using Google ADK."""
    pass

@cli.command()
@click.argument('symbol')
@click.option('--analysis-type', type=click.Choice(['comprehensive', 'technical', 'fundamental', 'quick']), 
              default='comprehensive', help='Type of analysis to perform')
@click.option('--risk-tolerance', type=click.Choice(['conservative', 'moderate', 'aggressive']), 
              default='moderate', help='Risk tolerance level')
@click.option('--investment-horizon', type=click.Choice(['short_term', 'medium_term', 'long_term']), 
              default='medium_term', help='Investment time horizon')
def analyze(symbol, analysis_type, risk_tolerance, investment_horizon):
    """Analyze a stock and provide trading recommendations."""
    console.print(f"\n[bold blue]Analyzing {symbol.upper()}...[/bold blue]")
    
    try:
        # Create the analysis prompt for the agent
        prompt = f"""
        Please analyze the stock {symbol.upper()} with the following parameters:
        - Analysis type: {analysis_type}
        - Risk tolerance: {risk_tolerance}
        - Investment horizon: {investment_horizon}
        
        First, fetch all available data for this stock including historical prices, company information, and technical indicators.
        Then, perform a {analysis_type} analysis and provide detailed recommendations.
        """
        
        # Run the agent
        response = market_maven.run(prompt)
        
        # Display the response
        console.print("\n[bold green]Analysis Complete![/bold green]")
        console.print(Panel(response, title=f"Analysis Results for {symbol.upper()}", border_style="green"))
        
    except Exception as e:
        console.print(f"[bold red]Error analyzing {symbol}: {str(e)}[/bold red]")

@cli.command()
@click.argument('symbol')
@click.argument('action', type=click.Choice(['BUY', 'SELL']))
@click.argument('quantity', type=int)
@click.option('--order-type', type=click.Choice(['MARKET', 'LIMIT']), default='MARKET')
@click.option('--limit-price', type=float, help='Limit price for LIMIT orders')
@click.option('--stop-loss', type=float, help='Stop loss price')
@click.option('--take-profit', type=float, help='Take profit price')
@click.option('--dry-run', is_flag=True, help='Simulate the trade without executing')
def trade(symbol, action, quantity, order_type, limit_price, stop_loss, take_profit, dry_run):
    """Execute a trade for the specified stock."""
    console.print(f"\n[bold blue]{'Simulating' if dry_run else 'Executing'} {action} order for {quantity} shares of {symbol.upper()}...[/bold blue]")
    
    try:
        # Create the trading prompt for the agent
        prompt = f"""
        Please execute a {action} trade for {symbol.upper()} with the following parameters:
        - Quantity: {quantity} shares
        - Order type: {order_type}
        - Limit price: {limit_price if limit_price else 'N/A'}
        - Stop loss: {stop_loss if stop_loss else 'N/A'}
        - Take profit: {take_profit if take_profit else 'N/A'}
        - Dry run: {dry_run}
        
        Use the stock_trader tool to execute this trade.
        """
        
        # Run the agent
        response = market_maven.run(prompt)
        
        # Display the response
        console.print("\n[bold green]Trade Request Complete![/bold green]")
        console.print(Panel(response, title=f"Trade Results for {symbol.upper()}", border_style="green"))
        
    except Exception as e:
        console.print(f"[bold red]Error executing trade: {str(e)}[/bold red]")

@cli.command()
@click.argument('symbol')
def position(symbol):
    """Get current position for a stock."""
    console.print(f"\n[bold blue]Getting position for {symbol.upper()}...[/bold blue]")
    
    try:
        prompt = f"""
        Please get the current position information for {symbol.upper()}.
        Use the stock_trader tool with action GET_POSITION.
        """
        
        response = market_maven.run(prompt)
        
        console.print("\n[bold green]Position Information Retrieved![/bold green]")
        console.print(Panel(response, title=f"Position for {symbol.upper()}", border_style="green"))
        
    except Exception as e:
        console.print(f"[bold red]Error getting position: {str(e)}[/bold red]")

@cli.command()
def portfolio():
    """Get account summary and portfolio information."""
    console.print(f"\n[bold blue]Getting account summary and portfolio...[/bold blue]")
    
    try:
        prompt = """
        Please get the account summary and portfolio information.
        Use the stock_trader tool with action GET_ACCOUNT_SUMMARY.
        """
        
        response = market_maven.run(prompt)
        
        console.print("\n[bold green]Account Information Retrieved![/bold green]")
        console.print(Panel(response, title="Account Summary & Portfolio", border_style="green"))
        
    except Exception as e:
        console.print(f"[bold red]Error getting account summary: {str(e)}[/bold red]")

@cli.command()
@click.argument('symbol')
def quick_analysis(symbol):
    """Perform a quick analysis of a stock for rapid decision making."""
    console.print(f"\n[bold blue]Performing quick analysis of {symbol.upper()}...[/bold blue]")
    
    try:
        prompt = f"""
        Please perform a quick analysis of {symbol.upper()} for rapid decision making.
        
        1. First, fetch the essential data (historical prices and key technical indicators)
        2. Then, perform a quick analysis focusing on immediate trading signals
        3. Provide a clear BUY/SELL/HOLD recommendation with reasoning
        
        Keep the analysis concise but informative.
        """
        
        response = market_maven.run(prompt)
        
        console.print("\n[bold green]Quick Analysis Complete![/bold green]")
        console.print(Panel(response, title=f"Quick Analysis for {symbol.upper()}", border_style="green"))
        
    except Exception as e:
        console.print(f"[bold red]Error in quick analysis: {str(e)}[/bold red]")

@cli.command()
def interactive():
    """Start an interactive session with the stock agent."""
    console.print("\n[bold green]Starting interactive session with the Stock Market Agent[/bold green]")
    console.print("[dim]Type 'exit' or 'quit' to end the session[/dim]\n")
    
    while True:
        try:
            user_input = console.input("[bold cyan]Stock Agent> [/bold cyan]")
            
            if user_input.lower() in ['exit', 'quit']:
                console.print("[bold yellow]Goodbye![/bold yellow]")
                break
            
            if not user_input.strip():
                continue
            
            console.print(f"\n[dim]Processing: {user_input}[/dim]")
            
            response = market_maven.run(user_input)
            
            console.print("\n[bold green]Agent Response:[/bold green]")
            console.print(Panel(response, border_style="blue"))
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Session interrupted. Goodbye![/bold yellow]")
            break
        except Exception as e:
            console.print(f"\n[bold red]Error: {str(e)}[/bold red]\n")

if __name__ == '__main__':
    cli() 
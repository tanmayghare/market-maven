"""
Production-grade CLI interface for the Stock Market Agent.
"""

import sys
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from rich.json import JSON

from market_maven.config.settings import settings
from market_maven.core.logging import setup_logging, get_logger
from market_maven.core.metrics import metrics
from market_maven.core.database_init import db_manager
from market_maven.agents.market_maven import market_maven


# Initialize console and logging
console = Console()
logger = get_logger(__name__)


def setup_cli_logging() -> None:
    """Set up logging for CLI operations."""
    log_file = None
    if settings.logging.log_file:
        log_file = Path(settings.logging.log_file)
    
    setup_logging(
        level=settings.logging.level,
        log_file=log_file,
        json_logs=settings.logging.json_logs
    )


@click.group()
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.option('--log-level', type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']), 
              default='INFO', help='Set logging level')
@click.pass_context
def cli(ctx: click.Context, debug: bool, log_level: str) -> None:
    """
    AI Stock Market Agent - Production-grade stock analysis and trading.
    
    This tool provides comprehensive stock market analysis and trading capabilities
    using Google's Agent Development Kit (ADK) and advanced AI models.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Set debug mode
    if debug:
        settings.debug = True
        log_level = 'DEBUG'
    
    # Override log level
    settings.logging.level = log_level
    
    # Setup logging
    setup_cli_logging()
    
    # Store context
    ctx.obj['debug'] = debug
    ctx.obj['log_level'] = log_level
    
    # Display startup banner
    if not ctx.obj.get('quiet', False):
        console.print(f"\n[bold blue]🤖 AI Stock Market Agent v1.0[/bold blue]")
        console.print(f"[dim]Environment: {settings.environment.upper()}[/dim]")
        console.print(f"[dim]Model: {settings.model.gemini_model}[/dim]")
        if settings.trading.enable_dry_run:
            console.print("[yellow]⚠️  DRY RUN MODE ENABLED - No real trades will be executed[/yellow]")
        console.print()


@cli.command()
@click.argument('symbol')
@click.option('--analysis-type', 
              type=click.Choice(['comprehensive', 'technical', 'fundamental', 'quick']), 
              default='comprehensive', 
              help='Type of analysis to perform')
@click.option('--risk-tolerance', 
              type=click.Choice(['conservative', 'moderate', 'aggressive']), 
              default='moderate', 
              help='Risk tolerance level')
@click.option('--investment-horizon', 
              type=click.Choice(['short_term', 'medium_term', 'long_term']), 
              default='medium_term', 
              help='Investment time horizon')
@click.option('--output-format', 
              type=click.Choice(['text', 'json']), 
              default='text', 
              help='Output format')
def analyze(
    symbol: str, 
    analysis_type: str, 
    risk_tolerance: str, 
    investment_horizon: str,
    output_format: str
) -> None:
    """Analyze a stock and provide trading recommendations."""
    
    symbol = symbol.upper()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        task = progress.add_task(f"Analyzing {symbol}...", total=None)
        
        try:
            # Perform analysis
            result = market_maven.analyze_stock(
                symbol=symbol,
                analysis_type=analysis_type,
                risk_tolerance=risk_tolerance,
                investment_horizon=investment_horizon
            )
            
            progress.update(task, completed=True)
            
            if result["status"] == "success":
                if output_format == "json":
                    console.print(JSON.from_data(result))
                else:
                    _display_analysis_result(result)
            else:
                console.print(f"[bold red]❌ Analysis failed: {result.get('error', 'Unknown error')}[/bold red]")
                sys.exit(1)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Analysis interrupted by user[/yellow]")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Analysis failed for {symbol}: {e}")
            console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
            sys.exit(1)


@cli.command()
@click.argument('symbol')
@click.argument('action', type=click.Choice(['BUY', 'SELL']))
@click.argument('quantity', type=int)
@click.option('--order-type', type=click.Choice(['MARKET', 'LIMIT']), default='MARKET')
@click.option('--limit-price', type=float, help='Limit price for LIMIT orders')
@click.option('--stop-loss', type=float, help='Stop loss price')
@click.option('--take-profit', type=float, help='Take profit price')
@click.option('--dry-run', is_flag=True, help='Simulate the trade without executing')
@click.option('--force', is_flag=True, help='Skip confirmation prompts')
def trade(
    symbol: str, 
    action: str, 
    quantity: int, 
    order_type: str, 
    limit_price: Optional[float],
    stop_loss: Optional[float], 
    take_profit: Optional[float], 
    dry_run: bool,
    force: bool
) -> None:
    """Execute a trade for the specified stock."""
    
    symbol = symbol.upper()
    action = action.upper()
    
    # Validation
    if quantity <= 0:
        console.print("[bold red]❌ Quantity must be positive[/bold red]")
        sys.exit(1)
    
    if quantity > settings.trading.max_position_size:
        console.print(f"[bold red]❌ Quantity exceeds maximum position size of {settings.trading.max_position_size}[/bold red]")
        sys.exit(1)
    
    if order_type == "LIMIT" and not limit_price:
        console.print("[bold red]❌ Limit price required for LIMIT orders[/bold red]")
        sys.exit(1)
    
    # Build order parameters
    order_params = {
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "order_type": order_type,
        "dry_run": dry_run or settings.trading.enable_dry_run
    }
    
    if limit_price:
        order_params["limit_price"] = limit_price
    if stop_loss:
        order_params["stop_loss"] = stop_loss
    if take_profit:
        order_params["take_profit"] = take_profit
    
    # Display order summary
    _display_order_summary(order_params)
    
    # Confirmation (unless forced or dry run)
    if not force and not order_params["dry_run"]:
        if not Confirm.ask("\n[yellow]⚠️  Execute this trade?[/yellow]"):
            console.print("[dim]Trade cancelled by user[/dim]")
            return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        task = progress.add_task("Executing trade...", total=None)
        
        try:
            # Execute trade
            result = market_maven.execute_trade(**order_params)
            
            progress.update(task, completed=True)
            
            if result["status"] == "success":
                console.print("\n[bold green]✅ Trade request completed![/bold green]")
                console.print(Panel(result["response"], title="Trade Results", border_style="green"))
            else:
                console.print(f"\n[bold red]❌ Trade failed: {result.get('error', 'Unknown error')}[/bold red]")
                sys.exit(1)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Trade interrupted by user[/yellow]")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            console.print(f"\n[bold red]❌ Unexpected error: {str(e)}[/bold red]")
            sys.exit(1)


@cli.command()
@click.argument('symbol', required=False)
def position(symbol: Optional[str]) -> None:
    """Get current position for a stock or all positions."""
    
    try:
        if symbol:
            symbol = symbol.upper()
            result = market_maven.get_position(symbol)
            
            if result["status"] == "success":
                console.print(f"\n[bold green]📊 Position for {symbol}[/bold green]")
                console.print(Panel(result["response"], border_style="blue"))
            else:
                console.print(f"[bold red]❌ Failed to get position: {result.get('error', 'Unknown error')}[/bold red]")
        else:
            # Get all positions via portfolio summary
            result = market_maven.get_portfolio_summary()
            
            if result["status"] == "success":
                console.print("\n[bold green]📊 All Positions[/bold green]")
                console.print(Panel(result["response"], border_style="blue"))
            else:
                console.print(f"[bold red]❌ Failed to get positions: {result.get('error', 'Unknown error')}[/bold red]")
                
    except Exception as e:
        logger.error(f"Position lookup failed: {e}")
        console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
        sys.exit(1)


@cli.command()
def portfolio() -> None:
    """Get account summary and portfolio information."""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        task = progress.add_task("Loading portfolio...", total=None)
        
        try:
            result = market_maven.get_portfolio_summary()
            
            progress.update(task, completed=True)
            
            if result["status"] == "success":
                console.print("\n[bold green]💼 Portfolio Summary[/bold green]")
                console.print(Panel(result["response"], border_style="green"))
            else:
                console.print(f"[bold red]❌ Failed to get portfolio: {result.get('error', 'Unknown error')}[/bold red]")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Portfolio summary failed: {e}")
            console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
            sys.exit(1)


@cli.command()
@click.argument('symbol')
def quick(symbol: str) -> None:
    """Perform a quick analysis of a stock for rapid decision making."""
    
    symbol = symbol.upper()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        task = progress.add_task(f"Quick analysis of {symbol}...", total=None)
        
        try:
            result = market_maven.analyze_stock(
                symbol=symbol,
                analysis_type="quick"
            )
            
            progress.update(task, completed=True)
            
            if result["status"] == "success":
                console.print(f"\n[bold green]⚡ Quick Analysis: {symbol}[/bold green]")
                console.print(Panel(result["response"], border_style="yellow"))
            else:
                console.print(f"[bold red]❌ Quick analysis failed: {result.get('error', 'Unknown error')}[/bold red]")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Quick analysis failed for {symbol}: {e}")
            console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
            sys.exit(1)


@cli.command()
def interactive() -> None:
    """Start an interactive session with the stock agent."""
    
    console.print("\n[bold green]🤖 Interactive Stock Market Agent[/bold green]")
    console.print("[dim]Type 'exit', 'quit', or press Ctrl+C to end the session[/dim]")
    console.print("[dim]Type 'help' for available commands[/dim]\n")
    
    session_commands = {
        "help": "Show available commands",
        "health": "Check agent health status",
        "settings": "Show current configuration",
        "clear": "Clear the screen"
    }
    
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]Stock Agent[/bold cyan]").strip()
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() in ['exit', 'quit']:
                console.print("[bold yellow]👋 Goodbye![/bold yellow]")
                break
            elif user_input.lower() == 'help':
                _display_interactive_help(session_commands)
                continue
            elif user_input.lower() == 'health':
                _display_health_check()
                continue
            elif user_input.lower() == 'settings':
                _display_settings()
                continue
            elif user_input.lower() == 'clear':
                console.clear()
                continue
            
            # Process with agent
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True
            ) as progress:
                
                task = progress.add_task("Processing...", total=None)
                
                try:
                    response = market_maven.run(user_input)
                    progress.update(task, completed=True)
                    
                    console.print("\n[bold green]🤖 Agent Response:[/bold green]")
                    console.print(Panel(response, border_style="blue"))
                    console.print()
                    
                except Exception as e:
                    progress.update(task, completed=True)
                    logger.error(f"Interactive session error: {e}")
                    console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]\n")
            
        except KeyboardInterrupt:
            console.print("\n[bold yellow]👋 Session interrupted. Goodbye![/bold yellow]")
            break
        except EOFError:
            console.print("\n[bold yellow]👋 Goodbye![/bold yellow]")
            break


@cli.command()
def health() -> None:
    """Check the health status of the agent and its components."""
    _display_health_check()


@cli.command()
def config() -> None:
    """Display current configuration settings."""
    _display_settings()


@cli.group()
def database() -> None:
    """Database management commands."""
    pass


@database.command()
@click.option('--force', is_flag=True, help='Force initialization even if database exists')
def init(force: bool) -> None:
    """Initialize the database with all tables and initial data."""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        task = progress.add_task("Initializing database...", total=None)
        
        try:
            success = asyncio.run(db_manager.initialize_database(force=force))
            progress.update(task, completed=True)
            
            if success:
                console.print("[bold green]✅ Database initialized successfully[/bold green]")
            else:
                console.print("[bold red]❌ Database initialization failed[/bold red]")
                sys.exit(1)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Database initialization interrupted[/yellow]")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
            sys.exit(1)


@database.command()
def reset() -> None:
    """Reset the database by dropping and recreating all tables."""
    
    if not Confirm.ask(
        "[bold red]⚠️  This will delete ALL data in the database. Are you sure?[/bold red]",
        default=False
    ):
        console.print("[yellow]Database reset cancelled[/yellow]")
        return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        task = progress.add_task("Resetting database...", total=None)
        
        try:
            success = asyncio.run(db_manager.reset_database())
            progress.update(task, completed=True)
            
            if success:
                console.print("[bold green]✅ Database reset successfully[/bold green]")
            else:
                console.print("[bold red]❌ Database reset failed[/bold red]")
                sys.exit(1)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠️  Database reset interrupted[/yellow]")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            console.print(f"[bold red]❌ Unexpected error: {str(e)}[/bold red]")
            sys.exit(1)


@database.command()
def status() -> None:
    """Check database connection and health status."""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        task = progress.add_task("Checking database status...", total=None)
        
        try:
            health_result = db_manager.check_health()
            schema_valid = asyncio.run(db_manager.validate_database_schema())
            progress.update(task, completed=True)
            
            # Create status table
            table = Table(title="Database Status", title_style="bold blue")
            table.add_column("Component", style="cyan")
            table.add_column("Status", justify="center")
            table.add_column("Details", style="dim")
            
            # Connection status
            if health_result["connected"]:
                table.add_row("Connection", "[green]✅ Connected[/green]", "Database is accessible")
            else:
                table.add_row("Connection", "[red]❌ Disconnected[/red]", 
                             health_result.get("error", "Cannot connect to database"))
            
            # Schema validation
            if schema_valid:
                table.add_row("Schema", "[green]✅ Valid[/green]", "All required tables exist")
            else:
                table.add_row("Schema", "[red]❌ Invalid[/red]", "Missing tables or schema issues")
            
            # Pool status (if available)
            if "details" in health_result and health_result["details"]:
                details = health_result["details"]
                pool_info = f"Size: {details.get('pool_size', 0)}, " \
                           f"In use: {details.get('pool_checked_out', 0)}, " \
                           f"Available: {details.get('pool_checked_in', 0)}"
                table.add_row("Connection Pool", "[blue]ℹ️  Active[/blue]", pool_info)
            
            console.print(table)
            
            # Overall status
            if health_result["connected"] and schema_valid:
                console.print("\n[bold green]🟢 Database is healthy and ready[/bold green]")
            else:
                console.print("\n[bold red]🔴 Database has issues that need attention[/bold red]")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Database status check failed: {e}")
            console.print(f"[bold red]❌ Status check failed: {str(e)}[/bold red]")
            sys.exit(1)


@database.command()
@click.option('--days', type=int, default=30, help='Number of days of data to retain')
def cleanup(days: int) -> None:
    """Clean up old data from the database."""
    
    if not Confirm.ask(
        f"This will delete data older than {days} days. Continue?",
        default=True
    ):
        console.print("[yellow]Database cleanup cancelled[/yellow]")
        return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    ) as progress:
        
        task = progress.add_task(f"Cleaning up data older than {days} days...", total=None)
        
        try:
            asyncio.run(db_manager.cleanup_old_data(days_to_keep=days))
            progress.update(task, completed=True)
            console.print(f"[bold green]✅ Database cleanup completed (kept {days} days of data)[/bold green]")
            
        except Exception as e:
            logger.error(f"Database cleanup failed: {e}")
            console.print(f"[bold red]❌ Cleanup failed: {str(e)}[/bold red]")
            sys.exit(1)


def _display_analysis_result(result: Dict[str, Any]) -> None:
    """Display analysis results in a formatted way."""
    
    symbol = result.get("symbol", "Unknown")
    analysis_type = result.get("analysis_type", "Unknown")
    
    console.print(f"\n[bold green]📈 Analysis Results: {symbol}[/bold green]")
    console.print(f"[dim]Analysis Type: {analysis_type.title()}[/dim]")
    console.print(f"[dim]Risk Tolerance: {result.get('risk_tolerance', 'Unknown').title()}[/dim]")
    console.print(f"[dim]Investment Horizon: {result.get('investment_horizon', 'Unknown').replace('_', ' ').title()}[/dim]")
    
    console.print(Panel(result["response"], border_style="green"))


def _display_order_summary(order_params: Dict[str, Any]) -> None:
    """Display order summary before execution."""
    
    table = Table(title="Order Summary", show_header=True, header_style="bold blue")
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="white")
    
    for key, value in order_params.items():
        if value is not None:
            display_key = key.replace('_', ' ').title()
            if key == "dry_run" and value:
                table.add_row(display_key, "[yellow]Yes (Simulated)[/yellow]")
            else:
                table.add_row(display_key, str(value))
    
    console.print("\n")
    console.print(table)


def _display_interactive_help(commands: Dict[str, str]) -> None:
    """Display help for interactive mode."""
    
    table = Table(title="Interactive Commands", show_header=True, header_style="bold blue")
    table.add_column("Command", style="cyan")
    table.add_column("Description", style="white")
    
    for cmd, desc in commands.items():
        table.add_row(cmd, desc)
    
    table.add_row("analyze SYMBOL", "Analyze a specific stock")
    table.add_row("trade SYMBOL BUY/SELL QTY", "Execute a trade")
    table.add_row("position SYMBOL", "Get position for a stock")
    table.add_row("portfolio", "Get portfolio summary")
    
    console.print("\n")
    console.print(table)
    console.print("\n[dim]You can also ask natural language questions about stocks and trading.[/dim]\n")


def _display_health_check() -> None:
    """Display agent health check results."""
    
    try:
        health = market_maven.health_check()
        
        # Overall status
        status_color = "green" if health["agent"] == "healthy" else "yellow" if health["agent"] == "degraded" else "red"
        console.print(f"\n[bold {status_color}]🏥 Agent Health: {health['agent'].upper()}[/bold {status_color}]")
        
        # Environment
        console.print(f"[dim]Environment: {health['environment']}[/dim]")
        
        # Tools status
        if health.get("tools"):
            table = Table(title="Tools Status", show_header=True, header_style="bold blue")
            table.add_column("Tool", style="cyan")
            table.add_column("Status", style="white")
            
            for tool_name, status in health["tools"].items():
                status_style = "green" if status == "healthy" else "red"
                table.add_row(tool_name, f"[{status_style}]{status}[/{status_style}]")
            
            console.print("\n")
            console.print(table)
        
        # Configuration status
        if health.get("configuration"):
            table = Table(title="Configuration Status", show_header=True, header_style="bold blue")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="white")
            
            for comp_name, status in health["configuration"].items():
                status_style = "green" if status == "configured" else "red"
                table.add_row(comp_name, f"[{status_style}]{status}[/{status_style}]")
            
            console.print("\n")
            console.print(table)
        
        # Issues
        if health.get("issues"):
            console.print("\n[bold red]⚠️  Issues Found:[/bold red]")
            for issue_type, issues in health["issues"].items():
                if issues:
                    console.print(f"[red]• {issue_type.replace('_', ' ').title()}: {', '.join(issues)}[/red]")
        
        console.print()
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        console.print(f"[bold red]❌ Health check failed: {str(e)}[/bold red]")


def _display_settings() -> None:
    """Display current configuration settings."""
    
    console.print("\n[bold blue]⚙️  Configuration Settings[/bold blue]")
    
    # Environment
    console.print(f"\n[bold]Environment:[/bold] {settings.environment}")
    console.print(f"[bold]Debug Mode:[/bold] {settings.debug}")
    
    # Model settings
    console.print(f"\n[bold]Model Configuration:[/bold]")
    console.print(f"  Model: {settings.model.gemini_model}")
    console.print(f"  Temperature: {settings.model.temperature}")
    console.print(f"  Max Tokens: {settings.model.max_tokens}")
    
    # Trading settings
    console.print(f"\n[bold]Trading Configuration:[/bold]")
    console.print(f"  Dry Run Mode: {settings.trading.enable_dry_run}")
    console.print(f"  Max Position Size: {settings.trading.max_position_size}")
    console.print(f"  Stop Loss: {settings.trading.stop_loss_percentage:.1%}")
    console.print(f"  Take Profit: {settings.trading.take_profit_percentage:.1%}")
    
    # API settings
    console.print(f"\n[bold]API Configuration:[/bold]")
    console.print(f"  Alpha Vantage: {'✅ Configured' if settings.api.alpha_vantage_api_key else '❌ Missing'}")
    console.print(f"  Google AI: {'✅ Configured' if settings.api.google_api_key else '❌ Missing'}")
    
    console.print()


def main() -> None:
    """Main CLI entry point."""
    try:
        cli()
    except Exception as e:
        logger.error(f"CLI error: {e}")
        console.print(f"[bold red]❌ Fatal error: {str(e)}[/bold red]")
        sys.exit(1)


if __name__ == '__main__':
    main() 
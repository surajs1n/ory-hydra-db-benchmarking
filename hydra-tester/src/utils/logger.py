import logging
import sys
from rich.console import Console
from rich.logging import RichHandler
from typing import Optional, Any

class Logger:
    """Custom logger with rich formatting and file output support"""
    
    def __init__(
        self,
        name: str = "hydra-tester",
        level: str = "INFO",
        log_file: Optional[str] = None,
        verbose: bool = False
    ):
        # Set up rich console
        self.console = Console()
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level.upper())
        
        # Clear any existing handlers
        self.logger.handlers = []
        
        # Create console handler with rich formatting
        console_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_path=verbose,
            markup=True,
            rich_tracebacks=True
        )
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        self.logger.addHandler(console_handler)
        
        # Add file handler if log_file is specified
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def debug(self, msg: str, data: Any = None, *args, **kwargs):
        """Log debug message with optional data"""
        if data is not None:
            if isinstance(data, dict):
                self.console.print("\n[dim]Debug data:[/dim]")
                self.console.print_json(data=data)
            else:
                self.console.print(f"\n[dim]Debug data:[/dim] {data}")
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message"""
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message"""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message"""
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message"""
        self.logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        """Log exception with traceback"""
        self.logger.exception(msg, *args, **kwargs)

    def section(self, title: str):
        """Log a section header"""
        self.console.print(f"\n[bold blue]{'='*20} {title} {'='*20}[/bold blue]\n")

    def success(self, msg: str):
        """Log a success message"""
        self.console.print(f"[bold green]✓ {msg}[/bold green]")

    def failure(self, msg: str):
        """Log a failure message"""
        self.console.print(f"[bold red]✗ {msg}[/bold red]")

    def json(self, data: Any, title: Optional[str] = None):
        """Log data with optional title"""
        if title:
            self.console.print(f"\n[bold cyan]{title}:[/bold cyan]")
        if isinstance(data, (dict, list)):
            self.console.print_json(data=data)
        else:
            self.console.print(str(data))

# Create default logger instance
logger = Logger()

def get_logger(
    name: str = "hydra-tester",
    level: str = "INFO",
    log_file: Optional[str] = None,
    verbose: bool = False
) -> Logger:
    """Get a configured logger instance"""
    return Logger(name=name, level=level, log_file=log_file, verbose=verbose)

import logging
import sys
import threading
from rich.console import Console
from rich.logging import RichHandler
from typing import Optional, Any
from queue import Queue

class ThreadSafeLogger:
    """Thread-safe logger with rich formatting and file output support"""
    
    def __init__(
        self,
        name: str = "hydra-tester",
        level: str = "INFO",
        log_file: Optional[str] = None,
        verbose: bool = False
    ):
        self._queue = Queue()
        self._thread = threading.Thread(target=self._logger_thread, daemon=True)
        # Set up rich console
        self.console = Console()
        
        # Create logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level.upper())
        
        # Clear any existing handlers
        self.logger.handlers = []
        
        # Start logger thread
        self._thread.start()
        
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

    def _logger_thread(self):
        """Background thread for processing log messages"""
        while True:
            record = self._queue.get()
            if record is None:
                break
            # Process the log record
            self.logger.handle(record)
            
    def _enqueue(self, level: int, msg: str, *args, **kwargs):
        """Add log record to queue"""
        thread_id = threading.get_ident()
        msg = f"[Thread-{thread_id}] {msg}"
        record = logging.LogRecord(
            "hydra-tester", level, "", 0, msg, args, None
        )
        self._queue.put(record)

    def debug(self, msg: str, data: Any = None, *args, **kwargs):
        """Log debug message with optional data"""
        if data is not None:
            if isinstance(data, dict):
                self.console.print("\n[dim]Debug data:[/dim]")
                self.console.print_json(data=data)
            else:
                self.console.print(f"\n[dim]Debug data:[/dim] {data}")
        self._enqueue(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        """Log info message"""
        self._enqueue(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        """Log warning message"""
        self._enqueue(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        """Log error message"""
        self._enqueue(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        """Log critical message"""
        self._enqueue(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs):
        """Log exception with traceback"""
        self._enqueue(logging.ERROR, msg, *args, exc_info=True, **kwargs)

    def section(self, title: str):
        """Log a section header"""
        self._enqueue(logging.INFO, f"\n{'='*20} {title} {'='*20}\n")

    def success(self, msg: str):
        """Log a success message"""
        self._enqueue(logging.INFO, f"✓ {msg}")

    def failure(self, msg: str):
        """Log a failure message"""
        self._enqueue(logging.ERROR, f"✗ {msg}")

    def json(self, data: Any, title: Optional[str] = None):
        """Log data with optional title"""
        msg = ""
        if title:
            msg += f"\n{title}:\n"
        if isinstance(data, (dict, list)):
            import json
            msg += json.dumps(data, indent=2)
        else:
            msg += str(data)
        self._enqueue(logging.INFO, msg)

    def flush(self):
        """Flush all queued messages and wait for them to be processed"""
        # Add a sentinel message to mark the end
        self._queue.put(None)
        # Wait for the thread to process all messages
        if self._thread.is_alive():
            self._thread.join()
        # Create a new thread for future messages
        self._thread = threading.Thread(target=self._logger_thread, daemon=True)
        self._thread.start()

    def __del__(self):
        """Cleanup on deletion"""
        self.flush()

# Remove the global instance creation here
# logger = ThreadSafeLogger() 

# Keep get_logger function to be called from main
def get_logger(
    name: str = "hydra-tester",
    level: str = "INFO",
    log_file: Optional[str] = None,
    verbose: bool = False
) -> ThreadSafeLogger:
    """Get a configured logger instance"""
    return ThreadSafeLogger(name=name, level=level, log_file=log_file, verbose=verbose)

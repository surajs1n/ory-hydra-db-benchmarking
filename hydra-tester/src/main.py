import argparse
import asyncio
import os
import asyncio
import threading
import time
import json
from datetime import datetime
from typing import List, Dict
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from .utils.config import ConfigLoader
from .utils.logger import get_logger # Import the function
from .client_manager import ClientManager
from .oauth_flow import OAuthFlow

class HydraTester:
    """Main class for running Hydra OAuth2 lifecycle tests"""

    def __init__(self, args):
        self.args = args
        # Initialize logger correctly based on args
        self.logger = get_logger(
            level="DEBUG" if args.verbose else "INFO",
            log_file=args.log_file,
            verbose=args.verbose
        )
        self.config = ConfigLoader(args.config).get_config()
        # Pass timeout to ClientManager
        self.client_manager = ClientManager(
            self.config.oauth_settings.admin_url,
            self.config.client_config,
            self.logger, # Pass logger instance
            self.args.timeout # Pass timeout
        )
        # Add timing and statistics tracking
        self.start_time = None
        self.end_time = None
        self.success_count = 0
        self.failure_count = 0

    async def setup_clients(self) -> None:
        """Set up OAuth2 clients"""
        self.logger.section("Setting up clients")
        
        # Try to load existing clients
        existing = self.client_manager.load_clients()
        if existing and len(existing) >= self.args.clients:
            self.logger.info(f"Using {self.args.clients} existing clients")
            return list(existing.values())[:self.args.clients]

        # Create new clients if needed
        clients = await self.client_manager.create_clients(self.args.clients)
        self.client_manager.save_clients()
        return clients

    def log_experiment_summary(self):
        """Log comprehensive experiment summary"""
        try:
            self.logger.debug("Generating experiment summary...")  # Debug log
            duration = self.end_time - self.start_time
            total_flows = self.args.clients * self.args.threads_per_client * self.args.flow_repeat_count
            
            summary = {
                "experiment_duration_seconds": duration,
                "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
                "end_time": datetime.fromtimestamp(self.end_time).isoformat(),
                "configuration": {
                    "clients": self.args.clients,
                    "threads_per_client": self.args.threads_per_client,
                    "flow_repeat_count": self.args.flow_repeat_count,
                    "refresh_count": self.args.refresh_count,
                    "refresh_interval": self.args.refresh_interval,
                    "timeout": self.args.timeout
                },
                "results": {
                    "total_flows_attempted": total_flows,
                    "successful_flows": self.success_count,
                    "failed_flows": self.failure_count,
                    "success_rate": f"{(self.success_count/total_flows)*100:.2f}%"
                }
            }
            
            # Use both logger and direct console output
            self.logger.section("Experiment Summary")
            self.logger.json(summary, "Experiment Summary")
        except Exception as e:
            self.logger.error(f"Failed to generate experiment summary: {e}", exc_info=True)
            print(f"Error generating summary: {e}")

    def _execute_single_flow(self, client_config: Dict, thread_id: int):
        """Executes a single OAuth flow in its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        full_history = [] # Accumulate history across repetitions
        flow = None # Define flow outside loop to access save_token_history later

        try:
            for i in range(self.args.flow_repeat_count):
                self.logger.info(f"[Client {client_config['client_id']} Thread {thread_id}] Starting flow repetition {i+1}/{self.args.flow_repeat_count}")
                
                # Create a new flow instance for each repetition for clean state (PKCE etc.)
                flow = OAuthFlow(
                    auth_url=client_config['auth_url'],
                    token_url=client_config['token_url'],
                admin_url=client_config['admin_url'],
                client_id=client_config['client_id'],
                client_secret=client_config['client_secret'],
                redirect_uri=client_config['redirect_uri'],
                scope=client_config['scope'],
                subject=client_config['subject'],
                session_data=client_config['session_data'],
                thread_id=thread_id,
                logger=self.logger, # Pass logger instance
                timeout=client_config['timeout'] # Pass timeout
            )
            
                # Run the auth flow
                tokens = loop.run_until_complete(flow.run_auth_flow())
                
                # Run refresh cycle if needed
                if client_config['refresh_count'] > 0 and tokens:
                    loop.run_until_complete(flow.run_refresh_cycle(
                        tokens.get('refresh_token'), # Use .get for safety
                        client_config['refresh_count'],
                        client_config['refresh_interval']
                    ))
                
                self.success_count += 1  # Increment on successful completion
                
                # Accumulate history from this repetition
                if hasattr(flow, 'thread_local') and hasattr(flow.thread_local, 'token_history'):
                     full_history.extend(flow.thread_local.token_history)
                     # Clear the flow's internal history for the next loop (if reusing instance, but we are not)
                     # flow.thread_local.token_history = [] 
                
                self.logger.info(f"[Client {client_config['client_id']} Thread {thread_id}] Flow repetition {i+1} completed successfully.")

            # After all repetitions, save the accumulated history once
            if flow: # Ensure flow was initialized
                 # Temporarily assign full history to the last flow instance for saving
                 flow.thread_local.token_history = full_history 
                 flow.save_token_history() 
            self.logger.info(f"[Client {client_config['client_id']} Thread {thread_id}] All {self.args.flow_repeat_count} flow repetitions completed.")
        except Exception as e:
            self.failure_count += 1  # Increment on failure
            # Log timeout errors specifically if possible
            if isinstance(e, asyncio.TimeoutError):
                 self.logger.error(f"[Client {client_config['client_id']} Thread {thread_id}] Flow execution TIMED OUT after {client_config['timeout']} seconds.")
            else:
                 self.logger.error(f"[Client {client_config['client_id']} Thread {thread_id}] Flow execution failed: {e}", exc_info=self.args.verbose) # Use self.logger
        finally:
            loop.close()

    def run_all_flows_concurrently(self, clients: List[dict]) -> None:
        """Run all OAuth flows concurrently across all clients and threads."""
        total_threads_required = len(clients) * self.args.threads_per_client
        self.logger.section(f"Starting {total_threads_required} total concurrent flows ({len(clients)} clients x {self.args.threads_per_client} threads/client) with timeout {self.args.timeout}s") # Use self.logger

        tasks = []
        for client in clients:
            # Add timeout to the config passed to each thread
            client_config = {
                'auth_url': self.args.hydra_public_url or self.config.oauth_settings.auth_url,
                'token_url': self.args.hydra_public_url or self.config.oauth_settings.token_url,
                'admin_url': self.args.hydra_admin_url or self.config.oauth_settings.admin_url,
                'client_id': client['client_id'],
                'client_secret': client['client_secret'],
                'redirect_uri': self.args.redirect_uri,
                'scope': self.args.scope,
                'subject': self.config.oauth_settings.subject,
                'session_data': self.config.oauth_settings.session_data.model_dump(),
                'refresh_count': self.args.refresh_count,
                'refresh_interval': self.args.refresh_interval,
                'timeout': self.args.timeout # Add timeout to config
            }
            for thread_id in range(self.args.threads_per_client):
                tasks.append((client_config, thread_id))

        # Use ThreadPoolExecutor for true parallelism
        # The max_workers will naturally limit concurrency based on total_threads_required
        with ThreadPoolExecutor(max_workers=total_threads_required) as executor:
            futures = {executor.submit(self._execute_single_flow, cfg, tid): (cfg['client_id'], tid) for cfg, tid in tasks}
            
            completed_count = 0
            for future in as_completed(futures):
                client_id, thread_id = futures[future]
                completed_count += 1
                try:
                    future.result()  # Raise exceptions if any occurred in the thread
                    self.logger.debug(f"Future completed for Client {client_id} Thread {thread_id}. ({completed_count}/{total_threads_required})") # Use self.logger
                except Exception as exc:
                    # Error is already logged within _execute_single_flow
                    self.logger.debug(f"Task for Client {client_id} Thread {thread_id} completed with an exception.") # Use self.logger
        
        self.logger.info(f"All {total_threads_required} flows have completed.") # Use self.logger

    # Removed cleanup(self) method

    def run(self) -> None:
        """Run the complete test cycle"""
        self.start_time = time.time()
        try:
            # --- Clear local client cache before setup ---
            client_cache_file = "output/clients.json"
            if os.path.exists(client_cache_file):
                try:
                    os.remove(client_cache_file)
                    self.logger.info(f"Cleared local client cache file: {client_cache_file}")
                except OSError as e:
                    self.logger.error(f"Error removing client cache file {client_cache_file}: {e}")
            # ---------------------------------------------

            # Set up clients (needs to run async before thread pool)
            clients = asyncio.run(self.setup_clients())
            if not clients:
                self.logger.error("No clients available, exiting.") # Use self.logger
                return

            # Run OAuth flows concurrently using the thread pool
            self.run_all_flows_concurrently(clients)

        except KeyboardInterrupt:
            self.logger.warning("Interrupted by user. Attempting cleanup...") # Use self.logger
            # Consider how to gracefully shut down the thread pool here if needed
        except Exception as e:
            self.logger.error(f"Test run failed: {e}", exc_info=self.args.verbose) # Use self.logger
        finally:
            self.end_time = time.time()
            self.log_experiment_summary()
            # Ensure all log messages are processed
            self.logger.flush()

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Hydra OAuth2 Lifecycle Tester")
    
    parser.add_argument(
        "--clients",
        type=int,
        default=5,
        help="Number of clients to manage"
    )
    parser.add_argument(
        "--refresh-count",
        type=int,
        default=5,
        help="Number of refresh cycles per client"
    )
    parser.add_argument(
        "--refresh-interval",
        type=int,
        default=5, # Changed default from 300 to 5
        help="Seconds between refresh calls"
    )
    parser.add_argument(
        "--hydra-admin-url",
        help="Hydra admin API URL (e.g., http://localhost:4445)"
    )
    parser.add_argument(
        "--hydra-public-url",
        help="Hydra public API URL (e.g., http://localhost:4444)"
    )
    parser.add_argument(
        "--redirect-uri",
        default="http://localhost/callback",
        help="Redirect URI used in flow"
    )
    parser.add_argument(
        "--scope",
        default="openid offline_access user user.profile user.email",
        help="OAuth2 scope string"
    )
    parser.add_argument(
        "--config",
        help="Path to config file"
    )
    parser.add_argument(
        "--log-file",
        help="Path to log file"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    # Removed --cleanup argument
    parser.add_argument(
        "--threads-per-client",
        type=int,
        default=1,
        help="Number of parallel threads per client (max 100)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="HTTP request timeout in seconds"
    )
    parser.add_argument(
        "--flow-repeat-count",
        type=int,
        default=1,
        help="Number of times each thread repeats the full auth flow + refresh cycle"
    )

    args = parser.parse_args()
    
    # Validate limits
    if args.clients > 100:
        raise ValueError("Maximum number of clients is 100")
    if args.threads_per_client > 100:
        raise ValueError("Maximum threads per client is 100")
        
    return args

def main():
    """Main entry point"""
    args = parse_args()
    
    # Signal handling might need adjustment for thread pools
    # Basic signal handling for main thread:
    tester = HydraTester(args)
    
    # Need access to the logger instance created in HydraTester
    # We'll configure it after creating the tester instance
    
    main_thread_interrupt = threading.Event()
    
    # Define signal_handler function that can access the tester's logger
    def create_signal_handler(tester_instance):
        def signal_handler(sig, frame):
            print("\nSignal received, initiating shutdown...")
            tester_instance.logger.warning("Signal received, initiating shutdown...") # Use tester's logger
            main_thread_interrupt.set()
            # Potentially add logic here to signal worker threads if possible/needed
            # For ThreadPoolExecutor, ongoing tasks will complete unless forced.
        return signal_handler

    signal_handler_func = create_signal_handler(tester)
    signal.signal(signal.SIGINT, signal_handler_func)
    signal.signal(signal.SIGTERM, signal_handler_func)
    # Removed duplicated signal registration below

    try:
        tester.run() # Run is now synchronous from the main thread's perspective
        if main_thread_interrupt.is_set():
             tester.logger.warning("Shutdown initiated by signal.") # Use tester's logger
        else:
             tester.logger.info("Test run completed normally.") # Use tester's logger
             
    except Exception as e:
         # Use the tester's logger if available, otherwise print
         log_func = tester.logger.critical if hasattr(tester, 'logger') else print
         log_func(f"Unhandled exception in main execution: {e}", exc_info=True)
         if hasattr(tester, 'logger'):
             tester.logger.flush()

if __name__ == "__main__":
    main()

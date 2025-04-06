import argparse
import asyncio
import os
from typing import List
import signal
from .utils.config import ConfigLoader
from .utils.logger import get_logger
from .client_manager import ClientManager
from .oauth_flow import OAuthFlow

class HydraTester:
    """Main class for running Hydra OAuth2 lifecycle tests"""

    def __init__(self, args):
        self.args = args
        self.logger = get_logger(
            level="DEBUG" if args.verbose else "INFO",
            log_file=args.log_file,
            verbose=args.verbose
        )
        self.config = ConfigLoader(args.config).get_config()
        self.client_manager = ClientManager(
            self.config.oauth_settings.admin_url,
            self.config.client_config
        )
        self.flows: List[OAuthFlow] = []

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

    async def run_oauth_flows(self, clients: List[dict]) -> None:
        """Run OAuth2 flows for all clients"""
        self.logger.section("Running OAuth2 flows")

        for client in clients:
            flow = OAuthFlow(
            # Override URLs from command line if provided
            auth_url=self.args.hydra_public_url or self.config.oauth_settings.auth_url,
            token_url=self.args.hydra_public_url or self.config.oauth_settings.token_url,
            admin_url=self.args.hydra_admin_url or self.config.oauth_settings.admin_url,
                client_id=client['client_id'],
                client_secret=client['client_secret'],
                redirect_uri=self.args.redirect_uri,
                scope=self.args.scope,
                subject=self.config.oauth_settings.subject,
                session_data=self.config.oauth_settings.session_data.model_dump()
            )
            self.flows.append(flow)

            try:
                tokens = await flow.run_auth_flow()
                if self.args.refresh_count > 0:
                    await flow.run_refresh_cycle(
                        tokens['refresh_token'],
                        self.args.refresh_count,
                        self.args.refresh_interval
                    )
            except Exception as e:
                self.logger.error(f"Flow failed for client {client['client_id']}: {e}")
                continue

            flow.save_token_history()

    async def cleanup(self) -> None:
        """Clean up resources"""
        if self.args.cleanup:
            self.logger.section("Cleaning up")
            await self.client_manager.cleanup_clients()

    async def run(self) -> None:
        """Run the complete test cycle"""
        try:
            # Set up clients
            clients = await self.setup_clients()
            if not clients:
                self.logger.error("No clients available")
                return

            # Run OAuth flows
            await self.run_oauth_flows(clients)

        except KeyboardInterrupt:
            self.logger.warning("Interrupted by user")
        except Exception as e:
            self.logger.error(f"Test failed: {e}")
        finally:
            await self.cleanup()

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
        default=300,
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
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up clients after test"
    )

    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_args()
    
    # Set up signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: loop.stop())

    # Create and run tester
    tester = HydraTester(args)
    try:
        loop.run_until_complete(tester.run())
    finally:
        loop.close()

if __name__ == "__main__":
    main()

from concurrent.futures import ThreadPoolExecutor
import asyncio
import threading
import os
from .oauth_flow import OAuthFlow
from .utils.logger import logger

class ParallelOAuthFlow:
    def __init__(self, client_config, thread_count):
        self.client_config = client_config
        self.thread_count = thread_count
        self.thread_local = threading.local()
        
    def _get_token_file(self, thread_id):
        return f"output/tokens_client_{self.client_config['client_id']}_thread_{thread_id}.json"
        
    async def _run_thread_flow(self, thread_id):
        logger.info(f"[Client {self.client_config['client_id']} Thread {thread_id}] Starting thread")
        
        # Each thread gets its own OAuthFlow instance
        flow = OAuthFlow(
            auth_url=self.client_config['auth_url'],
            token_url=self.client_config['token_url'],
            admin_url=self.client_config['admin_url'],
            client_id=self.client_config['client_id'],
            client_secret=self.client_config['client_secret'],
            redirect_uri=self.client_config['redirect_uri'],
            scope=self.client_config['scope'],
            subject=self.client_config['subject'],
            session_data=self.client_config['session_data'],
            thread_id=thread_id
        )
        
        # Override token file for this thread
        flow.tokens_file = self._get_token_file(thread_id)
        
        try:
            # Run the auth flow
            tokens = await flow.run_auth_flow()
            if self.client_config['refresh_count'] > 0:
                await flow.run_refresh_cycle(
                    tokens['refresh_token'],
                    self.client_config['refresh_count'],
                    self.client_config['refresh_interval']
                )
            flow.save_token_history()
            logger.info(f"[Client {self.client_config['client_id']} Thread {thread_id}] Thread completed successfully")
        except Exception as e:
            logger.error(f"[Client {self.client_config['client_id']} Thread {thread_id}] Thread failed: {e}")

    def _thread_worker(self, thread_id):
        # Each thread gets its own event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_thread_flow(thread_id))
        finally:
            loop.close()

    def run(self):
        logger.section(f"Starting {self.thread_count} threads for client {self.client_config['client_id']}")
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            futures = [
                executor.submit(self._thread_worker, i)
                for i in range(self.thread_count)
            ]
            # Wait for all threads to complete
            for future in futures:
                future.result()
        logger.info(f"[Client {self.client_config['client_id']}] All {self.thread_count} threads completed")

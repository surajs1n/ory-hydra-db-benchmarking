import json
import time
import asyncio
import threading
from typing import Dict, Optional, Tuple
import aiohttp
from urllib.parse import urlencode, urlparse, parse_qs
from .utils.pkce import PKCEGenerator
# from .utils.logger import logger # Removed global logger import
from .consent_handler import ConsentHandler

class OAuthFlow:
    """Handles OAuth2 authorization code flow with PKCE"""

    def __init__(
        self,
        auth_url: str,
        token_url: str,
        admin_url: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scope: str,
        subject: str,
        session_data: Dict,
        thread_id: Optional[int] = None,
        logger = None, # Added logger parameter
        timeout: int = 10 # Added timeout parameter
    ):
        self.auth_url = auth_url.rstrip('/')
        self.token_url = token_url.rstrip('/')
        self.admin_url = admin_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.pkce = PKCEGenerator()
        self.logger = logger # Store logger instance
        self.timeout = aiohttp.ClientTimeout(total=timeout) # Create timeout object
        # Pass timeout to ConsentHandler
        self.consent_handler = ConsentHandler(admin_url, subject, session_data, timeout=timeout) 
        
        # Thread-specific token file
        if thread_id is not None:
            self.tokens_file = f"output/tokens_{client_id}_thread_{thread_id}.json"
        else:
            self.tokens_file = "output/tokens.json"
            
        # Thread-local storage for session data
        self.thread_local = threading.local()
        self.thread_local.token_history = []
        self.thread_id = thread_id

    async def _make_auth_request(self, url: Optional[str] = None, cookies: Optional[Dict] = None) -> Tuple[str, Dict]:
        """Make authorization request with cookie handling"""
        if not url:
            # Initial auth request
            params = {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": self.scope,
                **self.pkce.auth_params
            }
            url = f"{self.auth_url}/oauth2/auth?{urlencode(params)}"
            self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Making initial auth request to: {url}") # Use self.logger

        async with aiohttp.ClientSession(timeout=self.timeout) as session: # Apply timeout
            async with session.get(url, allow_redirects=False, cookies=cookies) as response:
                if response.status not in [302, 303]:
                    error_text = await response.text()
                    raise Exception(f"Expected redirect, got {response.status}: {error_text}")
                
                # Convert cookies to dict
                new_cookies = {}
                for cookie in response.cookies.values():
                    new_cookies[cookie.key] = cookie.value
                
                return response.headers['Location'], new_cookies

    async def _exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for tokens"""
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            **self.pkce.token_params
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session: # Apply timeout
            async with session.post(
                f"{self.token_url}/oauth2/token",
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"[Client {self.client_id} Thread {self.thread_id}] Token exchange failed: {error_text}")
                return await response.json()

    async def _refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token"""
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session: # Apply timeout
            async with session.post(
                f"{self.token_url}/oauth2/token",
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"[Client {self.client_id} Thread {self.thread_id}] Token refresh failed: {error_text}")
                return await response.json()

    async def run_auth_flow(self) -> dict:
        """Run complete OAuth2 authorization flow"""
        self.logger.section(f"Starting OAuth2 flow for client {self.client_id} thread {self.thread_id}") # Use self.logger

        # Step 1: Initial authorization request
        redirect_url, cookies = await self._make_auth_request()
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Auth URL used: {self.auth_url}") # Use self.logger
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Initial redirect: {redirect_url}") # Use self.logger

        # Step 2: Handle login challenge
        login_challenge = self.consent_handler.extract_challenge(redirect_url, "login")
        if not login_challenge: # Check if challenge extraction failed
             self.logger.error(f"[Client {self.client_id} Thread {self.thread_id}] Failed to extract login challenge from URL: {redirect_url}")
             raise Exception("Login challenge extraction failed")
        login_response = await self.consent_handler.handle_login_challenge(login_challenge)
        if not login_response: # Check if handler failed
             self.logger.error(f"[Client {self.client_id} Thread {self.thread_id}] Login challenge handling failed for challenge: {login_challenge}")
             raise Exception("Login challenge handling failed")
        login_redirect = login_response["redirect_to"]
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Login redirect: {login_redirect}") # Use self.logger

        # Step 3: Make auth request with login verifier
        consent_redirect, updated_cookies = await self._make_auth_request(
            login_redirect,
            cookies
        )
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Consent redirect: {consent_redirect}") # Use self.logger
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Updated cookies: {updated_cookies}") # Use self.logger

        # Step 4: Handle consent challenge
        consent_challenge = self.consent_handler.extract_challenge(consent_redirect, "consent")
        if not consent_challenge: # Check if challenge extraction failed
             self.logger.error(f"[Client {self.client_id} Thread {self.thread_id}] Failed to extract consent challenge from URL: {consent_redirect}")
             raise Exception("Consent challenge extraction failed")
        consent_response = await self.consent_handler.handle_consent_challenge(
            consent_challenge,
            self.scope.split()
        )
        if not consent_response: # Check if handler failed
             self.logger.error(f"[Client {self.client_id} Thread {self.thread_id}] Consent challenge handling failed for challenge: {consent_challenge}")
             raise Exception("Consent challenge handling failed")
        final_redirect = consent_response["redirect_to"]
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Final redirect: {final_redirect}") # Use self.logger

        # Step 5: Make final auth request with consent verifier to get code
        callback_redirect, final_cookies = await self._make_auth_request(
            final_redirect,
            {**cookies, **updated_cookies}  # Merge all cookies
        )
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Callback redirect with code: {callback_redirect}") # Use self.logger
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Final cookies: {final_cookies}") # Use self.logger

        # Extract authorization code from callback
        parsed = urlparse(callback_redirect)
        params = parse_qs(parsed.query)
        code = params.get('code', [None])[0]
        if not code:
            self.logger.error(f"[Client {self.client_id} Thread {self.thread_id}] Failed to extract code from redirect: {callback_redirect}") # Use self.logger
            raise Exception("No authorization code in redirect")
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Extracted code: {code[:20]}...") # Use self.logger

        # Exchange code for tokens
        tokens = await self._exchange_code_for_tokens(code)
        self.logger.success(f"[Client {self.client_id} Thread {self.thread_id}] Successfully obtained tokens") # Use self.logger
        self.logger.debug(f"[Client {self.client_id} Thread {self.thread_id}] Tokens received: {tokens}") # Use self.logger

        # Save initial token set to thread-local storage
        self.thread_local.token_history.append({
            "client_id": self.client_id,
            "thread_id": self.thread_id,
            "timestamp": time.time(),
            "type": "initial",
            "tokens": tokens
        })

        return tokens

    async def run_refresh_cycle(
        self,
        refresh_token: str,
        count: int,
        interval: int
    ) -> None:
        """Run token refresh cycle"""
        self.logger.section(f"Starting refresh cycle for client {self.client_id} thread {self.thread_id}") # Use self.logger

        current_token = refresh_token
        if not current_token:
             self.logger.warning(f"[Client {self.client_id} Thread {self.thread_id}] No refresh token provided to start refresh cycle.")
             return # Cannot proceed without a refresh token

        for i in range(count):
            self.logger.info(f"[Client {self.client_id} Thread {self.thread_id}] Refresh attempt {i+1}/{count}") # Use self.logger
            
            # Wait for interval
            await asyncio.sleep(interval)

            try:
                # Refresh token
                new_tokens = await self._refresh_token(current_token)
                self.logger.success(f"[Client {self.client_id} Thread {self.thread_id}] Token refresh {i+1} successful") # Use self.logger

                # Save to thread-local history
                self.thread_local.token_history.append({
                    "client_id": self.client_id,
                    "thread_id": self.thread_id,
                    "timestamp": time.time(),
                    "type": "refresh",
                    "attempt": i + 1,
                    "tokens": new_tokens
                })

                # Update current token
                # Update current token ONLY if a new one was provided
                current_token = new_tokens.get('refresh_token', current_token) 

            except Exception as e:
                self.logger.error(f"[Client {self.client_id} Thread {self.thread_id}] Refresh attempt {i+1} failed: {e}") # Use self.logger
                break

    def save_token_history(self) -> None:
        """Save token history to thread-specific file"""
        # Each thread writes to its own file, so no locking needed
        try:
            with open(self.tokens_file, 'w') as f:
                json.dump(self.thread_local.token_history, f, indent=4)
            self.logger.info(f"[Client {self.client_id} Thread {self.thread_id}] Saved {len(self.thread_local.token_history)} token events to {self.tokens_file}") # Use self.logger
        except Exception as e:
            self.logger.error(f"[Client {self.client_id} Thread {self.thread_id}] Failed to save token history to {self.tokens_file}: {e}")

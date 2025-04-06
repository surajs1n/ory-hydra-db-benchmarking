import json
import time
import asyncio
from typing import Dict, Optional, Tuple
import aiohttp
from urllib.parse import urlencode, urlparse, parse_qs
from .utils.pkce import PKCEGenerator
from .utils.logger import logger
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
        session_data: Dict
    ):
        self.auth_url = auth_url.rstrip('/')
        self.token_url = token_url.rstrip('/')
        self.admin_url = admin_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.pkce = PKCEGenerator()
        self.consent_handler = ConsentHandler(admin_url, subject, session_data)
        self.tokens_file = "output/tokens.json"
        self.token_history = []

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
            logger.debug(f"Making initial auth request to: {url}")

        async with aiohttp.ClientSession() as session:
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

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.token_url}/oauth2/token",
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Token exchange failed: {error_text}")
                return await response.json()

    async def _refresh_token(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token"""
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.token_url}/oauth2/token",
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Token refresh failed: {error_text}")
                return await response.json()

    async def run_auth_flow(self) -> dict:
        """Run complete OAuth2 authorization flow"""
        logger.section(f"Starting OAuth2 flow for client {self.client_id}")

        # Step 1: Initial authorization request
        redirect_url, cookies = await self._make_auth_request()
        logger.debug(f"Auth URL used: {self.auth_url}")
        logger.debug(f"Initial redirect: {redirect_url}")
        logger.debug("Initial cookies:", cookies)

        # Step 2: Handle login challenge
        login_challenge = self.consent_handler.extract_challenge(redirect_url, "login")
        login_response = await self.consent_handler.handle_login_challenge(login_challenge)
        login_redirect = login_response["redirect_to"]
        logger.debug("Login redirect:", login_redirect)

        # Step 3: Make auth request with login verifier
        consent_redirect, updated_cookies = await self._make_auth_request(
            login_redirect,
            cookies
        )
        logger.debug("Consent redirect:", consent_redirect)
        logger.debug("Updated cookies:", updated_cookies)

        # Step 4: Handle consent challenge
        consent_challenge = self.consent_handler.extract_challenge(consent_redirect, "consent")
        consent_response = await self.consent_handler.handle_consent_challenge(
            consent_challenge,
            self.scope.split()
        )
        final_redirect = consent_response["redirect_to"]
        logger.debug("Final redirect:", final_redirect)

        # Step 5: Make final auth request with consent verifier to get code
        callback_redirect, final_cookies = await self._make_auth_request(
            final_redirect,
            {**cookies, **updated_cookies}  # Merge all cookies
        )
        logger.debug("Callback redirect with code:", callback_redirect)
        logger.debug("Final cookies:", final_cookies)

        # Extract authorization code from callback
        parsed = urlparse(callback_redirect)
        params = parse_qs(parsed.query)
        code = params.get('code', [None])[0]
        if not code:
            logger.error(f"Failed to extract code from redirect: {callback_redirect}")
            raise Exception("No authorization code in redirect")
        logger.debug(f"Extracted code: {code[:20]}...")

        # Exchange code for tokens
        tokens = await self._exchange_code_for_tokens(code)
        logger.success("Successfully obtained tokens")
        logger.debug("Tokens received:", tokens)

        # Save initial token set
        self.token_history.append({
            "client_id": self.client_id,
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
        logger.section(f"Starting refresh cycle for client {self.client_id}")

        current_token = refresh_token
        for i in range(count):
            logger.info(f"Refresh attempt {i+1}/{count}")
            
            # Wait for interval
            await asyncio.sleep(interval)

            try:
                # Refresh token
                new_tokens = await self._refresh_token(current_token)
                logger.success(f"Token refresh {i+1} successful")

                # Save to history
                self.token_history.append({
                    "client_id": self.client_id,
                    "timestamp": time.time(),
                    "type": "refresh",
                    "attempt": i + 1,
                    "tokens": new_tokens
                })

                # Update current token
                current_token = new_tokens.get('refresh_token', current_token)

            except Exception as e:
                logger.error(f"Refresh attempt {i+1} failed: {e}")
                break

    def save_token_history(self) -> None:
        """Save token history to file"""
        with open(self.tokens_file, 'w') as f:
            json.dump(self.token_history, f, indent=4)
        logger.info(f"Saved {len(self.token_history)} token events to {self.tokens_file}")

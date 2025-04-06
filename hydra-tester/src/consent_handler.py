import aiohttp
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import urlparse, parse_qs
from .utils.logger import logger

class ConsentHandler:
    """Handles Hydra login and consent flows"""

    def __init__(self, admin_url: str, subject: str, session_data: Dict[str, Any]):
        self.admin_url = f"{admin_url.rstrip('/')}/admin"  # Add /admin to base URL
        self.subject = subject
        self.session_data = session_data

    @staticmethod
    def extract_challenge(url: str, challenge_type: str) -> Optional[str]:
        """Extract login or consent challenge from URL"""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            challenge = params.get(f"{challenge_type}_challenge", [None])[0]
            return challenge
        except Exception as e:
            logger.error(f"Failed to extract {challenge_type} challenge: {e}")
            return None

    async def handle_login_challenge(self, challenge: str) -> Dict[str, Any]:
        """Handle the login challenge"""
        if not challenge:
            raise ValueError("No login challenge provided")

        # Get login request
        login_request = await self._get_login_request(challenge)
        if not login_request:
            raise Exception("Failed to get login request")

        # Accept login
        accept_response = await self._accept_login(challenge)
        if not accept_response or "redirect_to" not in accept_response:
            raise Exception("Failed to accept login")

        return accept_response

    async def handle_consent_challenge(self, challenge: str, requested_scopes: List[str]) -> Dict[str, Any]:
        """Handle the consent challenge"""
        if not challenge:
            raise ValueError("No consent challenge provided")

        # Get consent request
        consent_request = await self._get_consent_request(challenge)
        if not consent_request:
            raise Exception("Failed to get consent request")

        # Accept consent
        accept_response = await self._accept_consent(
            challenge,
            requested_scopes
        )
        if not accept_response or "redirect_to" not in accept_response:
            raise Exception("Failed to accept consent")

        return accept_response

    async def _get_login_request(self, challenge: str) -> Optional[dict]:
        """Get login request details"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.admin_url}/oauth2/auth/requests/login",
                params={"login_challenge": challenge}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to get login request: {error_text}")
                    return None
                return await response.json()

    async def _accept_login(
        self,
        challenge: str,
        remember: bool = True,
        remember_for: int = 3600
    ) -> Optional[dict]:
        """Accept login request"""
        data = {
            "subject": self.subject,
            "remember": remember,
            "remember_for": remember_for
        }

        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{self.admin_url}/oauth2/auth/requests/login/accept",
                params={"login_challenge": challenge},
                json=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to accept login: {error_text}")
                    return None
                return await response.json()

    async def _get_consent_request(self, challenge: str) -> Optional[dict]:
        """Get consent request details"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.admin_url}/oauth2/auth/requests/consent",
                params={"consent_challenge": challenge}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to get consent request: {error_text}")
                    return None
                return await response.json()

    async def _accept_consent(
        self,
        challenge: str,
        grant_scope: List[str]
    ) -> Optional[dict]:
        """Accept consent request"""
        data = {
            "grant_scope": grant_scope,
            "remember": True,
            "remember_for": 3600,
            "session": self.session_data
        }

        async with aiohttp.ClientSession() as session:
            async with session.put(
                f"{self.admin_url}/oauth2/auth/requests/consent/accept",
                params={"consent_challenge": challenge},
                json=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Failed to accept consent: {error_text}")
                    return None
                return await response.json()

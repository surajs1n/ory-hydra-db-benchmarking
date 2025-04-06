import base64
import hashlib
import os
import secrets

def generate_code_verifier(length: int = 64) -> str:
    """
    Generate a code verifier for PKCE.
    Args:
        length: Length of the code verifier (default: 64)
    Returns:
        A random code verifier string
    """
    token = secrets.token_urlsafe(length)
    return token[:length]

def generate_code_challenge(code_verifier: str) -> str:
    """
    Generate a code challenge for PKCE using SHA256.
    Args:
        code_verifier: The code verifier to generate the challenge from
    Returns:
        Base64URL-encoded code challenge
    """
    sha256_hash = hashlib.sha256(code_verifier.encode('ascii')).digest()
    code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('ascii')
    return code_challenge.rstrip('=')  # Remove padding

def generate_state() -> str:
    """
    Generate a random state parameter for OAuth2 requests.
    Returns:
        A random state string
    """
    return secrets.token_urlsafe(32)

def generate_nonce() -> str:
    """
    Generate a random nonce for OpenID Connect requests.
    Returns:
        A random nonce string
    """
    return secrets.token_urlsafe(32)

class PKCEGenerator:
    """
    Helper class to manage PKCE code verifier and challenge pairs.
    """
    def __init__(self):
        self.code_verifier = generate_code_verifier()
        self.code_challenge = generate_code_challenge(self.code_verifier)
        self.state = generate_state()
        self.nonce = generate_nonce()

    @property
    def auth_params(self) -> dict:
        """
        Get the parameters needed for the authorization request.
        Returns:
            Dictionary containing code_challenge, code_challenge_method, state, and nonce
        """
        return {
            "code_challenge": self.code_challenge,
            "code_challenge_method": "S256",
            "state": self.state,
            "nonce": self.nonce
        }

    @property
    def token_params(self) -> dict:
        """
        Get the parameters needed for the token request.
        Returns:
            Dictionary containing code_verifier
        """
        return {
            "code_verifier": self.code_verifier
        }

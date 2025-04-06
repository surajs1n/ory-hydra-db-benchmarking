import json
import os
from typing import Dict, Any, List
from typing_extensions import Annotated
from pydantic import BaseModel, Field
from dotenv import load_dotenv

class ClientConfig(BaseModel):
    """Client configuration model"""
    redirect_uris: List[str] = Field(default=["http://localhost/callback"])
    grant_types: List[str] = Field(default=["authorization_code", "refresh_token"])
    response_types: List[str] = Field(default=["code", "id_token"])
    token_endpoint_auth_method: str = Field(default="client_secret_post")
    scope: str = Field(default="openid offline_access user user.profile user.email")
    skip_consent: bool = Field(default=True)

class SessionData(BaseModel):
    """Session data model for consent handling"""
    access_token: Dict[str, Any] = Field(default_factory=dict)
    id_token: Dict[str, Any] = Field(default_factory=dict)

class OAuthSettings(BaseModel):
    """OAuth settings model"""
    auth_url: str = Field(default="http://localhost:4444")  # Base URL without path
    token_url: str = Field(default="http://localhost:4444")  # Base URL without path
    admin_url: str = Field(default="http://localhost:4445")  # Admin URL
    subject: str = Field(default="test-user@example.com")
    session_data: SessionData = Field(default_factory=SessionData)

class Config(BaseModel):
    """Main configuration model"""
    client_config: ClientConfig = Field(default_factory=ClientConfig)
    oauth_settings: OAuthSettings = Field(default_factory=OAuthSettings)

class ConfigLoader:
    """Configuration loader with environment variable support"""
    def __init__(self, config_path: str = None):
        load_dotenv()  # Load environment variables from .env file if present
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), 
            "../../config/default_config.json"
        )
        self.config = self._load_config()

    def _load_config(self) -> Config:
        """Load configuration from file and override with environment variables"""
        try:
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
        except FileNotFoundError:
            config_data = {}

        # Override with environment variables if present
        env_overrides = {
            "oauth_settings": {
                "auth_url": os.getenv("HYDRA_PUBLIC_URL", "http://localhost:4444"),
                "token_url": os.getenv("HYDRA_PUBLIC_URL", "http://localhost:4444"),
                "admin_url": os.getenv("HYDRA_ADMIN_URL", "http://localhost:4445"),
                "subject": os.getenv("TEST_SUBJECT", "test-user@example.com")
            }
        }

        # Only update if environment variables are set (not empty)
        for section, values in env_overrides.items():
            if section not in config_data:
                config_data[section] = {}
            for key, value in values.items():
                if value:  # Only override if environment variable is set
                    config_data[section][key] = value

        return Config(**config_data)

    def get_config(self) -> Config:
        """Get the loaded configuration"""
        return self.config

    def save_config(self, config_path: str = None) -> None:
        """Save the current configuration to a file"""
        save_path = config_path or self.config_path
        with open(save_path, 'w') as f:
            json.dump(self.config.model_dump(), f, indent=4)

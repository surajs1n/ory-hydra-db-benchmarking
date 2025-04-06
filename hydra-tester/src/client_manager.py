import json
import uuid
from typing import Dict, List, Optional
import aiohttp
from .utils.config import ClientConfig
# from .utils.logger import logger # Removed global logger import

class ClientManager:
    """Manages Hydra OAuth2 clients"""

    def __init__(self, admin_url: str, config: ClientConfig, logger): # Added logger param
        self.admin_url = f"{admin_url.rstrip('/')}/admin"  # Add /admin to base URL
        self.config = config
        self.logger = logger # Store logger instance
        self.clients: Dict[str, dict] = {}
        self.clients_file = "output/clients.json"

    async def create_client(self) -> dict:
        """Create a new Hydra client with configuration"""
        client_id = str(uuid.uuid4())
        client_data = {
            "client_id": client_id,
            "client_secret": str(uuid.uuid4()),
            **self.config.model_dump()
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.admin_url}/clients",
                json=client_data
            ) as response:
                if response.status != 201:
                    error_text = await response.text()
                    self.logger.error(f"Failed to create client: {error_text}") # Use self.logger
                    raise Exception(f"Failed to create client: {error_text}")
                
                created_client = await response.json()
                self.clients[client_id] = created_client
                self.logger.success(f"Created client: {client_id}") # Use self.logger
                return created_client

    async def get_client(self, client_id: str) -> Optional[dict]:
        """Get client details by ID"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.admin_url}/clients/{client_id}"
            ) as response:
                if response.status == 404:
                    return None
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"Failed to get client {client_id}: {error_text}") # Use self.logger
                    raise Exception(f"Failed to get client {client_id}: {error_text}")
                
                client = await response.json()
                return client

    async def delete_client(self, client_id: str) -> bool:
        """Delete a client by ID"""
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{self.admin_url}/clients/{client_id}"
            ) as response:
                if response.status not in [204, 404]:
                    error_text = await response.text()
                    self.logger.error(f"Failed to delete client {client_id}: {error_text}") # Use self.logger
                    raise Exception(f"Failed to delete client {client_id}: {error_text}")
                
                if response.status == 204:
                    self.clients.pop(client_id, None)
                    self.logger.info(f"Deleted client: {client_id}") # Use self.logger
                    return True
                return False

    async def create_clients(self, count: int) -> List[dict]:
        """Create multiple clients"""
        clients = []
        for _ in range(count):
            client = await self.create_client()
            clients.append(client)
        return clients

    def save_clients(self) -> None:
        """Save client data to file"""
        with open(self.clients_file, 'w') as f:
            json.dump(self.clients, f, indent=4)
        self.logger.info(f"Saved {len(self.clients)} clients to {self.clients_file}") # Use self.logger

    def load_clients(self) -> Dict[str, dict]:
        """Load client data from file"""
        try:
            with open(self.clients_file, 'r') as f:
                self.clients = json.load(f)
            self.logger.info(f"Loaded {len(self.clients)} clients from {self.clients_file}") # Use self.logger
        except FileNotFoundError:
            self.logger.warning(f"No clients file found at {self.clients_file}") # Use self.logger
        return self.clients

    async def cleanup_clients(self) -> None:
        """Delete all managed clients"""
        for client_id in list(self.clients.keys()):
            await self.delete_client(client_id)
        self.clients = {}
        self.logger.info("All clients cleaned up") # Use self.logger

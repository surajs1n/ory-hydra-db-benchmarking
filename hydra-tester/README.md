# Hydra OAuth2 Lifecycle Tester

A CLI tool for testing ORY Hydra's OAuth2 Authorization Code + Refresh Token flow.

## Features

- Manages multiple OAuth2 clients (up to 100)
- Simulates complete OAuth2 flow with PKCE
- **Supports parallel execution with multiple threads per client (up to 100)**
- Handles login/consent automatically
- Supports token refresh cycles
- Detailed, thread-safe logging and output
- Configurable via CLI or config file

## Installation

1. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Basic usage with default settings:
```bash
./run.py
```

Custom configuration with parallel execution:
```bash
./run.py \
  --clients 10 \
  --threads-per-client 5 \
  --refresh-count 10 \
  --refresh-interval 60 \
  --hydra-admin-url http://localhost:4445 \
  --hydra-public-url http://localhost:4444 \
  --scope "openid offline_access" \
  --verbose
```

### Command Line Options

| Option                 | Description                                      | Default                                          |
|------------------------|--------------------------------------------------|--------------------------------------------------|
| `--clients`            | Number of clients to manage (max 100)            | 5                                                |
| `--threads-per-client` | Number of parallel threads per client (max 100)  | 1                                                |
| `--refresh-count`      | Number of refresh cycles per client/thread       | 5                                                |
| `--refresh-interval`   | Seconds between refresh calls                    | 300                                              |
| `--hydra-admin-url`    | Hydra admin API URL                              | http://localhost:4445                            |
| `--hydra-public-url` | Hydra public API URL | http://localhost:4444 |
| `--redirect-uri` | Redirect URI used in flow | http://localhost/callback |
| `--scope` | OAuth2 scope string | openid offline_access user user.profile user.email |
| `--config` | Path to config file | config/default_config.json |
| `--log-file` | Path to log file | None (console only) |
| `--verbose` | Enable verbose logging | False |
| `--cleanup` | Clean up clients after test | False |

### Configuration File

The default configuration is in `config/default_config.json`. You can override it with your own:

```json
{
    "client_config": {
        "redirect_uris": ["http://localhost/callback"],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code", "id_token"],
        "token_endpoint_auth_method": "client_secret_post",
        "scope": "openid offline_access user user.profile user.email",
        "skip_consent": true
    },
    "oauth_settings": {
        "auth_url": "http://localhost:4444",  # Base URL without path
        "token_url": "http://localhost:4444",  # Base URL without path
        "admin_url": "http://localhost:4445",  # Admin URL
        "subject": "test-user@example.com",
        "session_data": {
            "access_token": {
                "user_id": "default-user-id"
            },
            "id_token": {
                "name": "Test User",
                "email": "test-user@example.com"
            }
        }
    }
}
```

### Environment Variables

The following environment variables are supported:

- `HYDRA_PUBLIC_URL`: Override the public API URL
- `HYDRA_ADMIN_URL`: Override the admin API URL
- `TEST_SUBJECT`: Override the test subject

## Output

The tool generates output files in the `output/` directory:

1.  `output/clients.json`: Contains credentials for all created/used clients.
2.  `output/tokens_client_{client_id}_thread_{thread_id}.json`: History of token issuance and refresh operations for each specific client and thread. This ensures thread-safe writing without file locks.

## Development

Project structure:
```
hydra-tester/
├── config/
│   └── default_config.json
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── client_manager.py
│   ├── oauth_flow.py
│   ├── consent_handler.py
│   └── utils/
│       ├── __init__.py
│       ├── config.py
│       ├── logger.py
│       └── pkce.py
├── output/
├── requirements.txt
├── run.py
└── README.md
```

## Error Handling

The tool includes comprehensive error handling:

- Client creation/management errors
- OAuth2 flow failures
- Token refresh failures
- Network connectivity issues

All errors are logged with appropriate context and stack traces in verbose mode.

## URL Configuration

The tool expects base URLs without paths:
- auth_url/token_url: Base public URL (e.g., http://localhost:4444)
  - Tool will append /oauth2/auth and /oauth2/token as needed
- admin_url: Base admin URL (e.g., http://localhost:4445)
  - Tool will append /admin and other paths as needed

## OAuth2 Flow Sequence

1. Initial authorization request
2. Handle login challenge
3. Make auth request with login verifier
4. Handle consent challenge
5. Make final auth request to get code
6. Exchange code for tokens

## Implementation Notes

- Uses PKCE (Proof Key for Code Exchange) for enhanced security
- Maintains cookies across the entire OAuth2 flow for session consistency
- Sets proper Content-Type headers for token requests (`application/x-www-form-urlencoded`)
- Handles login and consent challenges automatically
- Supports token refresh cycles with configurable intervals
- **Parallel Execution:** Uses a thread pool to run multiple OAuth flows concurrently for each client.
- **Thread Safety:** Employs thread-local storage and a thread-safe logging queue to ensure safe parallel operation.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License

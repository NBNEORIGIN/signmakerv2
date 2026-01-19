#!/usr/bin/env python3
"""
eBay OAuth 2.0 Authentication Helper

Handles OAuth token generation, storage, and refresh for eBay API access.
Supports both Authorization Code Grant (for user tokens) and Client Credentials (for app tokens).
"""

import base64
import json
import logging
import os
import time
import webbrowser
from dataclasses import dataclass
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, parse_qs, urlparse

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# eBay OAuth endpoints
EBAY_AUTH_URLS = {
    "sandbox": {
        "auth": "https://auth.sandbox.ebay.com/oauth2/authorize",
        "token": "https://api.sandbox.ebay.com/identity/v1/oauth2/token",
        "api_base": "https://api.sandbox.ebay.com",
    },
    "production": {
        "auth": "https://auth.ebay.com/oauth2/authorize",
        "token": "https://api.ebay.com/identity/v1/oauth2/token",
        "api_base": "https://api.ebay.com",
    },
}

# Required scopes for Inventory API, Account API, and Marketing API
EBAY_SCOPES = [
    "https://api.ebay.com/oauth/api_scope",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    "https://api.ebay.com/oauth/api_scope/sell.marketing",  # For Promoted Listings
]


@dataclass
class EbayTokens:
    """eBay OAuth tokens."""
    access_token: str
    refresh_token: str
    expires_at: float  # Unix timestamp
    token_type: str = "Bearer"
    
    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if token is expired or will expire within buffer_seconds."""
        return time.time() >= (self.expires_at - buffer_seconds)
    
    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EbayTokens":
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"],
            token_type=data.get("token_type", "Bearer"),
        )


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to capture OAuth callback."""
    
    auth_code = None
    
    def do_GET(self):
        """Handle GET request from OAuth callback."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if "code" in params:
            OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                </body></html>
            """)
        else:
            error = params.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"""
                <html><body>
                <h1>Authorization Failed</h1>
                <p>Error: {error}</p>
                </body></html>
            """.encode())
    
    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


class EbayAuth:
    """eBay OAuth 2.0 authentication manager."""
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        ru_name: str,
        environment: str = "production",
        token_file: Path = Path("ebay_tokens.json"),
    ):
        """
        Initialize eBay auth manager.
        
        Args:
            client_id: eBay App ID (Client ID)
            client_secret: eBay Cert ID (Client Secret)
            ru_name: eBay RuName (Redirect URL name from developer portal)
            environment: "sandbox" or "production"
            token_file: Path to store tokens
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.ru_name = ru_name
        self.environment = environment
        self.token_file = token_file
        self.urls = EBAY_AUTH_URLS[environment]
        self._tokens: Optional[EbayTokens] = None
    
    @property
    def api_base(self) -> str:
        """Get API base URL for current environment."""
        return self.urls["api_base"]
    
    def _get_basic_auth_header(self) -> str:
        """Generate Base64-encoded Basic auth header."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    def get_authorization_url(self, state: str = "ebay_auth") -> str:
        """
        Generate the authorization URL for user consent.
        
        Args:
            state: State parameter for CSRF protection
            
        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.ru_name,
            "scope": " ".join(EBAY_SCOPES),
            "state": state,
        }
        return f"{self.urls['auth']}?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, auth_code: str) -> EbayTokens:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            auth_code: Authorization code from OAuth callback
            
        Returns:
            EbayTokens object
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self._get_basic_auth_header(),
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self.ru_name,
        }
        
        response = requests.post(self.urls["token"], headers=headers, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        tokens = EbayTokens(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_at=time.time() + token_data["expires_in"],
            token_type=token_data.get("token_type", "Bearer"),
        )
        
        self._tokens = tokens
        self._save_tokens(tokens)
        
        return tokens
    
    def refresh_access_token(self, refresh_token: str) -> EbayTokens:
        """
        Refresh the access token using a refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New EbayTokens object
        """
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self._get_basic_auth_header(),
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": " ".join(EBAY_SCOPES),
        }
        
        response = requests.post(self.urls["token"], headers=headers, data=data)
        response.raise_for_status()
        
        token_data = response.json()
        
        # Refresh token may or may not be returned
        new_refresh_token = token_data.get("refresh_token", refresh_token)
        
        tokens = EbayTokens(
            access_token=token_data["access_token"],
            refresh_token=new_refresh_token,
            expires_at=time.time() + token_data["expires_in"],
            token_type=token_data.get("token_type", "Bearer"),
        )
        
        self._tokens = tokens
        self._save_tokens(tokens)
        
        return tokens
    
    def _save_tokens(self, tokens: EbayTokens) -> None:
        """Save tokens to file."""
        with self.token_file.open("w") as f:
            json.dump(tokens.to_dict(), f, indent=2)
        logging.info("Saved tokens to %s", self.token_file)
    
    def _load_tokens(self) -> Optional[EbayTokens]:
        """Load tokens from file."""
        if not self.token_file.exists():
            return None
        
        try:
            with self.token_file.open("r") as f:
                data = json.load(f)
            return EbayTokens.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            logging.warning("Failed to load tokens: %s", e)
            return None
    
    def get_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.
        
        Returns:
            Valid access token string
            
        Raises:
            RuntimeError: If no valid tokens available and auth required
        """
        # Try cached tokens first
        if self._tokens and not self._tokens.is_expired():
            return self._tokens.access_token
        
        # Try loading from file
        tokens = self._load_tokens()
        
        if tokens:
            if not tokens.is_expired():
                self._tokens = tokens
                return tokens.access_token
            
            # Try to refresh
            try:
                logging.info("Access token expired, refreshing...")
                tokens = self.refresh_access_token(tokens.refresh_token)
                return tokens.access_token
            except requests.HTTPError as e:
                logging.error("Failed to refresh token: %s", e)
                # Fall through to require re-auth
        
        raise RuntimeError(
            "No valid tokens available. Run 'python ebay_auth.py' to authenticate."
        )
    
    def get_auth_headers(self) -> dict:
        """Get headers with valid authorization for API requests."""
        token = self.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    def run_oauth_flow(self, port: int = 8080, manual: bool = True) -> EbayTokens:
        """
        Run the complete OAuth flow.
        
        Args:
            port: Local port for callback server (if not manual)
            manual: If True, user manually enters the auth code from URL
            
        Returns:
            EbayTokens object
        """
        if manual:
            return self._run_manual_oauth_flow()
        
        # Start local server
        server = HTTPServer(("localhost", port), OAuthCallbackHandler)
        OAuthCallbackHandler.auth_code = None
        
        # Generate and open auth URL
        auth_url = self.get_authorization_url()
        print(f"\nOpening browser for eBay authorization...")
        print(f"If browser doesn't open, visit:\n{auth_url}\n")
        webbrowser.open(auth_url)
        
        # Wait for callback
        print("Waiting for authorization callback...")
        while OAuthCallbackHandler.auth_code is None:
            server.handle_request()
        
        auth_code = OAuthCallbackHandler.auth_code
        server.server_close()
        
        # Exchange code for tokens
        print("Exchanging authorization code for tokens...")
        tokens = self.exchange_code_for_tokens(auth_code)
        
        print(f"\nAuthentication successful!")
        print(f"Access token expires at: {time.ctime(tokens.expires_at)}")
        print(f"Tokens saved to: {self.token_file}")
        
        return tokens
    
    def _run_manual_oauth_flow(self) -> EbayTokens:
        """
        Run OAuth flow with manual code entry.
        
        eBay requires HTTPS redirect URLs, so for localhost development
        we use their default success page and have the user copy the code.
        """
        auth_url = self.get_authorization_url()
        
        print("\n" + "="*60)
        print("eBay OAuth Authorization")
        print("="*60)
        print("\n1. Opening browser for eBay authorization...")
        print("\n2. After you authorize, eBay will redirect to a success page.")
        print("   Look at the URL in your browser's address bar.")
        print("   It will contain: ...&code=XXXXXX...")
        print("\n3. Copy the 'code' value from the URL and paste it below.")
        print("\nIf browser doesn't open, visit this URL:")
        print(f"\n{auth_url}\n")
        
        webbrowser.open(auth_url)
        
        print("-"*60)
        auth_code = input("Paste the authorization code here: ").strip()
        
        if not auth_code:
            raise ValueError("No authorization code provided")
        
        # Exchange code for tokens
        print("\nExchanging authorization code for tokens...")
        tokens = self.exchange_code_for_tokens(auth_code)
        
        print(f"\nAuthentication successful!")
        print(f"Access token expires at: {time.ctime(tokens.expires_at)}")
        print(f"Tokens saved to: {self.token_file}")
        
        return tokens


def get_ebay_auth_from_env(token_file: Path = None) -> EbayAuth:
    """
    Create EbayAuth instance from environment variables.
    
    Required environment variables:
        - EBAY_CLIENT_ID (App ID)
        - EBAY_CLIENT_SECRET (Cert ID)
        - EBAY_RU_NAME (Redirect URL name)
        
    Optional:
        - EBAY_ENVIRONMENT (sandbox/production, default: production)
    """
    client_id = os.environ.get("EBAY_CLIENT_ID")
    client_secret = os.environ.get("EBAY_CLIENT_SECRET")
    ru_name = os.environ.get("EBAY_RU_NAME")
    environment = os.environ.get("EBAY_ENVIRONMENT", "production")
    
    if not all([client_id, client_secret, ru_name]):
        missing = []
        if not client_id:
            missing.append("EBAY_CLIENT_ID")
        if not client_secret:
            missing.append("EBAY_CLIENT_SECRET")
        if not ru_name:
            missing.append("EBAY_RU_NAME")
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    if token_file is None:
        token_file = Path(__file__).parent / "ebay_tokens.json"
    
    return EbayAuth(
        client_id=client_id,
        client_secret=client_secret,
        ru_name=ru_name,
        environment=environment,
        token_file=token_file,
    )


def main():
    """Run OAuth flow to generate tokens."""
    import argparse
    
    parser = argparse.ArgumentParser(description="eBay OAuth 2.0 Authentication")
    parser.add_argument(
        "--port", type=int, default=8080,
        help="Local port for OAuth callback (default: 8080)"
    )
    parser.add_argument(
        "--environment", choices=["sandbox", "production"], default=None,
        help="Override EBAY_ENVIRONMENT"
    )
    args = parser.parse_args()
    
    # Override environment if specified
    if args.environment:
        os.environ["EBAY_ENVIRONMENT"] = args.environment
    
    try:
        auth = get_ebay_auth_from_env()
        auth.run_oauth_flow(port=args.port)
    except ValueError as e:
        print(f"\nError: {e}")
        print("\nPlease set the following environment variables in config.bat:")
        print("  set EBAY_CLIENT_ID=your_app_id")
        print("  set EBAY_CLIENT_SECRET=your_cert_id")
        print("  set EBAY_RU_NAME=your_ru_name")
        print("  set EBAY_ENVIRONMENT=production  (or sandbox)")
        return 1
    except Exception as e:
        logging.error("Authentication failed: %s", e)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

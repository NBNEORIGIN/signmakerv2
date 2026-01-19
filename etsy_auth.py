#!/usr/bin/env python3
"""
Etsy OAuth 2.0 Authentication Helper

Handles OAuth 2.0 Authorization Code Grant flow for Etsy API v3.
Supports token generation, storage, and automatic refresh.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import webbrowser
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# Etsy OAuth endpoints
ETSY_AUTH_URL = "https://www.etsy.com/oauth/connect"
ETSY_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"

# Default token file location
DEFAULT_TOKEN_FILE = Path(__file__).parent / "etsy_tokens.json"

# OAuth scopes required for listing management
REQUIRED_SCOPES = ["listings_r", "listings_w", "listings_d"]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to capture OAuth callback."""
    
    authorization_code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None
    
    def do_GET(self):
        """Handle GET request from OAuth callback."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if "code" in params:
            OAuthCallbackHandler.authorization_code = params["code"][0]
            OAuthCallbackHandler.state = params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: #F56400;">Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                </body></html>
            """)
        elif "error" in params:
            OAuthCallbackHandler.error = params.get("error_description", params["error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"""
                <html><body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: red;">Authorization Failed</h1>
                <p>{OAuthCallbackHandler.error}</p>
                </body></html>
            """.encode())
        else:
            self.send_response(400)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate PKCE code verifier and challenge.
    
    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate random code verifier (43-128 characters)
    code_verifier = secrets.token_urlsafe(64)[:128]
    
    # Generate code challenge (SHA256 hash, base64url encoded)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    
    return code_verifier, code_challenge


class EtsyAuth:
    """Etsy OAuth 2.0 authentication manager."""
    
    def __init__(
        self,
        api_key: str,
        redirect_uri: str = "http://localhost:3000/callback",
        token_file: Path = DEFAULT_TOKEN_FILE,
    ):
        """
        Initialize Etsy auth manager.
        
        Args:
            api_key: Etsy API key (keystring from developer portal)
            redirect_uri: OAuth redirect URI (must match app settings)
            token_file: Path to store/load tokens
        """
        self.api_key = api_key
        self.redirect_uri = redirect_uri
        self.token_file = Path(token_file)
        self._tokens: Optional[dict] = None
        self._load_tokens()
    
    def _load_tokens(self) -> None:
        """Load tokens from file if exists."""
        if self.token_file.exists():
            try:
                with self.token_file.open("r") as f:
                    self._tokens = json.load(f)
                logging.info("Loaded existing tokens from %s", self.token_file)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning("Failed to load tokens: %s", e)
                self._tokens = None
    
    def _save_tokens(self) -> None:
        """Save tokens to file."""
        if self._tokens:
            with self.token_file.open("w") as f:
                json.dump(self._tokens, f, indent=2)
            logging.info("Saved tokens to %s", self.token_file)
    
    @property
    def is_authenticated(self) -> bool:
        """Check if we have valid tokens."""
        return self._tokens is not None and "access_token" in self._tokens
    
    @property
    def access_token(self) -> Optional[str]:
        """Get current access token, refreshing if needed."""
        if not self._tokens:
            return None
        
        # Check if token is expired (with 5 min buffer)
        expires_at = self._tokens.get("expires_at", 0)
        if datetime.now().timestamp() > expires_at - 300:
            logging.info("Access token expired, refreshing...")
            if not self.refresh_token():
                return None
        
        return self._tokens.get("access_token")
    
    @property
    def shop_id(self) -> Optional[str]:
        """Get the shop ID from stored tokens."""
        return self._tokens.get("shop_id") if self._tokens else None
    
    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str, str]:
        """
        Generate OAuth authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Tuple of (authorization_url, code_verifier, state)
        """
        if state is None:
            state = secrets.token_urlsafe(16)
        
        code_verifier, code_challenge = generate_pkce_pair()
        
        params = {
            "response_type": "code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(REQUIRED_SCOPES),
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        
        url = f"{ETSY_AUTH_URL}?{urlencode(params)}"
        return url, code_verifier, state
    
    def exchange_code(self, authorization_code: str, code_verifier: str) -> bool:
        """
        Exchange authorization code for access token.
        
        Args:
            authorization_code: Code from OAuth callback
            code_verifier: PKCE code verifier used in authorization
            
        Returns:
            True if successful
        """
        data = {
            "grant_type": "authorization_code",
            "client_id": self.api_key,
            "redirect_uri": self.redirect_uri,
            "code": authorization_code,
            "code_verifier": code_verifier,
        }
        
        response = requests.post(ETSY_TOKEN_URL, data=data)
        
        if response.status_code != 200:
            logging.error("Token exchange failed: %s", response.text)
            return False
        
        token_data = response.json()
        
        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now().timestamp() + expires_in
        
        self._tokens = {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "expires_at": expires_at,
            "token_type": token_data.get("token_type", "Bearer"),
        }
        
        # Fetch and store shop ID
        shop_id = self._fetch_shop_id()
        if shop_id:
            self._tokens["shop_id"] = shop_id
        
        self._save_tokens()
        logging.info("Successfully obtained access token")
        return True
    
    def refresh_token(self) -> bool:
        """
        Refresh the access token using refresh token.
        
        Returns:
            True if successful
        """
        if not self._tokens or "refresh_token" not in self._tokens:
            logging.error("No refresh token available")
            return False
        
        data = {
            "grant_type": "refresh_token",
            "client_id": self.api_key,
            "refresh_token": self._tokens["refresh_token"],
        }
        
        response = requests.post(ETSY_TOKEN_URL, data=data)
        
        if response.status_code != 200:
            logging.error("Token refresh failed: %s", response.text)
            return False
        
        token_data = response.json()
        
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now().timestamp() + expires_in
        
        self._tokens["access_token"] = token_data["access_token"]
        self._tokens["refresh_token"] = token_data["refresh_token"]
        self._tokens["expires_at"] = expires_at
        
        self._save_tokens()
        logging.info("Successfully refreshed access token")
        return True
    
    def _fetch_shop_id(self) -> Optional[str]:
        """Fetch the user's shop ID from Etsy API."""
        if not self._tokens or "access_token" not in self._tokens:
            return None
        
        headers = {
            "Authorization": f"Bearer {self._tokens['access_token']}",
            "x-api-key": self.api_key,
        }
        
        # Get user info first
        response = requests.get(
            "https://openapi.etsy.com/v3/application/users/me",
            headers=headers,
        )
        
        if response.status_code != 200:
            logging.warning("Failed to fetch user info: %s", response.text)
            return None
        
        user_id = response.json().get("user_id")
        if not user_id:
            return None
        
        # Get user's shop
        response = requests.get(
            f"https://openapi.etsy.com/v3/application/users/{user_id}/shops",
            headers=headers,
        )
        
        if response.status_code != 200:
            logging.warning("Failed to fetch shop info: %s", response.text)
            return None
        
        shops = response.json().get("results", [])
        if shops:
            shop_id = str(shops[0]["shop_id"])
            logging.info("Found shop ID: %s", shop_id)
            return shop_id
        
        return None
    
    def authorize_interactive(self, port: int = 3000) -> bool:
        """
        Run interactive OAuth flow with local callback server.
        
        Args:
            port: Port for local callback server
            
        Returns:
            True if authorization successful
        """
        # Update redirect URI to match port
        self.redirect_uri = f"http://localhost:{port}/callback"
        
        # Generate authorization URL
        auth_url, code_verifier, state = self.get_authorization_url()
        
        print("\n" + "=" * 60)
        print("ETSY AUTHORIZATION")
        print("=" * 60)
        print("\nOpening browser for Etsy authorization...")
        print(f"\nIf browser doesn't open, visit:\n{auth_url}\n")
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Start local server to capture callback
        OAuthCallbackHandler.authorization_code = None
        OAuthCallbackHandler.state = None
        OAuthCallbackHandler.error = None
        
        server = HTTPServer(("localhost", port), OAuthCallbackHandler)
        server.timeout = 300  # 5 minute timeout
        
        print(f"Waiting for authorization callback on port {port}...")
        
        # Handle single request
        server.handle_request()
        server.server_close()
        
        if OAuthCallbackHandler.error:
            logging.error("Authorization failed: %s", OAuthCallbackHandler.error)
            return False
        
        if not OAuthCallbackHandler.authorization_code:
            logging.error("No authorization code received")
            return False
        
        if OAuthCallbackHandler.state != state:
            logging.error("State mismatch - possible CSRF attack")
            return False
        
        # Exchange code for token
        return self.exchange_code(OAuthCallbackHandler.authorization_code, code_verifier)
    
    def get_headers(self) -> dict:
        """
        Get headers for authenticated API requests.
        
        Returns:
            Dict with Authorization and x-api-key headers
        """
        token = self.access_token
        if not token:
            raise ValueError("Not authenticated - run authorize_interactive() first")
        
        return {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }


def main():
    """CLI for Etsy authentication."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Etsy OAuth Authentication")
    parser.add_argument("--authorize", action="store_true", help="Run interactive authorization flow")
    parser.add_argument("--refresh", action="store_true", help="Refresh access token")
    parser.add_argument("--status", action="store_true", help="Check authentication status")
    parser.add_argument("--port", type=int, default=3000, help="Callback server port")
    args = parser.parse_args()
    
    api_key = os.environ.get("ETSY_API_KEY")
    if not api_key:
        logging.error("ETSY_API_KEY environment variable not set")
        return 1
    
    auth = EtsyAuth(api_key=api_key)
    
    if args.authorize:
        if auth.authorize_interactive(port=args.port):
            print("\n✓ Authorization successful!")
            print(f"  Shop ID: {auth.shop_id}")
            print(f"  Tokens saved to: {auth.token_file}")
            return 0
        else:
            print("\n✗ Authorization failed")
            return 1
    
    elif args.refresh:
        if auth.refresh_token():
            print("✓ Token refreshed successfully")
            return 0
        else:
            print("✗ Token refresh failed")
            return 1
    
    elif args.status:
        if auth.is_authenticated:
            print("✓ Authenticated")
            print(f"  Shop ID: {auth.shop_id}")
            expires_at = auth._tokens.get("expires_at", 0)
            expires_dt = datetime.fromtimestamp(expires_at)
            print(f"  Token expires: {expires_dt.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("✗ Not authenticated")
            print("  Run with --authorize to authenticate")
        return 0
    
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    exit(main())

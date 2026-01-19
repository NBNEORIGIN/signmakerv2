#!/usr/bin/env python3
"""Quick script to exchange auth code for tokens."""
from ebay_auth import get_ebay_auth_from_env

code = "v^1.1#i^1#r^1#p^3#f^0#I^3#t^Ul41Xzc6NkY2QkNBMUFDQ0ZCNDI0MTg2Rjg1RTJCNzlEMjc1OENfMl8xI0VeMjYw"

auth = get_ebay_auth_from_env()
tokens = auth.exchange_code_for_tokens(code)
print(f"Success! Access token expires at: {tokens.expires_at}")
print(f"Tokens saved to: {auth.token_file}")

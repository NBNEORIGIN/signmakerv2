#!/usr/bin/env python3
"""Test R2 image upload functionality"""

import os
import sys
from pathlib import Path

# Check if R2 environment variables are set
print("Checking R2 environment variables...")
print(f"R2_ACCOUNT_ID: {os.environ.get('R2_ACCOUNT_ID', 'NOT SET')}")
print(f"R2_ACCESS_KEY_ID: {os.environ.get('R2_ACCESS_KEY_ID', 'NOT SET')}")
print(f"R2_SECRET_ACCESS_KEY: {'SET' if os.environ.get('R2_SECRET_ACCESS_KEY') else 'NOT SET'}")
print(f"R2_BUCKET_NAME: {os.environ.get('R2_BUCKET_NAME', 'NOT SET')}")
print(f"R2_PUBLIC_URL: {os.environ.get('R2_PUBLIC_URL', 'NOT SET')}")

# Check if all required variables are set
required_vars = ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET_NAME', 'R2_PUBLIC_URL']
missing = [var for var in required_vars if not os.environ.get(var)]

if missing:
    print(f"\nERROR: Missing environment variables: {', '.join(missing)}")
    print("\nMake sure to run this script with: call config.bat && python test_r2_upload.py")
    sys.exit(1)

print("\nAll R2 environment variables are set!")

# Try to import boto3
try:
    import boto3
    from botocore.config import Config
    print("boto3 is installed")
except ImportError:
    print("ERROR: boto3 is not installed. Run: pip install boto3")
    sys.exit(1)

# Try to connect to R2
print("\nTesting R2 connection...")
try:
    s3_client = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )
    
    # Try to list bucket contents (just first 5 items)
    response = s3_client.list_objects_v2(
        Bucket=os.environ['R2_BUCKET_NAME'],
        MaxKeys=5
    )
    
    print(f"✓ Successfully connected to R2 bucket: {os.environ['R2_BUCKET_NAME']}")
    
    if 'Contents' in response:
        print(f"  Bucket contains {response.get('KeyCount', 0)} items (showing first 5):")
        for obj in response.get('Contents', []):
            print(f"    - {obj['Key']}")
    else:
        print("  Bucket is empty")
    
    print("\n✓ R2 upload functionality is working correctly!")
    
except Exception as e:
    print(f"\n✗ ERROR connecting to R2: {e}")
    sys.exit(1)

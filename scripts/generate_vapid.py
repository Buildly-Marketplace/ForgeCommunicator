#!/usr/bin/env python3
"""
Generate VAPID keys for web push notifications.
Run this script and add the output to your environment variables.
"""

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64


def base64url_encode(data: bytes) -> str:
    """Encode bytes as base64url without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def generate_vapid_keys():
    """Generate a new VAPID key pair for web push."""
    # Generate a new ECDSA P-256 key pair
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()
    
    # Get private key in raw bytes (32 bytes for SECP256R1)
    private_numbers = private_key.private_numbers()
    private_bytes = private_numbers.private_value.to_bytes(32, 'big')
    
    # Get public key in uncompressed format (65 bytes: 0x04 + X + Y)
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    
    return base64url_encode(public_bytes), base64url_encode(private_bytes)


if __name__ == "__main__":
    public_key, private_key = generate_vapid_keys()
    
    print("\n=== VAPID Keys Generated ===\n")
    print("Add these to your environment variables:\n")
    print(f"VAPID_PUBLIC_KEY={public_key}")
    print(f"VAPID_PRIVATE_KEY={private_key}")
    print(f"VAPID_CONTACT_EMAIL=admin@buildly.io")
    print("\n============================\n")

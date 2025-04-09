# Copyright (c) 2025 Jeremiah Baker
# All rights reserved. This file is part of the Rubiqs Suite, developed by J. Baker Design.
#
# Unauthorized copying, distribution, modification, or use of this software is strictly prohibited
# without prior written consent from J. Baker Design. For commercial licensing inquiries, visit:
# https://jeremiahbakerdesign.com or contact support@jeremiahbakerdesign.com.

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
import base64
import json
import hashlib

# Load the public key
with open("app/keys/public_key.pem", "rb") as f:
    public_key = serialization.load_pem_public_key(f.read(), backend=default_backend())

# Extract numbers
numbers = public_key.public_numbers()
n_int = numbers.n
e_int = numbers.e

# Base64 URL encode
def b64url_uint(val):
    return base64.urlsafe_b64encode(val.to_bytes((val.bit_length() + 7) // 8, 'big')).rstrip(b'=').decode('utf-8')

jwk = {
    "kty": "RSA",
    "alg": "RS256",
    "use": "sig",
    "kid": "test-key",  # 🔐 must match what you used in JWT header
    "n": b64url_uint(n_int),
    "e": b64url_uint(e_int)
}

# Save to jwks.json
with open("app/keys/jwks.json", "w") as f:
    json.dump({"keys": [jwk]}, f, indent=2)

print("✅ Saved updated app/keys/jwks.json")

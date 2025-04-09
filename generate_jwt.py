# Copyright (c) 2025 Jeremiah Baker
# All rights reserved. This file is part of the Rubiqs Suite, developed by J. Baker Design.
#
# Unauthorized copying, distribution, modification, or use of this software is strictly prohibited
# without prior written consent from J. Baker Design. For commercial licensing inquiries, visit:
# https://jeremiahbakerdesign.com or contact support@jeremiahbakerdesign.com.

import jwt
import os
import uuid
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# Load private key
with open("app/keys/private_key.pem", "r") as f:
    private_key = f.read()

# Use strict UTC with a buffer of 5 minutes
now = datetime.now(timezone.utc)
future_iat = now + timedelta(seconds=30)  # 30-second buffer
future_exp = future_iat + timedelta(minutes=5)

payload = {
    "iss": os.getenv("CLIENT_ID"),
    "sub": os.getenv("CLIENT_ID"),
    "aud": os.getenv("PLATFORM_ISS"),
    "iat": int(future_iat.timestamp()),
    "exp": int(future_exp.timestamp()),
    "jti": str(uuid.uuid4())
}

headers = {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "test-key"
}

client_assertion = jwt.encode(
    payload,
    private_key,
    algorithm="RS256",
    headers=headers
)

print("✅ JWT generated (UTC-aware):\n")
print(client_assertion)

"""Clés de licence de test, signées par une paire générée pour la session."""

import base64
import json
from datetime import date

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

_PRIVATE = Ed25519PrivateKey.generate()
TEST_PUBLIC_KEY = base64.b64encode(
    _PRIVATE.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
).decode()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_key(features, expires=None, instance=None, client="Tests", private=None) -> str:
    payload = {"v": 1, "id": "test", "client": client, "features": features,
               "issued": date.today().isoformat(), "expires": expires, "instance": instance}
    signed = "AQM1." + _b64url(json.dumps(payload).encode())
    return f"{signed}.{_b64url((private or _PRIVATE).sign(signed.encode()))}"

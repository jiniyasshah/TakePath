"""Passphrase-protected, opt-in portable credential export.

Normal project files keep secrets out. This encrypted bundle is only created
by explicit portable export; nothing resembling a passphrase is serialized.
"""
from __future__ import annotations

import base64
import json
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .secure_store import validate_password

AAD = b"TakePath portable secure inputs v1"
SECRET_ID = re.compile(r"^[a-f0-9]{32}$")
MAX_CIPHERTEXT = 2_000_000


class PortableSecretError(ValueError):
    """Invalid passphrase, damaged file, or invalid encrypted values."""


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < 12:
        raise PortableSecretError("Use a passphrase with at least 12 characters.")
    return Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(
        passphrase.encode("utf-8"))


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _decode(value: str, size: int | None = None) -> bytes:
    if not isinstance(value, str) or len(value) > MAX_CIPHERTEXT:
        raise PortableSecretError("Invalid portable credential data.")
    try:
        result=base64.b64decode(value,validate=True)
    except Exception as exc:
        raise PortableSecretError("Damaged portable credential data.") from exc
    if size is not None and len(result) != size:
        raise PortableSecretError("Invalid portable credential size.")
    return result


def encrypt_secret_bundle(values: dict[str, str], passphrase: str) -> dict:
    """Encrypt only secure-action IDs and their values. Never embed the key."""
    if (not isinstance(values, dict) or not values or len(values) > 12000 or
        any(not isinstance(k,str) or not SECRET_ID.fullmatch(k)
            for k in values)):
        raise PortableSecretError("No valid secure input steps to export.")
    for value in values.values():
        validate_password(value)
    payload=json.dumps(values,sort_keys=True,separators=(",",":")).encode("utf-8")
    salt=os.urandom(16)
    nonce=os.urandom(12)
    ciphertext=AESGCM(_derive_key(passphrase,salt)).encrypt(nonce,payload,AAD)
    return {"version":1,"kdf":"scrypt-32768-8-1","cipher":"aes-256-gcm",
            "salt":_encode(salt),"nonce":_encode(nonce),"data":_encode(ciphertext)}


def decrypt_secret_bundle(bundle: dict, passphrase: str) -> dict[str,str]:
    """Authenticate BEFORE interpreting JSON. Never return partial plaintext."""
    if (not isinstance(bundle,dict) or bundle.get("version")!=1 or
        bundle.get("kdf")!="scrypt-32768-8-1" or
        bundle.get("cipher")!="aes-256-gcm"):
        raise PortableSecretError("Unsupported or invalid portable credentials.")
    salt=_decode(bundle.get("salt"),16)
    nonce=_decode(bundle.get("nonce"),12)
    ciphertext=_decode(bundle.get("data"))
    if not 16 <= len(ciphertext) <= MAX_CIPHERTEXT:
        raise PortableSecretError("Invalid portable credentials.")
    try:
        raw=AESGCM(_derive_key(passphrase,salt)).decrypt(nonce,ciphertext,AAD)
    except InvalidTag as exc:
        raise PortableSecretError("Incorrect passphrase or modified encrypted project.") from exc
    try:
        data=json.loads(raw.decode("utf-8"))
        if (not isinstance(data,dict) or len(data)>12000 or
            any(not isinstance(k,str) or not SECRET_ID.fullmatch(k) or
                not isinstance(v,str) for k,v in data.items())):
            raise ValueError("Invalid credential map")
        for value in data.values():
            validate_password(value)
        return data
    except (UnicodeError,ValueError,TypeError) as exc:
        raise PortableSecretError("Decrypted credential data is invalid.") from exc

"""Transparent, user-scoped encryption for TakePath project files.

Save, Save As, and Export use the SAME authenticated format. A random 256-bit
master key is held by the system credential vault, never in the project, in
QSettings, or in source code. Files are readable by the same OS user/device,
not secretly portable across arbitrary computers.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import tempfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .core import Project
from .secure_store import CredentialError, valid_reference, validate_password

FORMAT = "takepath-device-encrypted-v1"
KEY_REF = "a9431a43c00a4e33a246cab599690187"
AAD = b"TakePath encrypted project v1"
MAX_PLAINTEXT = 16 * 1024 * 1024
MAX_FILE = 25 * 1024 * 1024


class ProjectEncryptionError(ValueError):
    """No secure vault, unavailable device key, corruption, or invalid data."""


def _key(store, *, create: bool) -> bytes:
    if store is None:
        raise ProjectEncryptionError(
            "Secure system storage is unavailable. Cannot save without encryption. "
            "Enable Windows Credential Manager or the supported system keychain.")
    try:
        encoded = store.get(KEY_REF)
    except (CredentialError, OSError, ValueError) as exc:
        raise ProjectEncryptionError("Cannot access the OS-protected TakePath key.") from exc
    if encoded is None:
        if not create:
            raise ProjectEncryptionError(
                "This project was encrypted for a different Windows/macOS/Linux "
                "user profile or computer. Its device-protected key is unavailable.")
        encoded = base64.b64encode(os.urandom(32)).decode("ascii")
        try:
            store.set(KEY_REF, encoded)
            if store.get(KEY_REF) != encoded:
                raise ProjectEncryptionError("System key verification failed.")
        except (CredentialError, OSError, ValueError) as exc:
            raise ProjectEncryptionError("Could not securely store the TakePath encryption key.") from exc
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ProjectEncryptionError("The stored TakePath encryption key is invalid.") from exc
    if len(key) != 32:
        raise ProjectEncryptionError("The stored TakePath encryption key has an invalid size.")
    return key


def _values(values):
    if not isinstance(values, dict):
        raise ProjectEncryptionError("Invalid saved secure values.")
    result={}
    for action_id, value in values.items():
        if not valid_reference(action_id):
            raise ProjectEncryptionError("Invalid secure action reference.")
        try:
            result[action_id]=validate_password(value)
        except ValueError as exc:
            raise ProjectEncryptionError("Invalid protected input value.") from exc
    return result


def encrypt_project(project: Project, store, secure_values=None) -> bytes:
    """Always encrypt *all* project metadata/actions and optional secure inputs."""
    document={"project":project.to_dict(),"secure_values":_values(secure_values or {})}
    raw=json.dumps(document,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    if len(raw)>MAX_PLAINTEXT:
        raise ProjectEncryptionError("This project is too large to encrypt.")
    key=_key(store, create=True)
    nonce=os.urandom(12)
    encrypted=AESGCM(key).encrypt(nonce,raw,AAD)
    envelope={"format":FORMAT,"cipher":"aes-256-gcm",
              "nonce":base64.b64encode(nonce).decode("ascii"),
              "data":base64.b64encode(encrypted).decode("ascii")}
    return (json.dumps(envelope,separators=(",",":"))+"\n").encode("utf-8")


def decrypt_project(data: bytes, store) -> tuple[Project,dict[str,str]]:
    """Read new encrypted files or legacy plain JSON (for migration)."""
    if len(data)>MAX_FILE:
        raise ProjectEncryptionError("This project is too large to open.")
    try:
        envelope=json.loads(data.decode("utf-8"))
    except (UnicodeError,ValueError) as exc:
        raise ProjectEncryptionError("This project file is invalid or corrupted.") from exc
    if not isinstance(envelope,dict):
        raise ProjectEncryptionError("Invalid project format.")
    if envelope.get("format") != FORMAT:
        # Existing .vas.json projects remain importable, but the next save
        # automatically migrates them to fully encrypted files.
        if envelope.get("schema") in (1,2):
            return Project.from_dict(envelope),{}
        raise ProjectEncryptionError("Unsupported project encryption format.")
    if envelope.get("cipher") != "aes-256-gcm":
        raise ProjectEncryptionError("Unsupported encryption algorithm.")
    try:
        nonce=base64.b64decode(envelope["nonce"],validate=True)
        ciphertext=base64.b64decode(envelope["data"],validate=True)
        if len(nonce)!=12 or not 16<=len(ciphertext)<=MAX_PLAINTEXT+16:
            raise ValueError("Invalid ciphertext size")
    except (KeyError,ValueError,TypeError) as exc:
        raise ProjectEncryptionError("Encrypted project data is damaged.") from exc
    key=_key(store, create=False)  # never replace a missing key during open
    try:
        plaintext=AESGCM(key).decrypt(nonce,ciphertext,AAD)
    except InvalidTag as exc:
        raise ProjectEncryptionError(
            "This file could not be authenticated with the current device key. "
            "It may be corrupted or belong to another account.") from exc
    try:
        payload=json.loads(plaintext.decode("utf-8"))
        if not isinstance(payload,dict):
            raise ValueError("Invalid contents")
        project=Project.from_dict(payload["project"])
        values=_values(payload.get("secure_values",{}))
    except (ValueError,UnicodeError,TypeError,KeyError) as exc:
        raise ProjectEncryptionError("The encrypted project contains invalid data.") from exc
    return project,values


def save_encrypted_project(project: Project, destination, store, secure_values=None):
    """Atomically replace the destination with ciphertext, never a plaintext temp."""
    path=Path(destination)
    encrypted=encrypt_project(project,store,secure_values)
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile(mode="wb",dir=str(path.parent),
                                         prefix="."+path.name+".",suffix=".tmp",
                                         delete=False) as file:
            temp_path=Path(file.name)
            file.write(encrypted)
            file.flush()
            os.fsync(file.fileno())
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def load_encrypted_project(source, store) -> tuple[Project,dict[str,str]]:
    path=Path(source)
    if path.stat().st_size>MAX_FILE:
        raise ProjectEncryptionError("This project is too large to open.")
    return decrypt_project(path.read_bytes(),store)

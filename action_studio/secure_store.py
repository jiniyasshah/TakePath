"""User-scoped protected input storage, separate from portable .vas.json projects.

Windows Credential Manager uses Windows' per-user credential protection.
No fallback to plaintext files, Qt settings, environment variables or clipboard.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt
import re
import sys

MAX_PASSWORD_CHARS = 512
_REF_RE = re.compile(r"^[a-f0-9]{32}$")
_PREFIX = 'VisualActionStudio.secure.v1.'
_CRED_TYPE_GENERIC = 1
_CRED_PERSIST_LOCAL_MACHINE = 2


class CredentialError(RuntimeError):
    pass


def valid_reference(ref: str) -> bool:
    return isinstance(ref, str) and bool(_REF_RE.fullmatch(ref))


def validate_password(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_PASSWORD_CHARS:
        raise ValueError(f'Password must contain 1–{MAX_PASSWORD_CHARS} characters.')
    return value


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ('Flags', wt.DWORD), ('Type', wt.DWORD), ('TargetName', wt.LPWSTR),
        ('Comment', wt.LPWSTR), ('LastWritten', wt.FILETIME),
        ('CredentialBlobSize', wt.DWORD), ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)),
        ('Persist', wt.DWORD), ('AttributeCount', wt.DWORD),
        ('Attributes', ctypes.c_void_p), ('TargetAlias', wt.LPWSTR), ('UserName', wt.LPWSTR),
    ]


class WindowsCredentialStore:
    """Store only opaque UUID references in a project, never secrets.

    CredRead / CredWrite with CRED_PERSIST_LOCAL_MACHINE store values in the
    currently signed-in Windows user's Credential Manager. No cloud sync is
    intentionally requested. Credentials remain accessible to other programs
    running as the same Windows user; this isn't isolation from malware.
    """
    def __init__(self):
        if sys.platform != 'win32':
            raise CredentialError('Windows Credential Manager is only available on Windows.')
        lib = ctypes.WinDLL('Advapi32.dll', use_last_error=True)
        self._read = lib.CredReadW
        self._read.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.POINTER(ctypes.POINTER(_CREDENTIALW))]
        self._read.restype = wt.BOOL
        self._write = lib.CredWriteW
        self._write.argtypes = [ctypes.POINTER(_CREDENTIALW), wt.DWORD]
        self._write.restype = wt.BOOL
        self._delete = lib.CredDeleteW
        self._delete.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD]
        self._delete.restype = wt.BOOL
        self._free = lib.CredFree
        self._free.argtypes = [ctypes.c_void_p]
        self._free.restype = None

    @staticmethod
    def _name(ref: str) -> str:
        if not valid_reference(ref):
            raise ValueError('Invalid credential reference.')
        return _PREFIX + ref

    def get(self, ref: str) -> str | None:
        ptr = ctypes.POINTER(_CREDENTIALW)()
        if not self._read(self._name(ref), _CRED_TYPE_GENERIC, 0, ctypes.byref(ptr)):
            code = ctypes.get_last_error()
            if code == 1168:  # ERROR_NOT_FOUND
                return None
            raise CredentialError(f'Could not read Windows credential (error {code}).')
        try:
            cred = ptr.contents
            if cred.CredentialBlobSize % 2 or cred.CredentialBlobSize > MAX_PASSWORD_CHARS * 4:
                raise CredentialError('Saved credential has an invalid size.')
            # CredRead returns a protected credential blob owned by Windows.
            data = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
            return data.decode('utf-16-le')
        finally:
            self._free(ctypes.cast(ptr, ctypes.c_void_p))

    def set(self, ref: str, secret: str) -> None:
        self._name(ref)
        validate_password(secret)
        blob = bytearray(secret.encode('utf-16-le'))
        if len(blob) > 2560:  # Windows CRED_MAX_CREDENTIAL_BLOB_SIZE is often 2560
            raise ValueError('Password exceeds Windows Credential Manager size limit.')
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer(blob)
        cred = _CREDENTIALW()
        cred.Type = _CRED_TYPE_GENERIC
        cred.TargetName = self._name(ref)
        cred.Comment = 'Visual Action Studio secure replay input'
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        cred.Persist = _CRED_PERSIST_LOCAL_MACHINE
        try:
            if not self._write(ctypes.byref(cred), 0):
                raise CredentialError(f'Could not save Windows credential (error {ctypes.get_last_error()}).')
        finally:
            for i in range(len(blob)):
                blob[i] = 0
            del buffer

    def delete(self, ref: str) -> None:
        if not self._delete(self._name(ref), _CRED_TYPE_GENERIC, 0):
            code = ctypes.get_last_error()
            if code != 1168:
                raise CredentialError(f'Could not delete Windows credential (error {code}).')


class KeyringCredentialStore:
    """macOS Keychain or Linux Secret Service through the system keyring.

    Never uses the insecure plaintext/file-backend fallbacks. An unavailable
    system keychain forces session-only credential use instead.
    """
    SERVICE = 'TakePath.secure.v1'

    def __init__(self):
        try:
            import keyring
            from keyring.backends.fail import Keyring as FailKeyring
            from keyring.backends.null import Keyring as NullKeyring
            backend = keyring.get_keyring()
            if isinstance(backend, (FailKeyring, NullKeyring)) or getattr(backend, 'priority', 0) <= 0:
                raise CredentialError('No usable system credential store is configured.')
            # Restrict to specific native backends; avoid unprotected third-party stores.
            module = type(backend).__module__
            approved = (sys.platform == 'darwin' and module.startswith('keyring.backends.macOS')) or (
                sys.platform.startswith('linux') and module.startswith('keyring.backends.SecretService'))
            if not approved:
                raise CredentialError('Secure storage requires macOS Keychain or Linux Secret Service.')
            self.keyring = keyring
        except CredentialError:
            raise
        except Exception as exc:
            raise CredentialError(f'System keychain unavailable: {exc}') from exc

    def get(self, ref: str):
        if not valid_reference(ref):
            raise ValueError('Invalid credential reference.')
        return self.keyring.get_password(self.SERVICE, ref)

    def set(self, ref: str, secret: str):
        if not valid_reference(ref):
            raise ValueError('Invalid credential reference.')
        self.keyring.set_password(self.SERVICE, ref, validate_password(secret))

    def delete(self, ref: str):
        if not valid_reference(ref):
            raise ValueError('Invalid credential reference.')
        try:
            self.keyring.delete_password(self.SERVICE, ref)
        except self.keyring.errors.PasswordDeleteError:
            pass


def credential_store():
    try:
        return WindowsCredentialStore() if sys.platform == 'win32' else KeyringCredentialStore()
    except (CredentialError, ImportError, OSError):
        return None  # Session-only secure inputs remain available.

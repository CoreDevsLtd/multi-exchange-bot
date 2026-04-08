"""
Simple application-side encryption helper using Fernet symmetric encryption.
Set ENCRYPTION_KEY env var to a urlsafe-base64 32-byte key (Fernet). Use
"from secrets_manager import encrypt_credentials_dict, decrypt_credentials_dict"

If ENCRYPTION_KEY not set, functions are no-ops (returns values unchanged).
"""
import os
from typing import Dict, Any

ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
_f = None
if ENCRYPTION_KEY:
    try:
        from cryptography.fernet import Fernet
        _f = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
    except Exception:
        _f = None


def generate_key() -> str:
    """Generate a new Fernet key (base64 urlsafe)."""
    try:
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()
    except Exception:
        raise RuntimeError('cryptography not available')


def _encrypt_string(s: str) -> str:
    if not s or not _f:
        return s
    try:
        token = _f.encrypt(s.encode()).decode()
        return f"ENC:{token}"
    except Exception:
        return s


def _decrypt_string(s: str) -> str:
    if not s or not _f:
        return s
    try:
        if isinstance(s, str) and s.startswith('ENC:'):
            token = s[4:]
            return _f.decrypt(token.encode()).decode()
    except Exception:
        pass
    return s


def encrypt_credentials_dict(creds: Dict[str, Any]) -> Dict[str, Any]:
    if not creds or not isinstance(creds, dict):
        return creds
    if not _f:
        return creds
    out = {}
    for k, v in creds.items():
        if v is None:
            out[k] = v
            continue
        # Only encrypt strings
        if isinstance(v, str) and v:
            out[k] = _encrypt_string(v)
        else:
            out[k] = v
    return out


def decrypt_credentials_dict(creds: Dict[str, Any]) -> Dict[str, Any]:
    if not creds or not isinstance(creds, dict):
        return creds
    if not _f:
        return creds
    out = {}
    for k, v in creds.items():
        if isinstance(v, str) and v.startswith('ENC:'):
            out[k] = _decrypt_string(v)
        else:
            out[k] = v
    return out

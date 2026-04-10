from __future__ import annotations

import os

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials, db

_app: firebase_admin.App | None = None


def init(
    service_account_path: str | None = None,
    database_url: str | None = None,
) -> None:
    """Initialize the Firebase app. Safe to call multiple times; only initializes once.

    If arguments are omitted, reads FIREBASE_SERVICE_ACCOUNT and FIREBASE_URL
    from environment variables (loaded from .env if present).
    """
    global _app
    if _app is not None:
        return

    load_dotenv()
    path = service_account_path or os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    url = database_url or os.environ.get("FIREBASE_URL")

    if not path:
        raise ValueError(
            "service_account_path not provided and FIREBASE_SERVICE_ACCOUNT not set."
        )
    if not url:
        raise ValueError(
            "database_url not provided and FIREBASE_URL not set."
        )

    cred = credentials.Certificate(path)
    _app = firebase_admin.initialize_app(cred, {"databaseURL": url})


def ref(path: str) -> db.Reference:
    if _app is None:
        raise RuntimeError("erts_firebase not initialized — call init() first.")
    return db.reference(path, app=_app)

"""Quick validation to ensure required secrets are present before running or deploying."""
from __future__ import annotations

import os
import sys
from typing import Iterable


BACKEND_REQUIRED = (
    "GOOGLE_API_KEY",
    "TRANSPARENCIA_API_KEY",
)

FRONTEND_REQUIRED = (
    "NEXTAUTH_SECRET",
    "NEXT_PUBLIC_API_URL",
)


BACKEND_DB_REQUIRED = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)


def missing(keys: Iterable[str]) -> list[str]:
    return [k for k in keys if not os.getenv(k)]


def main() -> int:
    missing_backend = missing(BACKEND_REQUIRED)
    missing_frontend = missing(FRONTEND_REQUIRED)
    missing_db = missing(BACKEND_DB_REQUIRED)

    if not missing_backend and not missing_frontend and not missing_db:
        print("All required secrets are available.")
        return 0

    if missing_backend:
        print("[backend] Missing:", ", ".join(missing_backend))
    if missing_frontend:
        print("[frontend] Missing:", ", ".join(missing_frontend))
    if missing_db:
        print("[database] Missing:", ", ".join(missing_db))
    return 1


if __name__ == "__main__":
    sys.exit(main())

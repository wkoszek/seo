"""Common utilities for SEO tool."""

import json
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
CWD = Path.cwd()

# Credentials stored in current working directory (per-project)
CLIENT_SECRETS_FILE = CWD / ".client_secrets.json"
TOKEN_FILE = CWD / ".token.json"
REPORTS_DIR = CWD / "reports" / "seo"
SCOPES = ["https://www.googleapis.com/auth/webmasters"]  # Full access for sitemap submission

# Site configuration
SITE_URL = "sc-domain:bayareapolishgroup.com"
SITEMAP_URL = "https://www.bayareapolishgroup.com/sitemap.xml"

# Google Cloud Console URLs
GOOGLE_CLOUD_CONSOLE = "https://console.cloud.google.com/"
GOOGLE_CLOUD_API_LIBRARY = "https://console.cloud.google.com/apis/library/searchconsole.googleapis.com"
GOOGLE_CLOUD_CREDENTIALS = "https://console.cloud.google.com/apis/credentials"


def print_header(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(num: int, text: str):
    print(f"  [{num}] {text}")


def print_success(text: str):
    print(f"  ✓ {text}")


def print_error(text: str):
    print(f"  ✗ {text}")


def print_info(text: str):
    print(f"  → {text}")


def print_progress(current: int, total: int, prefix: str = ""):
    """Print progress: done/total"""
    pct = (current / total * 100) if total else 0
    print(f"\r  {prefix}{current}/{total} ({pct:.0f}%)", end="", flush=True)


def check_dependencies():
    """Check if required packages are installed."""
    missing = []
    try:
        import httpx
    except ImportError:
        missing.append("httpx")
    try:
        import pandas
    except ImportError:
        missing.append("pandas")
    try:
        from google.oauth2.credentials import Credentials
    except ImportError:
        missing.append("google-auth")

    if missing:
        print_error("Missing dependencies detected.")
        print()
        print("Install with uv:")
        print(f"  cd {SCRIPT_DIR}")
        print("  uv sync")
        print()
        print("Or with pip:")
        print(f"  pip install -r {SCRIPT_DIR}/requirements.txt")
        print()
        return False
    return True


def get_credentials():
    """Get valid credentials."""
    if not CLIENT_SECRETS_FILE.exists():
        print_error("Run 'seo init' first.")
        return None
    if not TOKEN_FILE.exists():
        print_error("Run 'seo auth' first.")
        return None

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            print_error("Token invalid. Run 'seo auth'.")
            return None
    return creds

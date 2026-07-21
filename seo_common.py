"""Common utilities for SEO tool."""

import json
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).parent
CWD = Path.cwd()

# Credentials: client secrets per-project, token global in ~/.config/seo/
CLIENT_SECRETS_FILE = CWD / ".client_secrets.json"
TOKEN_FILE = Path.home() / ".config" / "seo" / "token.json"
REPORTS_DIR = CWD / "reports" / "seo"
SCOPES = [
    "https://www.googleapis.com/auth/webmasters",       # Search Console
    "https://www.googleapis.com/auth/analytics.edit",   # GA Admin API (create properties)
    "https://www.googleapis.com/auth/analytics.readonly",  # GA4 Data API (read reports)
    "https://www.googleapis.com/auth/siteverification", # Site Verification API (verify command)
]

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


OP_CLIENT_SECRETS_REF = "op://infra/2woumqmg4y7vq55nf6e4o2qj2y/json"
OP_TOKEN_REF = "op://infra/4p77rxpejqgnsr5tp2kfjf4fr4/json"


def _load_client_secrets_file():
    """Return path to client secrets, sourcing from envvar or 1Password if needed."""
    import os, subprocess, tempfile

    # Already exists locally
    if CLIENT_SECRETS_FILE.exists():
        return CLIENT_SECRETS_FILE

    # Env var: can be a file path or raw JSON
    env_val = os.environ.get("GOOGLE_CLIENT_SECRETS", "")
    if env_val:
        p = Path(env_val)
        if p.exists():
            return p
        # Treat as raw JSON — write to temp file
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(env_val)
        return tmp

    # 1Password
    try:
        result = subprocess.run(
            ["op", "read", OP_CLIENT_SECRETS_REF],
            capture_output=True, text=True, check=True
        )
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(result.stdout.strip())
        return tmp
    except Exception:
        pass

    return None


def _load_token_file():
    """Return path to token file, sourcing from 1Password if needed."""
    import os, subprocess, tempfile

    if TOKEN_FILE.exists():
        return TOKEN_FILE

    env_val = os.environ.get("GOOGLE_TOKEN_JSON", "")
    if env_val:
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(env_val)
        return tmp

    try:
        result = subprocess.run(
            ["op", "read", OP_TOKEN_REF],
            capture_output=True, text=True, check=True
        )
        tmp = Path(tempfile.mktemp(suffix=".json"))
        tmp.write_text(result.stdout.strip())
        return tmp
    except Exception:
        pass

    return None


def get_credentials():
    """Get valid credentials."""
    secrets_file = _load_client_secrets_file()
    if not secrets_file:
        print_error("No client secrets found. Options:")
        print_error("  1. Run 'seo init' to set up .client_secrets.json")
        print_error("  2. Set GOOGLE_CLIENT_SECRETS env var (path or JSON)")
        print_error(f"  3. Store in 1Password at {OP_CLIENT_SECRETS_REF}")
        return None

    token_file = _load_token_file()
    if not token_file:
        print_error("No token found. Run 'seo auth' first.")
        return None

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            print_error("Token invalid. Run 'seo auth'.")
            return None
    return creds

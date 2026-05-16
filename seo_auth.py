"""Authenticate with Google."""

from seo_common import (
    CLIENT_SECRETS_FILE, TOKEN_FILE, SCOPES,
    check_dependencies, print_header, print_success, print_error, print_info,
    _load_client_secrets_file
)


def cmd_auth(args):
    """Authenticate with Google."""
    if not check_dependencies():
        return 1

    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request

    print_header("SEO Tool - Authentication")

    secrets_file = _load_client_secrets_file()
    if not secrets_file:
        print_error("No credentials found. Run 'seo init' first, or set GOOGLE_CLIENT_SECRETS.")
        return 1
    CLIENT_SECRETS_FILE_RESOLVED = secrets_file

    if TOKEN_FILE.exists() and not args.force:
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
            if creds and creds.valid:
                print_success("Already authenticated!")
                return 0
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())
                print_success("Token refreshed!")
                return 0
        except:
            pass

    print_info("Opening browser for authentication...")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_FILE_RESOLVED), SCOPES)
    creds = flow.run_local_server(port=8080)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    print_success("Authentication successful!")
    return 0

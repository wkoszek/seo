"""List verified sites."""

from seo_common import (
    check_dependencies, get_credentials, print_header
)


def cmd_sites(args):
    """List verified sites."""
    if not check_dependencies():
        return 1

    from googleapiclient.discovery import build

    print_header("Verified Sites")

    creds = get_credentials()
    if not creds:
        return 1

    service = build("searchconsole", "v1", credentials=creds)
    response = service.sites().list().execute()

    for site in response.get("siteEntry", []):
        print(f"  • {site['siteUrl']} ({site['permissionLevel']})")
    return 0

"""Check configuration status."""

from seo_common import (
    CLIENT_SECRETS_FILE, TOKEN_FILE, SITE_URL, SITEMAP_URL,
    print_header, print_success, print_error, print_info
)


def cmd_status(args):
    """Check configuration status."""
    print_header("SEO Tool - Status")

    print("Credentials:")
    if CLIENT_SECRETS_FILE.exists():
        print_success("client_secrets.json found")
    else:
        print_error("client_secrets.json missing - run 'seo init'")
        return 1

    print("\nAuthentication:")
    if TOKEN_FILE.exists():
        print_success("token.json found")
    else:
        print_error("Not authenticated - run 'seo auth'")
        return 1

    print("\nConfiguration:")
    print_info(f"Site: {SITE_URL}")
    print_info(f"Sitemap: {SITEMAP_URL}")

    print()
    print_success("Ready! Run 'seo report' or 'seo crawl'")
    return 0

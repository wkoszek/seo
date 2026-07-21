"""Verify site ownership via Google Site Verification API, then add to Search Console."""

from seo_common import (
    get_credentials,
    print_header, print_success, print_error, print_info,
)

# method key → (API method string, site type)
# INET_DOMAIN = bare domain (dns only)
# SITE        = URL-prefix (https://...) required for file/meta/analytics
METHODS = {
    "analytics": ("ANALYTICS", "SITE"),
    "dns":       ("DNS_TXT",   "INET_DOMAIN"),
    "file":      ("FILE",      "SITE"),
    "meta":      ("META",      "SITE"),
}


def _site_body(method_key, domain):
    """Return the site dict for getToken / insert based on method type."""
    _, site_type = METHODS[method_key]
    if site_type == "SITE":
        return {"type": "SITE", "identifier": f"https://{domain}/"}
    return {"type": "INET_DOMAIN", "identifier": domain}


def cmd_verify(args):
    """Verify domain ownership and add to Google Search Console."""
    domain = args.domain.lstrip("https://").lstrip("http://").rstrip("/")
    method_key = args.method.lower()

    if method_key not in METHODS:
        print_error(f"Unknown method '{method_key}'. Choose: {', '.join(METHODS)}")
        return 1

    method, _ = METHODS[method_key]

    try:
        from googleapiclient.discovery import build
    except ImportError:
        print_error("google-api-python-client not installed. Run: uv sync")
        return 1

    creds = get_credentials()
    if not creds:
        return 1

    svc = build("siteVerification", "v1", credentials=creds)

    if args.confirm:
        return _do_verify(svc, domain, method_key)

    # --- Step 1: get token and show instructions ---
    if method_key == "analytics":
        # No token step needed for Analytics — GA presence is the proof.
        print_header(f"Verify via Google Analytics: {domain}")
        print_info("GA must already be firing on the live site.")
        print_info("Run with --confirm to complete verification.")
        print()
        return 0

    print_header(f"Get Verification Token: {domain} ({method_key})")

    try:
        resp = svc.webResource().getToken(body={
            "site": _site_body(method_key, domain),
            "verificationMethod": method,
        }).execute()
    except Exception as e:
        print_error(f"getToken failed: {e}")
        return 1

    token = resp.get("token", "")

    if method_key == "dns":
        print_info("Add this TXT record to your DNS:")
        print()
        print(f"    Name:  @  (or {domain})")
        print(f"    Type:  TXT")
        print(f"    Value: {token}")
        print()
        print_info("After DNS propagates, run:")
        print_info(f"    seo verify {domain} --method dns --confirm")

    elif method_key == "file":
        # Token is the filename; content is just the token string
        filename = token
        print_info(f"Create this file at the site root:")
        print()
        print(f"    Path:    static/{filename}")
        print(f"    Content: {token}")
        print()
        print_info(f"It must be reachable at: https://{domain}/{filename}")
        print_info("After deploying, run:")
        print_info(f"    seo verify {domain} --method file --confirm")

    elif method_key == "meta":
        print_info("Add this tag inside <head> of your homepage:")
        print()
        print(f"    {token}")
        print()
        print_info("After deploying, run:")
        print_info(f"    seo verify {domain} --method meta --confirm")

    return 0


def _do_verify(svc, domain, method_key):
    """Call webResource.insert to complete verification, then add to Search Console."""
    method, site_type = METHODS[method_key]
    print_header(f"Complete Verification: {domain}")

    try:
        result = svc.webResource().insert(
            verificationMethod=method,
            body={"site": _site_body(method_key, domain)},
        ).execute()
        print_success(f"Verified: {result.get('id', domain)}")
    except Exception as e:
        print_error(f"Verification failed: {e}")
        return 1

    # Add to Search Console — domain property for INET_DOMAIN, URL-prefix for SITE
    print()
    print_info("Adding to Google Search Console...")
    if site_type == "INET_DOMAIN":
        sc_url = f"sc-domain:{domain}"
    else:
        sc_url = f"https://{domain}/"
    try:
        from googleapiclient.discovery import build as gsc_build
        sc = gsc_build("searchconsole", "v1", credentials=svc._http.credentials)
        sc.sites().add(siteUrl=sc_url).execute()
        print_success(f"Added {sc_url} to Search Console")
    except Exception as e:
        # May already exist — not fatal
        print_info(f"Search Console add skipped: {e}")

    print()
    print_info(f"Submit sitemap with:  seo sitemap {domain}")
    return 0

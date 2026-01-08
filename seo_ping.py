"""Ping search engines with all sitemaps."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from seo_common import (
    SITE_URL, SITEMAP_URL, SCRIPT_DIR,
    get_credentials, check_dependencies,
    print_header, print_success, print_error, print_info
)

# IndexNow key file location (in static/ so Hugo copies it to site root)
INDEXNOW_KEY_FILE = SCRIPT_DIR.parent.parent / "static" / "indexnow-key.txt"


def cmd_ping(args):
    """Ping search engines with all sitemaps."""
    if not check_dependencies():
        return 1

    import httpx
    from googleapiclient.discovery import build

    print_header("Ping Search Engines")
    print_info(f"Sitemap: {SITEMAP_URL}")
    print()

    # Fetch and parse sitemaps
    sitemaps = fetch_sitemaps_list()
    if not sitemaps:
        print_error("Failed to fetch sitemaps")
        return 1

    print(f"Found {len(sitemaps)} sitemap(s)")
    print()

    # Google - use Search Console API
    print("Google (Search Console API):")
    google_success = ping_google_api(sitemaps)

    # Bing/IndexNow
    print("Bing (IndexNow):")
    indexnow_success = ping_indexnow(sitemaps)

    print()
    return 0 if (google_success and indexnow_success) else 1


def fetch_sitemaps_list():
    """Fetch list of all sitemaps from sitemap index."""
    import httpx

    sitemaps = []
    try:
        client = httpx.Client(timeout=30, follow_redirects=True)
        resp = client.get(SITEMAP_URL)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

        # Add main sitemap
        sitemaps.append(SITEMAP_URL)

        # Check if sitemap index (contains other sitemaps)
        for loc in root.findall(".//sm:sitemap/sm:loc", ns):
            if loc.text and loc.text not in sitemaps:
                sitemaps.append(loc.text)

    except Exception as e:
        print_error(f"Failed to fetch sitemap: {e}")

    return sitemaps


def ping_google_api(sitemaps):
    """Submit sitemaps via Google Search Console API."""
    from googleapiclient.discovery import build

    creds = get_credentials()
    if not creds:
        print_error("  Not authenticated. Run 'seo auth' first.")
        return False

    try:
        service = build("searchconsole", "v1", credentials=creds)
        success = 0
        failed = 0

        for sitemap in sitemaps:
            try:
                service.sitemaps().submit(siteUrl=SITE_URL, feedpath=sitemap).execute()
                success += 1
            except Exception as e:
                print_error(f"  Failed: {sitemap} - {e}")
                failed += 1

        if failed == 0:
            print_success(f"  {success}/{len(sitemaps)} sitemaps submitted")
        else:
            print_error(f"  {success}/{len(sitemaps)} succeeded, {failed} failed")

        return failed == 0

    except Exception as e:
        print_error(f"  API error: {e}")
        return False


def ping_indexnow(sitemaps):
    """Submit sitemaps via IndexNow protocol."""
    import httpx

    # Check for IndexNow key
    if not INDEXNOW_KEY_FILE.exists():
        print_info("  IndexNow not configured.")
        print_info(f"  To enable: create {INDEXNOW_KEY_FILE}")
        print_info("  Content: your-random-key (8-128 alphanumeric chars)")
        print_info("  Hugo will copy it to site root for verification.")
        return True  # Not an error, just not configured

    key = INDEXNOW_KEY_FILE.read_text().strip()
    if len(key) < 8 or len(key) > 128:
        print_error(f"  Invalid key length ({len(key)}). Must be 8-128 chars.")
        return False

    # Extract host from sitemap URL
    host = SITEMAP_URL.split("://")[1].split("/")[0]

    # Submit each sitemap URL to IndexNow
    client = httpx.Client(timeout=30)
    success = 0
    failed = 0

    for sitemap in sitemaps:
        try:
            resp = client.post(
                "https://api.indexnow.org/indexnow",
                json={
                    "host": host,
                    "key": key,
                    "keyLocation": f"https://{host}/{key}.txt",
                    "urlList": [sitemap]
                },
                headers={"Content-Type": "application/json"}
            )
            if resp.status_code in (200, 202):
                success += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    if failed == 0:
        print_success(f"  {success}/{len(sitemaps)} sitemaps submitted")
    else:
        print_error(f"  {success}/{len(sitemaps)} succeeded, {failed} failed")

    return failed == 0

"""Submit sitemap to Google Search Console (and optionally Bing/IndexNow)."""

import xml.etree.ElementTree as ET

from seo_common import (
    get_credentials,
    print_header, print_success, print_error, print_info,
)


def cmd_sitemap(args):
    """Submit sitemap for a domain to Google Search Console."""
    domain = args.domain.lstrip("https://").lstrip("http://").rstrip("/")
    # Use URL-prefix property by default; --domain-property switches to sc-domain:
    if getattr(args, "domain_property", False):
        site_url = f"sc-domain:{domain}"
    else:
        site_url = f"https://{domain}/"
    sitemap_url = f"https://{domain}/sitemap.xml"

    print_header(f"Submit Sitemap: {domain}")
    print_info(f"Site:    {site_url}")
    print_info(f"Sitemap: {sitemap_url}")
    print()

    # Verify sitemap is reachable and collect all URLs in it
    sitemaps = _fetch_sitemap_urls(sitemap_url)
    if not sitemaps:
        print_error("Could not fetch sitemap — is the site live?")
        return 1

    print_info(f"Found {len(sitemaps)} sitemap URL(s)")
    for s in sitemaps:
        print_info(f"  {s}")
    print()

    return _submit_to_gsc(site_url, sitemaps)


def _fetch_sitemap_urls(sitemap_url):
    """Fetch sitemap and return list of sitemap URLs (handles sitemap index)."""
    try:
        import httpx
    except ImportError:
        print_error("httpx not installed. Run: uv sync")
        return []

    try:
        resp = httpx.get(sitemap_url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        print_error(f"Failed to fetch {sitemap_url}: {e}")
        return []

    sitemaps = [sitemap_url]
    try:
        root = ET.fromstring(resp.text)
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for loc in root.findall(".//sm:sitemap/sm:loc", ns):
            if loc.text and loc.text not in sitemaps:
                sitemaps.append(loc.text)
    except ET.ParseError:
        pass

    return sitemaps


def _submit_to_gsc(site_url, sitemaps):
    """Submit each sitemap URL to Google Search Console."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        print_error("google-api-python-client not installed. Run: uv sync")
        return 1

    creds = get_credentials()
    if not creds:
        return 1

    try:
        service = build("searchconsole", "v1", credentials=creds)
    except Exception as e:
        print_error(f"Failed to build Search Console client: {e}")
        return 1

    ok = 0
    fail = 0
    for url in sitemaps:
        try:
            service.sitemaps().submit(siteUrl=site_url, feedpath=url).execute()
            print_success(f"Submitted: {url}")
            ok += 1
        except Exception as e:
            print_error(f"Failed:    {url} — {e}")
            fail += 1

    print()
    if fail == 0:
        print_success(f"All {ok} sitemap(s) submitted to Google Search Console")
        return 0
    else:
        print_error(f"{ok} succeeded, {fail} failed")
        return 1

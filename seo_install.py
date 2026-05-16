"""Install Google Analytics on a domain: create GA4 property + data stream, write snippet."""

from seo_common import (
    get_credentials, print_header, print_success, print_error, print_info
)


GA_ADMIN_BASE = "https://analyticsadmin.googleapis.com/v1beta"


def _request(creds, method, url, body=None):
    import httpx
    from google.auth.transport.requests import Request as GRequest

    if not creds.valid:
        creds.refresh(GRequest())

    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    import json
    r = httpx.request(method, url, headers=headers, content=json.dumps(body) if body else None)
    r.raise_for_status()
    return r.json()


def _get_or_create_property(creds, account_id, domain):
    """Return existing GA4 property resource name for domain, or create one."""
    # List existing properties under account
    url = f"{GA_ADMIN_BASE}/properties?filter=parent:accounts/{account_id}&pageSize=200"
    data = _request(creds, "GET", url)
    for prop in data.get("properties", []):
        if domain in prop.get("displayName", "") or domain in prop.get("industryCategory", ""):
            print_info(f"Found existing property: {prop['name']} ({prop['displayName']})")
            return prop["name"]

    # Create new property
    print_info(f"Creating new GA4 property for {domain}...")
    body = {
        "displayName": domain,
        "timeZone": "America/Los_Angeles",
        "currencyCode": "USD",
        "parent": f"accounts/{account_id}",
    }
    prop = _request(creds, "POST", f"{GA_ADMIN_BASE}/properties", body)
    print_success(f"Created property: {prop['name']}")
    return prop["name"]


def _get_or_create_stream(creds, property_name, domain):
    """Return measurement ID for domain stream, creating it if needed."""
    # List existing data streams
    url = f"{GA_ADMIN_BASE}/{property_name}/dataStreams"
    data = _request(creds, "GET", url)
    for stream in data.get("dataStreams", []):
        web = stream.get("webStreamData", {})
        if domain in web.get("defaultUri", ""):
            mid = web.get("measurementId", "")
            print_info(f"Found existing stream: {stream['name']} ({mid})")
            return mid

    # Create new web data stream
    print_info(f"Creating web data stream for https://{domain}...")
    body = {
        "type": "WEB_DATA_STREAM",
        "displayName": domain,
        "webStreamData": {"defaultUri": f"https://{domain}"},
    }
    stream = _request(creds, "POST", url, body)
    mid = stream.get("webStreamData", {}).get("measurementId", "")
    print_success(f"Created stream, measurement ID: {mid}")
    return mid


def _write_snippet(domain, measurement_id, output_dir):
    from pathlib import Path
    out = Path(output_dir) / f"{domain}.ga.html"
    snippet = f"""<!-- Google Analytics: {domain} -->
<script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{measurement_id}');
</script>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(snippet)
    return out


def cmd_install(args):
    """Create GA4 property + stream for a domain and write the gtag snippet."""
    creds = get_credentials()
    if not creds:
        return 1

    domain = args.domain
    account_id = args.account

    if not account_id:
        # Try to list accounts so user can pick
        try:
            data = _request(creds, "GET", f"{GA_ADMIN_BASE}/accounts")
            accounts = data.get("accounts", [])
            if not accounts:
                print_error("No GA accounts found. Create one at analytics.google.com first.")
                return 1
            if len(accounts) == 1:
                account_id = accounts[0]["name"].split("/")[-1]
                print_info(f"Using account: {accounts[0]['displayName']} ({account_id})")
            else:
                print_info("Multiple GA accounts found. Use --account ID to specify one:")
                for a in accounts:
                    aid = a["name"].split("/")[-1]
                    print(f"  {aid}  {a['displayName']}")
                return 1
        except Exception as e:
            print_error(f"Could not list accounts: {e}")
            print_info("Run with --account <ID> (find it at analytics.google.com → Admin → Account Settings)")
            return 1

    print_header(f"GA Install: {domain}")

    try:
        property_name = _get_or_create_property(creds, account_id, domain)
        measurement_id = _get_or_create_stream(creds, property_name, domain)

        if not measurement_id:
            print_error("Could not get measurement ID.")
            return 1

        # Write snippet file
        out = _write_snippet(domain, measurement_id, args.output)
        print_success(f"Measurement ID: {measurement_id}")
        print_success(f"Snippet written: {out}")
        print()
        print(f"  <!-- paste into <head> of {domain} -->")
        print(open(out).read())
        return 0

    except Exception as e:
        print_error(f"Failed: {e}")
        return 1

"""Fetch GA4 (Google Analytics Data API) reports for the configured site."""

import json

from seo_common import print_info, print_error

GA_ADMIN_BASE = "https://analyticsadmin.googleapis.com/v1beta"
GA_DATA_BASE = "https://analyticsdata.googleapis.com/v1beta"


def _request(creds, method, url, body=None):
    import httpx
    from google.auth.transport.requests import Request as GRequest

    if not creds.valid:
        creds.refresh(GRequest())

    headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}
    r = httpx.request(method, url, headers=headers, content=json.dumps(body) if body else None)
    r.raise_for_status()
    return r.json()


def resolve_property(creds, domain):
    """Find the GA4 property whose web data stream serves `domain`.

    Returns a resource name like 'properties/514231035', or None.
    """
    data = _request(creds, "GET", f"{GA_ADMIN_BASE}/accountSummaries?pageSize=200")
    candidates = []
    for account in data.get("accountSummaries", []):
        for prop in account.get("propertySummaries", []):
            candidates.append(prop)

    # Fast path: displayName mentions the domain
    ordered = sorted(candidates, key=lambda p: domain not in p.get("displayName", ""))
    for prop in ordered:
        try:
            streams = _request(creds, "GET", f"{GA_ADMIN_BASE}/{prop['property']}/dataStreams")
        except Exception:
            continue
        for stream in streams.get("dataStreams", []):
            uri = stream.get("webStreamData", {}).get("defaultUri", "")
            if domain in uri:
                return prop["property"]
    return None


def run_report(creds, property_name, body):
    return _request(creds, "POST", f"{GA_DATA_BASE}/{property_name}:runReport", body)


def fetch_ga4(creds, domain, days, output_dir):
    """Fetch GA4 reports and save them to <output_dir>/ga4.json.

    Returns the property resource name, or None if unavailable.
    """
    try:
        property_name = resolve_property(creds, domain)
    except Exception as e:
        print_error(f"GA4 property lookup failed: {e}")
        return None
    if not property_name:
        print_info(f"No GA4 property found for {domain}, skipping GA4 fetch")
        return None

    date_ranges = [{"startDate": f"{days}daysAgo", "endDate": "today"}]
    reports = {
        "totals": {
            "dateRanges": date_ranges,
            "metrics": [{"name": m} for m in [
                "activeUsers", "newUsers", "sessions", "screenPageViews",
                "averageSessionDuration", "bounceRate", "engagementRate"]],
        },
        "daily": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "date"}],
            "metrics": [{"name": "activeUsers"}, {"name": "sessions"}, {"name": "screenPageViews"}],
            "orderBys": [{"dimension": {"dimensionName": "date"}}],
        },
        "pages": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "pagePath"}],
            "metrics": [{"name": "screenPageViews"}, {"name": "activeUsers"}],
            "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
            "limit": 20,
        },
        "channels": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "sessionDefaultChannelGroup"}],
            "metrics": [{"name": "sessions"}, {"name": "activeUsers"}],
            "orderBys": [{"metric": {"metricName": "sessions"}, "desc": True}],
        },
        "countries": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "country"}],
            "metrics": [{"name": "activeUsers"}, {"name": "sessions"}],
            "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}],
            "limit": 10,
        },
        "devices": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "deviceCategory"}],
            "metrics": [{"name": "activeUsers"}, {"name": "sessions"}],
            "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}],
        },
    }

    out = {"property": property_name}
    for name, body in reports.items():
        try:
            out[name] = run_report(creds, property_name, body)
        except Exception as e:
            print_error(f"GA4 report '{name}' failed: {e}")
            out[name] = {}

    path = output_dir / "ga4.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    return property_name


def rows(report):
    """Flatten a runReport response into (dimension_values, metric_values) tuples."""
    return [
        ([d["value"] for d in r.get("dimensionValues", [])],
         [m["value"] for m in r.get("metricValues", [])])
        for r in report.get("rows", [])
    ]

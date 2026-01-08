"""Fetch raw GSC data to disk."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from seo_common import (
    SITE_URL, REPORTS_DIR, SCRIPT_DIR,
    check_dependencies, get_credentials,
    print_header, print_success, print_error, print_info, print_progress
)


def cmd_fetch(args):
    """Fetch raw GSC data and save to disk."""
    if not check_dependencies():
        return 1

    import pandas as pd
    from googleapiclient.discovery import build

    print_header("SEO Fetch")

    creds = get_credentials()
    if not creds:
        return 1

    service = build("searchconsole", "v1", credentials=creds)

    end_date = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=args.days + 3)).strftime("%Y-%m-%d")

    # Create timestamped output directory
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = Path(args.output) / ts
    output_dir.mkdir(parents=True, exist_ok=True)

    print_info(f"Period: {start_date} to {end_date}")
    print_info(f"Output: {output_dir}")
    print()

    # Fetch analytics data
    data = {}
    for name, dims in [("queries", ["query"]), ("pages", ["page"]),
                       ("countries", ["country"]), ("devices", ["device"]), ("dates", ["date"])]:
        print(f"  Fetching {name}...", end=" ", flush=True)
        try:
            rows = fetch_gsc_data(service, start_date, end_date, dims)
            data[name] = rows
            print(f"({len(rows)} rows)")
        except Exception as e:
            print(f"error: {e}")
            data[name] = []

    # Fetch sitemaps status
    print(f"  Fetching sitemaps...", end=" ", flush=True)
    sitemaps_data = fetch_sitemaps(service)
    print(f"({len(sitemaps_data)} sitemaps)")

    # Inspect URLs for indexing status
    inspection_results = []
    gsc_dir = output_dir / "gsc"
    gsc_dir.mkdir(exist_ok=True)

    if data.get("pages"):
        all_pages = [p["page"] for p in data["pages"]]

        # Default 60 URLs, --full for all
        if args.full:
            pages_to_inspect = all_pages
            print(f"  Inspecting URLs (--full mode: {len(all_pages)} URLs)...")
        else:
            pages_to_inspect = all_pages[:60]
            print(f"  Inspecting URLs ({len(pages_to_inspect)} URLs, use --full for all)...")

        total = len(pages_to_inspect)

        for i, url in enumerate(pages_to_inspect, 1):
            result, raw_response = inspect_url(service, url)
            inspection_results.append(result)

            # Save raw API response to JSON file
            if raw_response:
                url_hash = url.replace("https://", "").replace("http://", "").replace("/", "_")[:100]
                raw_file = gsc_dir / f"inspect_{url_hash}.json"
                with open(raw_file, "w") as f:
                    json.dump(raw_response, f, indent=2)

            # Progress every 10 URLs or at the end
            if i % 10 == 0 or i == total:
                print_progress(i, total, "Inspecting: ")

            # Rate limit: 0.3s for default, 1.1s for --full (60 req/min limit)
            time.sleep(1.1 if args.full else 0.3)

        print()  # New line after progress
    else:
        print(f"  Inspecting URLs... (no pages data)")

    # Save all data to CSV files
    print()
    print_header("Saving Data")

    for name, rows in data.items():
        if rows:
            path = output_dir / f"{name}.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            print(f"  {path.name}: {len(rows)} rows")

    if sitemaps_data:
        path = output_dir / "sitemaps.csv"
        pd.DataFrame(sitemaps_data).to_csv(path, index=False)
        print(f"  {path.name}: {len(sitemaps_data)} rows")

    if inspection_results:
        path = output_dir / "inspections.csv"
        pd.DataFrame(inspection_results).to_csv(path, index=False)
        print(f"  {path.name}: {len(inspection_results)} rows")

    # Save metadata
    metadata = {
        "timestamp": ts,
        "start_date": start_date,
        "end_date": end_date,
        "days": args.days,
        "full": args.full,
        "site_url": SITE_URL,
        "pages_inspected": len(inspection_results),
        "total_pages": len(data.get("pages", [])),
    }
    with open(output_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print()
    print_success(f"Data saved to: {output_dir}")
    print_info(f"Run 'seo render' to generate reports")
    return 0


def fetch_gsc_data(service, start_date, end_date, dimensions):
    """Fetch GSC data with pagination."""
    all_rows = []
    start_row = 0
    while True:
        resp = service.searchanalytics().query(
            siteUrl=SITE_URL,
            body={"startDate": start_date, "endDate": end_date,
                  "dimensions": dimensions, "rowLimit": 25000, "startRow": start_row}
        ).execute()
        rows = resp.get("rows", [])
        if not rows:
            break
        for row in rows:
            entry = {"clicks": row["clicks"], "impressions": row["impressions"],
                     "ctr": row["ctr"], "position": row["position"]}
            for i, dim in enumerate(dimensions):
                entry[dim] = row["keys"][i]
            all_rows.append(entry)
        if len(rows) < 25000:
            break
        start_row += 25000
    return all_rows


def fetch_sitemaps(service):
    """Fetch sitemap status."""
    sitemaps_data = []
    try:
        resp = service.sitemaps().list(siteUrl=SITE_URL).execute()
        for sm in resp.get("sitemap", []):
            contents = sm.get("contents", [{}])
            first_content = contents[0] if contents else {}
            sitemaps_data.append({
                "path": sm.get("path", ""),
                "type": sm.get("type", ""),
                "submitted": sm.get("lastSubmitted", ""),
                "downloaded": sm.get("lastDownloaded", ""),
                "warnings": int(sm.get("warnings") or 0),
                "errors": int(sm.get("errors") or 0),
                "submitted_count": int(first_content.get("submitted") or 0),
                "indexed_count": int(first_content.get("indexed") or 0),
            })
    except Exception as e:
        print_error(f"Failed to fetch sitemaps: {e}")
    return sitemaps_data


def inspect_url(service, url):
    """Inspect a single URL for indexing status. Returns (result, raw_response)."""
    result = {"url": url, "verdict": "ERROR", "coverage": "", "indexing_state": "", "last_crawl": ""}
    raw_response = None
    try:
        resp = service.urlInspection().index().inspect(
            body={"inspectionUrl": url, "siteUrl": SITE_URL}
        ).execute()

        raw_response = resp  # Save raw API response

        inspection = resp.get("inspectionResult", {})
        index_status = inspection.get("indexStatusResult", {})

        result["verdict"] = index_status.get("verdict", "UNKNOWN")
        result["coverage"] = index_status.get("coverageState", "")
        result["indexing_state"] = index_status.get("indexingState", "")
        result["last_crawl"] = index_status.get("lastCrawlTime", "")
        result["robots_txt"] = index_status.get("robotsTxtState", "")
        result["crawl_allowed"] = index_status.get("pageFetchState", "")
    except Exception as e:
        result["error"] = str(e)[:50]
    return result, raw_response

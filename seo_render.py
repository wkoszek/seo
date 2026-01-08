"""Render SEO reports from fetched data."""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from seo_common import (
    REPORTS_DIR,
    print_header, print_success, print_error, print_info
)


def cmd_render(args):
    """Render reports from fetched GSC data."""
    # Find the data directory
    data_dir = find_data_dir(args.data)
    if not data_dir:
        return 1

    print_header("SEO Render")
    print_info(f"Data: {data_dir}")
    print()

    # Load metadata
    metadata = {}
    metadata_file = data_dir / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            metadata = json.load(f)

    # Load CSV data
    data = {}
    for name in ["queries", "pages", "countries", "devices", "dates", "sitemaps", "inspections"]:
        csv_file = data_dir / f"{name}.csv"
        if csv_file.exists():
            data[name] = pd.read_csv(csv_file).to_dict("records")
        else:
            data[name] = []

    # Load JSON inspection data for detailed analysis
    inspections_detailed = load_inspection_jsons(data_dir / "gsc")

    # Generate console report
    if inspections_detailed:
        generate_console_report(inspections_detailed, data, metadata, args.verbose)
    else:
        print_info("No detailed inspection data (gsc/*.json) found")
        print_info("Console report requires --full fetch for detailed analysis")
        print()

    # Generate HTML report
    html_path = data_dir / "report.html"
    generate_html_report(html_path, data, metadata)
    print()
    print_success(f"HTML report: {html_path}")

    return 0


def find_data_dir(data_arg):
    """Find the data directory to use."""
    if data_arg:
        # Specific directory provided
        data_dir = Path(data_arg)
        if not data_dir.exists():
            print_error(f"Directory not found: {data_dir}")
            return None
        return data_dir

    # Find latest directory in reports/seo/
    reports_dir = REPORTS_DIR
    if not reports_dir.exists():
        print_error(f"No reports directory: {reports_dir}")
        print_info("Run 'seo fetch' first to get data from Google.")
        return None

    # Get all timestamped directories
    dirs = [d for d in reports_dir.iterdir() if d.is_dir() and d.name[0].isdigit()]
    if not dirs:
        print_error(f"No fetch data found in {reports_dir}")
        print_info("Run 'seo fetch' first to get data from Google.")
        return None

    # Return most recent
    return sorted(dirs, key=lambda d: d.name)[-1]


def load_inspection_jsons(gsc_dir):
    """Load detailed inspection data from JSON files."""
    if not gsc_dir or not gsc_dir.exists():
        return []

    inspections = []
    for f in gsc_dir.glob("inspect_*.json"):
        try:
            with open(f) as fp:
                data = json.load(fp)
                result = data.get("inspectionResult", {})
                index_status = result.get("indexStatusResult", {})
                rich_results = result.get("richResultsResult", {})

                url = index_status.get("googleCanonical", "")
                if not url:
                    url = f.stem.replace("inspect_", "").replace("_", "/")

                inspections.append({
                    "url": url,
                    "verdict": index_status.get("verdict", "UNKNOWN"),
                    "coverage": index_status.get("coverageState", ""),
                    "fetch": index_status.get("pageFetchState", "UNKNOWN"),
                    "indexing": index_status.get("indexingState", "UNKNOWN"),
                    "robots_txt": index_status.get("robotsTxtState", "UNKNOWN"),
                    "last_crawl": index_status.get("lastCrawlTime", ""),
                    "crawled_as": index_status.get("crawledAs", "UNKNOWN"),
                    "google_canonical": index_status.get("googleCanonical", ""),
                    "user_canonical": index_status.get("userCanonical", ""),
                    "referring_urls": index_status.get("referringUrls", []),
                    "rich_verdict": rich_results.get("verdict", "NONE"),
                    "rich_items": [item.get("richResultType", "") for item in rich_results.get("detectedItems", [])],
                })
        except Exception as e:
            print_error(f"Failed to parse {f.name}: {e}")

    return inspections


def generate_console_report(inspections, data, metadata, verbose=False):
    """Generate detailed console report."""
    total = len(inspections)
    now = datetime.now()

    stats = calculate_stats(inspections)

    # Header
    print()
    print("=" * 70)
    print("URL INSPECTION REPORT")
    print("=" * 70)
    start = metadata.get("start_date", "")
    end = metadata.get("end_date", "")
    print(f"Period: {start} to {end}  |  URLs: {total}")
    print()

    # Traffic summary from CSV data
    if data.get("dates"):
        total_clicks = sum(d.get("clicks", 0) for d in data["dates"])
        total_impressions = sum(d.get("impressions", 0) for d in data["dates"])
        avg_ctr = sum(d.get("ctr", 0) for d in data["dates"]) / len(data["dates"]) if data["dates"] else 0
        avg_pos = sum(d.get("position", 0) for d in data["dates"]) / len(data["dates"]) if data["dates"] else 0
        print(f"TRAFFIC: {total_clicks:,} clicks | {total_impressions:,} impressions | {avg_ctr*100:.1f}% CTR | {avg_pos:.1f} position")
        print()

    # HEALTH line
    pass_pct = stats["verdicts"]["PASS"] / total * 100 if total else 0
    missing_rich_pct = stats["rich"]["none"] / total * 100 if total else 0
    desktop_pct = stats["crawled_as"]["DESKTOP"] / total * 100 if total else 0
    non_www_pct = stats["www"]["non_www"] / total * 100 if total else 0
    orphan_count = stats["internal_links"].get(0, 0) + stats["internal_links"].get(1, 0)

    print("HEALTH:")
    health_parts = []
    health_parts.append(f"{pass_pct:.0f}% indexed")
    if missing_rich_pct > 0:
        health_parts.append(f"{missing_rich_pct:.0f}% missing rich results")
    if desktop_pct > 0:
        health_parts.append(f"{desktop_pct:.0f}% desktop-only")
    if non_www_pct > 0:
        health_parts.append(f"{non_www_pct:.0f}% non-www")
    if orphan_count > 0:
        health_parts.append(f"{orphan_count} orphan pages")
    print(f"  {' | '.join(health_parts)}")
    print()

    # VERDICTS
    print("-" * 70)
    print("VERDICTS - Is this URL in Google's index?")
    print("-" * 70)
    print(f"  PASS:      {stats['verdicts']['PASS']:>4}   URL is indexed and appearing in search results")
    print(f"  NEUTRAL:   {stats['verdicts']['NEUTRAL']:>4}   URL is valid but not indexed (redirect, canonical elsewhere)")
    print(f"  FAIL:      {stats['verdicts']['FAIL']:>4}   URL has issues preventing indexing")
    print(f"  PARTIAL:   {stats['verdicts']['PARTIAL']:>4}   URL is indexed but has some issues")
    print()

    # FETCH
    print("-" * 70)
    print("FETCH - Could Google successfully download the page?")
    print("-" * 70)
    print(f"  OK:         {stats['fetch']['SUCCESSFUL']:>4}   Page downloaded successfully")
    print(f"  SOFT_404:   {stats['fetch']['SOFT_404']:>4}   Page exists but looks like an error page to Google")
    print(f"  NOT_FOUND:  {stats['fetch']['NOT_FOUND']:>4}   Page returned 404")
    print(f"  ERROR:      {stats['fetch']['ERROR']:>4}   Server error, timeout, or blocked")
    print()

    # CANONICAL
    print("-" * 70)
    print("CANONICAL - Does Google's chosen canonical match yours?")
    print("-" * 70)
    print(f"  match:     {stats['canonical']['match']:>4}   Google uses your specified canonical URL")
    print(f"  mismatch:  {stats['canonical']['mismatch']:>4}   Google chose a different canonical (duplicate content issue)")
    print()

    # MOBILE/DESKTOP
    print("-" * 70)
    print("CRAWL AGENT - How does Google crawl your pages?")
    print("-" * 70)
    print(f"  MOBILE:    {stats['crawled_as']['MOBILE']:>4}   Crawled with mobile user-agent (good)")
    print(f"  DESKTOP:   {stats['crawled_as']['DESKTOP']:>4}   Crawled with desktop user-agent only")
    print()

    # WWW vs non-WWW
    if stats['www']['non_www'] > 0 or stats['www']['www'] > 0:
        print("-" * 70)
        print("WWW CONSISTENCY")
        print("-" * 70)
        print(f"  www:       {stats['www']['www']:>4}   URLs with www. prefix")
        print(f"  non-www:   {stats['www']['non_www']:>4}   URLs without www. prefix")
        print()

    # RICH RESULTS
    print("-" * 70)
    print("RICH RESULTS - Structured data detected by Google")
    print("-" * 70)
    print(f"  with data: {total - stats['rich']['none']:>4}   Has structured data")
    print(f"  none:      {stats['rich']['none']:>4}   No structured data detected")
    print()

    # INTERNAL LINKS
    print("-" * 70)
    print("INTERNAL LINKS - Pages with 0-1 links are 'orphans'")
    print("-" * 70)
    for count in sorted(stats['internal_links'].keys()):
        num_pages = stats['internal_links'][count]
        label = "orphan!" if count <= 1 else ""
        bar = "#" * min(num_pages // 10, 40)
        print(f"  {count:>2} links: {num_pages:>4} pages  {bar} {label}")
    print()

    # CRAWL AGE
    print("-" * 70)
    print("CRAWL AGE - How recently did Google crawl these pages?")
    print("-" * 70)
    print(f"  <7 days:   {stats['crawl_age']['<7d']:>4}   Crawled within last week")
    print(f"  7-30 days: {stats['crawl_age']['7-30d']:>4}   Crawled 1-4 weeks ago")
    print(f"  >30 days:  {stats['crawl_age']['>30d']:>4}   Not crawled in over a month")
    print()

    # BY LANGUAGE
    if stats['languages']:
        print("-" * 70)
        print("BY LANGUAGE")
        print("-" * 70)
        for lang, lang_data in sorted(stats['languages'].items()):
            lang_total = lang_data['total']
            lang_pass = lang_data['PASS']
            lang_pct = lang_pass / lang_total * 100 if lang_total else 0
            flag = "!" if lang_pct < 90 else ""
            print(f"  /{lang}/:  {lang_total:>3} pages,  {lang_pass:>3} PASS ({lang_pct:>5.1f}%) {flag}")
        print()

    # ISSUES
    issues = [i for i in inspections if i['verdict'] != 'PASS' or
              i['fetch'] not in ('SUCCESSFUL', 'UNKNOWN') or
              i['google_canonical'] != i['user_canonical']]

    if issues:
        print("=" * 70)
        print(f"ISSUES ({len(issues)})")
        print("=" * 70)
        print_url_table(issues[:30])
        if len(issues) > 30:
            print(f"  ... and {len(issues) - 30} more")
        print()

    # ORPHAN PAGES
    orphans = [i for i in inspections if len(i['referring_urls']) <= 1]
    if orphans:
        print("=" * 70)
        print(f"ORPHAN PAGES ({len(orphans)}) - 0-1 internal links")
        print("=" * 70)
        for o in orphans[:15]:
            path = extract_path(o['url'])
            links = len(o['referring_urls'])
            print(f"  [{links} links] {path}")
        if len(orphans) > 15:
            print(f"  ... and {len(orphans) - 15} more")
        print()

    if verbose:
        print("=" * 70)
        print(f"ALL URLS ({total})")
        print("=" * 70)
        print_url_table(inspections)
        print()


def calculate_stats(inspections):
    """Calculate statistics from inspections."""
    stats = {
        "verdicts": defaultdict(int),
        "fetch": defaultdict(int),
        "canonical": {"match": 0, "mismatch": 0},
        "crawled_as": defaultdict(int),
        "www": {"www": 0, "non_www": 0},
        "rich": {"none": 0},
        "internal_links": defaultdict(int),
        "crawl_age": {"<7d": 0, "7-30d": 0, ">30d": 0},
        "languages": defaultdict(lambda: {"total": 0, "PASS": 0}),
    }

    now = datetime.now()

    for i in inspections:
        verdict = i["verdict"]
        if verdict not in ("PASS", "NEUTRAL", "FAIL", "PARTIAL"):
            verdict = "UNKNOWN"
        stats["verdicts"][verdict] += 1

        fetch = i["fetch"]
        if fetch == "SUCCESSFUL":
            stats["fetch"]["SUCCESSFUL"] += 1
        elif fetch == "SOFT_404":
            stats["fetch"]["SOFT_404"] += 1
        elif fetch == "NOT_FOUND":
            stats["fetch"]["NOT_FOUND"] += 1
        else:
            stats["fetch"]["ERROR"] += 1

        if i["google_canonical"] == i["user_canonical"]:
            stats["canonical"]["match"] += 1
        else:
            stats["canonical"]["mismatch"] += 1

        stats["crawled_as"][i["crawled_as"]] += 1

        url = i["url"]
        if "://www." in url:
            stats["www"]["www"] += 1
        elif "://" in url:
            stats["www"]["non_www"] += 1

        if not i["rich_items"]:
            stats["rich"]["none"] += 1

        num_links = len(i["referring_urls"])
        stats["internal_links"][num_links] += 1

        if i["last_crawl"]:
            try:
                crawl_time = datetime.fromisoformat(i["last_crawl"].replace("Z", "+00:00"))
                days_ago = (now - crawl_time.replace(tzinfo=None)).days
                if days_ago < 7:
                    stats["crawl_age"]["<7d"] += 1
                elif days_ago <= 30:
                    stats["crawl_age"]["7-30d"] += 1
                else:
                    stats["crawl_age"][">30d"] += 1
            except:
                pass

        lang = extract_language(url)
        if lang:
            stats["languages"][lang]["total"] += 1
            if i["verdict"] == "PASS":
                stats["languages"][lang]["PASS"] += 1

    for v in ("PASS", "NEUTRAL", "FAIL", "PARTIAL"):
        if v not in stats["verdicts"]:
            stats["verdicts"][v] = 0

    return stats


def extract_path(url):
    """Extract path from URL."""
    if "://" in url:
        path = "/" + url.split("://", 1)[1].split("/", 1)[-1]
    else:
        path = url
    return path if len(path) <= 60 else path[:57] + "..."


def extract_language(url):
    """Extract language code from URL path."""
    match = re.search(r"/([a-z]{2})/", url)
    return match.group(1) if match else None


def print_url_table(inspections):
    """Print URLs in table format."""
    headers = ["VERDICT", "FETCH", "CANON", "PATH"]
    rows = []

    for i in inspections:
        verdict = i["verdict"][:7]
        fetch = "OK" if i["fetch"] == "SUCCESSFUL" else i["fetch"][:8]
        canon = "ok" if i["google_canonical"] == i["user_canonical"] else "BAD"
        path = extract_path(i["url"])
        rows.append([verdict, fetch, canon, path])

    widths = [max(len(h), max(len(r[j]) for r in rows)) for j, h in enumerate(headers)]
    widths[-1] = min(widths[-1], 50)

    header_line = "  ".join(h.ljust(widths[j]) for j, h in enumerate(headers))
    print(f"  {header_line}")
    separator = "  ".join("-" * widths[j] for j in range(len(headers)))
    print(f"  {separator}")

    for row in rows:
        row[-1] = row[-1][:50]
        line = "  ".join(str(v).ljust(widths[j]) for j, v in enumerate(row))
        print(f"  {line}")


def generate_html_report(path, data, metadata):
    """Generate HTML report from data."""

    def table(rows, cols):
        if not rows:
            return "<p>No data</p>"
        h = "<table><thead><tr>" + "".join(f"<th>{c[1]}</th>" for c in cols) + "</tr></thead><tbody>"
        for row in rows:
            h += "<tr>" + "".join(f"<td class='{c[2]}'>{fmt(row.get(c[0]), c[0])}</td>" for c in cols) + "</tr>"
        return h + "</tbody></table>"

    def fmt(v, k):
        if k == "ctr":
            return f"{v*100:.2f}%" if v else ""
        if k == "position":
            return f"{v:.1f}" if v else ""
        if isinstance(v, (int, float)) and k in ("clicks", "impressions", "submitted_count", "indexed_count"):
            return f"{int(v):,}"
        return v if v else ""

    # Calculate summary stats
    total_clicks = sum(d.get("clicks", 0) for d in data.get("dates", []))
    total_impressions = sum(d.get("impressions", 0) for d in data.get("dates", []))
    dates = data.get("dates", [])
    avg_ctr = sum(d.get("ctr", 0) for d in dates) / len(dates) if dates else 0
    avg_position = sum(d.get("position", 0) for d in dates) / len(dates) if dates else 0
    total_pages = len(data.get("pages", []))
    total_queries = len(data.get("queries", []))

    start_date = metadata.get("start_date", "")
    end_date = metadata.get("end_date", "")

    # Sitemaps section
    sitemaps_html = ""
    if data.get("sitemaps"):
        sitemaps_html = "<h2>Sitemap Status</h2>" + table(data["sitemaps"], [
            ("path", "Sitemap", "trunc"),
            ("submitted_count", "Submitted", "num"),
            ("indexed_count", "Indexed", "num"),
            ("errors", "Errors", "num"),
        ])

    # Indexing health section
    health_html = ""
    inspections = data.get("inspections", [])
    if inspections:
        verdicts = {}
        for insp in inspections:
            v = insp.get("verdict", "UNKNOWN")
            verdicts[v] = verdicts.get(v, 0) + 1
        total = len(inspections)
        pass_count = verdicts.get("PASS", 0)
        pass_pct = (pass_count / total * 100) if total else 0

        health_html = f"""<h2>Indexing Health</h2>
<div class="health-summary">
<div class="health-bar-container">
<div class="health-bar" style="width: {pass_pct:.0f}%"></div>
</div>
<div class="health-stats">
<span class="health-pct">{pass_pct:.0f}% indexed</span>
<span class="health-detail">({pass_count:,} of {total:,} URLs inspected)</span>
</div>
</div>
<div class="verdict-grid">"""
        for verdict in ["PASS", "NEUTRAL", "FAIL", "PARTIAL", "ERROR"]:
            count = verdicts.get(verdict, 0)
            if count > 0:
                pct = count / total * 100
                cls = "pass" if verdict == "PASS" else "neutral" if verdict == "NEUTRAL" else "fail"
                health_html += f'<div class="verdict-item {cls}"><div class="verdict-count">{count:,}</div><div class="verdict-label">{verdict}</div><div class="verdict-pct">{pct:.1f}%</div></div>'
        health_html += "</div>"

    # Indexing issues section
    issues_html = ""
    indexing_issues = [i for i in inspections if i.get("verdict") != "PASS"]
    if indexing_issues:
        issues_html = "<h2>Indexing Issues</h2><div class='issues'>"
        for issue in indexing_issues[:20]:
            vc = "error" if issue.get("verdict") != "PASS" else ""
            issues_html += f'<div class="issue"><span class="verdict {vc}">{issue.get("verdict", "")}</span>'
            issues_html += f'<span class="issue-url">{issue.get("url", "")}</span>'
            issues_html += f'<span class="issue-reason">{issue.get("coverage", "")}</span></div>'
        issues_html += "</div>"

    # Traffic by device section
    devices_html = ""
    devices = data.get("devices", [])
    if devices:
        total_dev_clicks = sum(d.get("clicks", 0) for d in devices)
        devices_html = "<h2>Traffic by Device</h2><div class='device-bars'>"
        for d in sorted(devices, key=lambda x: x.get("clicks", 0), reverse=True):
            clicks = d.get("clicks", 0)
            pct = (clicks / total_dev_clicks * 100) if total_dev_clicks else 0
            device = d.get("device", "Unknown").title()
            devices_html += f'<div class="device-row"><span class="device-name">{device}</span><div class="device-bar-bg"><div class="device-bar" style="width:{pct:.0f}%"></div></div><span class="device-value">{clicks:,} ({pct:.0f}%)</span></div>'
        devices_html += "</div>"

    # Traffic by country section
    countries_html = ""
    countries = data.get("countries", [])
    if countries:
        top_countries = sorted(countries, key=lambda x: x.get("clicks", 0), reverse=True)[:10]
        countries_html = "<h2>Top Countries</h2>" + table(top_countries, [
            ("country", "Country", ""),
            ("clicks", "Clicks", "num"),
            ("impressions", "Impressions", "num"),
            ("ctr", "CTR", "num"),
            ("position", "Position", "num"),
        ])

    # Daily trend chart
    trend_html = ""
    sorted_dates = sorted(data.get("dates", []), key=lambda x: x.get("date", ""))
    if sorted_dates:
        max_clicks = max(d.get("clicks", 1) for d in sorted_dates) or 1
        trend_html = "<h2>Daily Traffic Trend</h2><div class='trend-chart'>"
        for d in sorted_dates:
            clicks = d.get("clicks", 0)
            height = (clicks / max_clicks * 100)
            date_str = d.get("date", "")[-5:]
            trend_html += f'<div class="trend-bar-wrapper"><div class="trend-bar" style="height:{height:.0f}%"></div><div class="trend-label">{date_str}</div><div class="trend-value">{clicks}</div></div>'
        trend_html += "</div>"

    # Top pages
    top_pages = sorted(data.get("pages", []), key=lambda x: x.get("clicks", 0), reverse=True)[:20]

    # Top queries
    top_queries = sorted(data.get("queries", []), key=lambda x: x.get("clicks", 0), reverse=True)[:30]

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>SEO Report</title>
<style>
body {{ font-family: system-ui; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
h1 {{ color: #333; }} h2 {{ margin-top: 30px; border-bottom: 2px solid #d6262d; padding-bottom: 10px; }}
.stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }}
@media (min-width: 768px) {{ .stats {{ grid-template-columns: repeat(6, 1fr); }} }}
.stat {{ background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.stat-value {{ font-size: 1.8em; font-weight: bold; color: #d6262d; }}
.stat-label {{ font-size: 0.85em; color: #666; margin-top: 5px; }}
table {{ width: 100%; background: white; border-collapse: collapse; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
th {{ background: #f8f9fa; padding: 12px; text-align: left; }}
td {{ padding: 10px; border-top: 1px solid #eee; }}
.num {{ text-align: right; }}
.trunc {{ max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.issues {{ background: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.issue {{ padding: 10px 0; border-bottom: 1px solid #eee; }}
.verdict {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; background: #28a745; color: white; }}
.verdict.error {{ background: #dc3545; }}
.issue-url {{ margin-left: 10px; font-size: 0.9em; word-break: break-all; }}
.issue-reason {{ display: block; margin-left: 60px; color: #666; font-size: 0.85em; }}
.health-summary {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 15px; }}
.health-bar-container {{ background: #eee; border-radius: 10px; height: 20px; overflow: hidden; }}
.health-bar {{ background: linear-gradient(90deg, #28a745, #5cb85c); height: 100%; }}
.health-stats {{ margin-top: 10px; }}
.health-pct {{ font-size: 1.5em; font-weight: bold; color: #28a745; }}
.health-detail {{ color: #666; margin-left: 10px; }}
.verdict-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; }}
.verdict-item {{ background: white; border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.verdict-item.pass {{ border-left: 4px solid #28a745; }}
.verdict-item.neutral {{ border-left: 4px solid #ffc107; }}
.verdict-item.fail {{ border-left: 4px solid #dc3545; }}
.verdict-count {{ font-size: 1.5em; font-weight: bold; }}
.verdict-label {{ font-size: 0.8em; color: #666; text-transform: uppercase; }}
.verdict-pct {{ font-size: 0.9em; color: #999; }}
.device-bars {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.device-row {{ display: flex; align-items: center; margin: 10px 0; }}
.device-name {{ width: 80px; font-weight: 500; }}
.device-bar-bg {{ flex: 1; background: #eee; border-radius: 4px; height: 24px; margin: 0 15px; overflow: hidden; }}
.device-bar {{ background: #d6262d; height: 100%; }}
.device-value {{ width: 120px; text-align: right; font-size: 0.9em; color: #666; }}
.trend-chart {{ display: flex; align-items: flex-end; gap: 2px; background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); height: 180px; overflow-x: auto; }}
.trend-bar-wrapper {{ display: flex; flex-direction: column; align-items: center; min-width: 30px; height: 100%; }}
.trend-bar {{ width: 100%; background: linear-gradient(180deg, #d6262d, #ff6b6b); border-radius: 2px 2px 0 0; margin-top: auto; min-height: 2px; }}
.trend-label {{ font-size: 0.7em; color: #999; margin-top: 5px; white-space: nowrap; }}
.trend-value {{ font-size: 0.7em; color: #666; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
</style></head><body>
<h1>SEO Report</h1>
<p>{start_date} to {end_date}</p>
<div class="stats">
<div class="stat"><div class="stat-value">{total_clicks:,}</div><div class="stat-label">Clicks</div></div>
<div class="stat"><div class="stat-value">{total_impressions:,}</div><div class="stat-label">Impressions</div></div>
<div class="stat"><div class="stat-value">{avg_ctr*100:.1f}%</div><div class="stat-label">CTR</div></div>
<div class="stat"><div class="stat-value">{avg_position:.1f}</div><div class="stat-label">Position</div></div>
<div class="stat"><div class="stat-value">{total_pages:,}</div><div class="stat-label">Pages</div></div>
<div class="stat"><div class="stat-value">{total_queries:,}</div><div class="stat-label">Queries</div></div>
</div>
{trend_html}
{health_html}
{sitemaps_html}
<div class="two-col">
<div>{devices_html}</div>
<div>{countries_html}</div>
</div>
{issues_html}
<h2>Top Pages</h2>
{table(top_pages, [('page','Page','trunc'),('clicks','Clicks','num'),('impressions','Impr','num'),('ctr','CTR','num'),('position','Pos','num')])}
<h2>Top Queries</h2>
{table(top_queries, [('query','Query',''),('clicks','Clicks','num'),('impressions','Impr','num'),('ctr','CTR','num'),('position','Pos','num')])}
</body></html>"""

    with open(path, "w") as f:
        f.write(html)

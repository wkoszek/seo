"""Suggest new content pages based on GSC data."""

import re
from pathlib import Path

import pandas as pd

from seo_common import REPORTS_DIR, print_header, print_info, print_error


LANGS = ["de", "es", "fr", "pl", "it", "pt"]


def cmd_suggest(args):
    """Suggest next pages to create based on search data."""
    data_dir = find_data_dir(args.data)
    if not data_dir:
        return 1

    print_header("SEO Content Suggestions")
    print_info(f"Data: {data_dir}")
    print()

    queries = load_csv(data_dir / "queries.csv")
    pages = load_csv(data_dir / "pages.csv")

    if queries is None or pages is None:
        return 1

    suggest_new_topics(queries, pages, min_impressions=args.min_impressions)
    suggest_translations(pages, min_impressions=args.min_impressions)

    return 0


def find_data_dir(data_arg):
    if data_arg:
        d = Path(data_arg)
        if not d.exists():
            print_error(f"Directory not found: {data_arg}")
            return None
        return d

    if not REPORTS_DIR.exists():
        print_error(f"No reports directory: {REPORTS_DIR}")
        print_info("Run 'seo fetch' first.")
        return None

    dirs = [d for d in REPORTS_DIR.iterdir() if d.is_dir() and d.name[0].isdigit()]
    if not dirs:
        print_error(f"No fetch data found in {REPORTS_DIR}")
        print_info("Run 'seo fetch' first.")
        return None

    return sorted(dirs, key=lambda d: d.name)[-1]


def load_csv(path):
    if not path.exists():
        print_error(f"Missing: {path.name}")
        return None
    return pd.read_csv(path)


def extract_lang(url):
    m = re.search(r"/([a-z]{2})/", url)
    return m.group(1) if m else ""


def extract_slug(url):
    parts = url.rstrip("/").split("/")
    return parts[-1].lower() if parts else ""


def suggest_new_topics(queries, pages, min_impressions=50):
    """Find search queries that suggest missing or weak content."""
    # Build set of words used in existing page slugs (EN)
    pages["lang"] = pages["page"].apply(extract_lang)
    pages["slug"] = pages["page"].apply(extract_slug)
    en_slugs = set(pages[pages["lang"] == "en"]["slug"])

    # Near-miss: high impressions, position 5-20, low CTR — we appear but don't rank well
    near_miss = queries[
        (queries["impressions"] >= min_impressions)
        & (queries["position"] >= 5)
        & (queries["position"] <= 25)
    ].copy()
    near_miss = near_miss.sort_values("impressions", ascending=False)

    # Filter to queries that don't closely match an existing EN slug
    def no_page_match(q):
        q_words = set(re.sub(r"[^a-z0-9 ]", "", q.lower()).split())
        for slug in en_slugs:
            slug_words = set(slug.replace("-", " ").split())
            if len(q_words & slug_words) >= max(1, len(q_words) // 2):
                return False
        return True

    gaps = near_miss[near_miss["query"].apply(no_page_match)]

    print("=" * 60)
    print("NEW CONTENT OPPORTUNITIES")
    print("Queries with traffic but no closely matching EN page")
    print("=" * 60)
    print(f"  {'IMPRESSIONS':>11}  {'CLICKS':>6}  {'POSITION':>8}  QUERY")
    print(f"  {'-'*11}  {'-'*6}  {'-'*8}  {'-'*40}")
    for _, row in gaps.head(25).iterrows():
        print(f"  {int(row['impressions']):>11,}  {int(row['clicks']):>6}  {row['position']:>8.1f}  {row['query']}")
    if len(gaps) > 25:
        print(f"  ... and {len(gaps) - 25} more")
    print()


def suggest_translations(pages, min_impressions=50):
    """Find EN pages with traffic that are missing translations."""
    pages["lang"] = pages["page"].apply(extract_lang)
    pages["slug"] = pages["page"].apply(extract_slug)

    # EN pages grouped by slug with total impressions
    en_pages = pages[pages["lang"] == "en"].groupby("slug")["impressions"].sum().reset_index()
    en_pages = en_pages[en_pages["impressions"] >= min_impressions].sort_values("impressions", ascending=False)

    print("=" * 60)
    print("TRANSLATION GAPS")
    print("EN pages with traffic missing in other languages")
    print("=" * 60)

    for lang in LANGS:
        lang_slugs = set(pages[pages["lang"] == lang]["slug"])
        missing = en_pages[~en_pages["slug"].isin(lang_slugs)]
        if missing.empty:
            continue
        total_impr = missing["impressions"].sum()
        print(f"\n  /{lang}/  — {len(missing)} missing  ({total_impr:,} impressions unreached)")
        print(f"  {'IMPRESSIONS':>11}  SLUG")
        print(f"  {'-'*11}  {'-'*45}")
        for _, row in missing.head(15).iterrows():
            print(f"  {int(row['impressions']):>11,}  {row['slug']}")
        if len(missing) > 15:
            print(f"  ... and {len(missing) - 15} more")
    print()

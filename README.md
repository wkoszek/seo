# 🔍 SEO Tool

Google Search Console integration and sitemap crawler. 🚀

## ✨ Features

- 📊 Fetch data from Google Search Console
- 🗺️ Crawl and validate sitemaps
- 📈 Generate SEO performance reports
- 🔔 Ping search engines with sitemap updates

## 🛠️ Setup

Requires [uv](https://docs.astral.sh/uv/) and [direnv](https://direnv.net/).

```bash
uv python install 3.12
uv sync --python 3.12
direnv allow
```

After setup, entering the directory will auto-activate the Python 3.12 venv.

## 🚀 Usage

```bash
./seo init      # Set up credentials (guided)
./seo auth      # Authenticate with Google
./seo status    # Check configuration
./seo fetch     # Fetch raw GSC data to disk
./seo render    # Render reports from fetched data
./seo ping      # Ping search engines with all sitemaps
```

The tool guides you through each step. 🎯

### 📋 Workflow

1. **Fetch** raw data from Google (expensive, rate-limited):

```bash
./seo fetch           # 60 URLs (quick) ⚡
./seo fetch --full    # All URLs (slow, run overnight) 🌙
```

I wasn't able to increase the 60req/min limit, so if you have a lot
of pages, use `--full` to get the full picture.

2. **Render** reports from fetched data (cheap, repeatable):

```bash
./seo render          # Uses latest fetch
./seo render --data reports/seo/20251229-093000  # Specific fetch
```

Data is saved to timestamped directories: `reports/seo/YYYYMMDD-HHMMSS/` 📁

## 👤 Author

Adam Koszek <adam@koszek.com>

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

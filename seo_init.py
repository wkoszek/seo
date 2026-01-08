"""Initialize Google Cloud credentials."""

import json
import shutil
import webbrowser
from pathlib import Path

from seo_common import (
    CLIENT_SECRETS_FILE, GOOGLE_CLOUD_CONSOLE,
    GOOGLE_CLOUD_API_LIBRARY, GOOGLE_CLOUD_CREDENTIALS,
    print_header, print_step, print_success, print_error, print_info
)


def cmd_init(args):
    """Initialize Google Cloud credentials setup."""
    print_header("SEO Tool - Google Cloud Setup")

    if CLIENT_SECRETS_FILE.exists():
        print_success("client_secrets.json already exists")
        print_info("Run 'seo auth' to authenticate, or delete the file to reconfigure.")
        return 0

    print("This wizard sets up Google Cloud credentials for Search Console access.\n")

    input("Press ENTER to start...")

    # Step 1: Project
    print_header("Step 1: Select Google Cloud Project")
    print("Select an existing project or create a new one.\n")
    print_info("Opening Google Cloud Console...")
    webbrowser.open(GOOGLE_CLOUD_CONSOLE)
    input("\nPress ENTER when ready...")

    # Step 2: Enable API
    print_header("Step 2: Enable Search Console API")
    print('Click the blue "ENABLE" button.\n')
    print_info("Opening API page...")
    webbrowser.open(GOOGLE_CLOUD_API_LIBRARY)
    input("\nPress ENTER when enabled...")

    # Step 3: Create credentials
    print_header("Step 3: Create OAuth Client")
    print_step(1, 'Click "+ Create client"')
    print_step(2, 'Select "Desktop app"')
    print_step(3, 'Name it "SEO Tool" and click Create')
    print_step(4, 'Click "Download JSON"')
    print()
    print_info("Opening Credentials page...")
    webbrowser.open(GOOGLE_CLOUD_CREDENTIALS)
    input("\nPress ENTER after downloading...")

    # Step 4: Install file
    print_header("Step 4: Install Credentials")
    print("Drag & drop the downloaded JSON file here, or paste the path:\n")

    while True:
        file_path = input("Path: ").strip().strip("'\"")
        if not file_path:
            continue

        source = Path(file_path)
        if not source.exists():
            print_error("File not found. Try again.")
            continue

        try:
            with open(source) as f:
                data = json.load(f)
            if "installed" not in data and "web" not in data:
                print_error("Not a valid Google OAuth file. Try again.")
                continue
        except:
            print_error("Invalid JSON. Try again.")
            continue

        shutil.copy2(source, CLIENT_SECRETS_FILE)
        print_success("Credentials installed!")
        break

    print_header("Setup Complete")
    print("Next: Run './seo auth' to authenticate.\n")
    return 0

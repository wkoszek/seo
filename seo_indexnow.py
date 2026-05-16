"""Generate / inspect the IndexNow key file.

IndexNow (https://www.indexnow.org/) lets us notify Bing/Yandex about new or
updated URLs without using their dashboards. Each origin proves it owns the
key by serving `<key>.txt` at its root containing the key string. We share a
single key across every site we run by storing it at:

    ~/Sync/static/indexnow-key.txt

Each Hugo site's build is expected to copy that file into the rendered
output (typically by symlinking or copying into the site's `static/` dir
before `hugo` runs) so `<key>.txt` is served at the site root.
"""

import secrets
import string
from pathlib import Path

from seo_common import (
    print_header, print_success, print_error, print_info,
)

# Shared key file: ~/Sync/static/indexnow-key.txt — matches the path read by
# seo_ping.INDEXNOW_KEY_FILE.
INDEXNOW_KEY_FILE = Path.home() / "Sync" / "static" / "indexnow-key.txt"
KEY_LENGTH = 32  # IndexNow requires 8-128 alphanumeric chars; 32 is plenty.


def cmd_indexnow(args):
    """Generate the IndexNow key file if missing; show its location and value."""
    print_header("IndexNow Key")

    if INDEXNOW_KEY_FILE.exists() and not args.force:
        key = INDEXNOW_KEY_FILE.read_text().strip()
        print_info(f"Key file: {INDEXNOW_KEY_FILE}")
        print_info(f"Key:      {key}")
        print_info("Already configured — pass --force to regenerate.")
        return 0

    INDEXNOW_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    alphabet = string.ascii_letters + string.digits
    key = "".join(secrets.choice(alphabet) for _ in range(KEY_LENGTH))
    INDEXNOW_KEY_FILE.write_text(key + "\n")

    print_success(f"Wrote {INDEXNOW_KEY_FILE}")
    print_info(f"Key: {key}")
    print()
    print_info("Each Hugo site needs to serve <key>.txt at its root for verification.")
    print_info("In each site's Makefile (or build step), copy the file into static/ before")
    print_info(f"running hugo, e.g.:")
    print_info(f"    cp {INDEXNOW_KEY_FILE} static/{key}.txt")
    print_info("then redeploy. After that, `seo ping` will POST to IndexNow automatically.")
    return 0

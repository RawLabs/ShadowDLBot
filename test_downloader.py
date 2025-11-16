"""
Small manual test harness for the downloader.

Usage:
    python test_downloader.py "https://www.youtube.com/watch?v=xxxx"

This will:
- Call download_video(url)
- Print returned metadata
- Confirm file exists
"""

import os
import sys

from downloader.core import download_video

def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python test_downloader.py <video_url> [--allow-long]")
        return

    allow_long = False
    if "--allow-long" in args:
        allow_long = True
        args.remove("--allow-long")

    url = args[0]
    result = download_video(url, allow_long=allow_long)

    print("Title:", result["title"])
    print("Duration:", result["duration"], "seconds")
    print("Platform:", result["platform"])
    print("File:", result["file_path"])
    print("Size:", result["filesize_bytes"], "bytes")

    if os.path.exists(result["file_path"]):
        print("File exists ✔️")
    else:
        print("File missing ❌")

if __name__ == "__main__":
    main()

"""
Small manual test harness for the downloader.

Usage:
    python test_downloader.py "https://www.youtube.com/watch?v=xxxx"

This will:
- Call download_video(url)
- Print returned metadata
- Confirm file exists
"""

from downloader.core import download_video
import sys
import os

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_downloader.py <video_url>")
        return

    url = sys.argv[1]
    result = download_video(url)

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

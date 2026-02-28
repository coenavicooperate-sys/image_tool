"""
写真抽出のCLI - サブプロセスとして実行し、Streamlitのイベントループ競合を回避
Windows + Streamlit 環境で Playwright の NotImplementedError を防ぐため、
別プロセスで実行して結果をJSONで出力する
"""

import json
import sys

from photo_extractor import extract_photos_from_url


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "URLを指定してください"}), file=sys.stderr)
        sys.exit(1)
    url = sys.argv[1].strip()
    try:
        photos = extract_photos_from_url(url, headless=True)
        print(json.dumps({"photos": photos, "count": len(photos)}))
    except Exception as e:
        print(json.dumps({"error": str(e), "type": type(e).__name__}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

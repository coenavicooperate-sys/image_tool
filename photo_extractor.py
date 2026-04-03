"""
写真抽出モジュール - Playwright を使用してホットペッパー/食べログから画像を取得
クラウド環境（Linux）対応：ヘッドレスモード、必要なブラウザは playwright install で事前インストール
"""

import re
import time
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


# サムネイルURLを高画質URLに変換するパターン
HIGH_RES_PATTERNS = [
    # 食べログ tblg.k-img.com: 一覧の 150px サムネ → 1024（クリック後に近い大きさ）
    (re.compile(r'150x150_rect_', re.I), r'1024x1024_rect_'),
    (re.compile(r'150x150_square_', re.I), r'1024x1024_rect_'),
    # 食べログ tblg.k-img.com: 小サイズ → 1024x1024 で高画質取得
    (re.compile(r'320x320_rect_', re.I), r'1024x1024_rect_'),
    (re.compile(r'320x320_square_', re.I), r'1024x1024_rect_'),
    (re.compile(r'640x640_rect_', re.I), r'1024x1024_rect_'),
    (re.compile(r'640x640_square_', re.I), r'1024x1024_rect_'),
    (re.compile(r'480x480_rect_', re.I), r'1024x1024_rect_'),
    # 食べログ: _s.jpg → _l.jpg, _m.jpg → _l.jpg など
    (re.compile(r'_s(\d*)\.(jpg|jpeg|png|webp)', re.I), r'_l\1.\2'),
    (re.compile(r'_m(\d*)\.(jpg|jpeg|png|webp)', re.I), r'_l\1.\2'),
    (re.compile(r'_thumb\.(jpg|jpeg|png|webp)', re.I), r'.\1'),
    # ホットペッパー: imgfp.hotp.jp のサイズ指定
    (re.compile(r'(imgfp\.hotp\.jp[^"\']*?)_[sSmM]\.', re.I), r'\1_L.'),
    # 一般的なパターン: 小さいサイズ指定を除去
    (re.compile(r'[?&](w|width|h|height|size)=\d+', re.I), ''),
]


def _tabelog_boost_wxh_in_url(url: str) -> str:
    """
    食べログ CDN の任意 WxH_rect_ / WxH_square_（横長・縦長の非正方形サムネ含む）を
    長辺 1024px・縦横比維持の rect に拡大。正方形のみの置換パターンに無いサイズを拾う。
    """
    if 'tblg.k-img.com' not in url.lower():
        return url

    def repl(m: re.Match) -> str:
        try:
            w, h = int(m.group(1)), int(m.group(2))
        except ValueError:
            return m.group(0)
        if w <= 0 or h <= 0:
            return m.group(0)
        if max(w, h) >= 1024:
            return m.group(0)
        if w >= h:
            nw, nh = 1024, max(1, round(1024 * h / w))
        else:
            nh, nw = 1024, max(1, round(1024 * w / h))
        return f"{nw}x{nh}_rect_"

    return re.sub(r'(\d+)x(\d+)_(rect|square)_', repl, url, flags=re.I)


def to_high_res_url(url: str) -> str:
    """サムネイルURLを高画質版URLに変換"""
    if not url or not url.startswith(('http://', 'https://')):
        return url
    result = url
    for pattern, replacement in HIGH_RES_PATTERNS:
        result = pattern.sub(replacement, result)
    result = _tabelog_boost_wxh_in_url(result)
    # 重複した ?& を整理
    result = re.sub(r'\?&+', '?', result).rstrip('?&')
    return result


def normalize_image_url(url: str, base_url: str) -> str:
    """相対URLを絶対URLに変換し、高画質版に変換"""
    if not url:
        return ""
    if url.startswith('//'):
        url = 'https:' + url
    elif url.startswith('/'):
        parsed = urlparse(base_url)
        url = f"{parsed.scheme}://{parsed.netloc}{url}"
    elif not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)
    return to_high_res_url(url)


def is_photo_page(url: str) -> bool:
    """写真一覧ページかどうか判定"""
    url_lower = url.lower()
    return (
        'dtlphotolst' in url_lower  # 食べログ
        or '/photo' in url_lower
        or '/photos' in url_lower
        or 'photolst' in url_lower
    )


def get_photo_page_url(url: str) -> str | None:
    """
    店舗ページURLから写真一覧ページURLを推測
    既に写真ページの場合はそのまま返す
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    url_lower = url.lower()

    if is_photo_page(url):
        # 食べログ smp2（スマホ版）→ PC版に変換（画像抽出が安定しやすい）
        if 'tabelog.com' in parsed.netloc and '/smp2' in path:
            path = path.replace('/smp2', '').rstrip('/')
            return f"{parsed.scheme}://{parsed.netloc}{path}/"
        return url


def get_fallback_photo_url(url: str) -> str | None:
    """
    カテゴリ付きURL（例: dtlphotolst/1/smp2/）で失敗した場合の代替URLを返す
    「全写真」ページの方が安定することがある
    """
    if 'tabelog.com' not in url or 'dtlphotolst' not in url:
        return None
    parsed = urlparse(url)
    path = parsed.path.rstrip('/')
    # dtlphotolst/1/ や dtlphotolst/2/ など → dtlphotolst/ に変換
    if re.search(r'/dtlphotolst/\d+/', path):
        base = path.split('/dtlphotolst')[0]
        return f"{parsed.scheme}://{parsed.netloc}{base}/dtlphotolst/"
    return None

    # 食べログ: 店舗ページ → dtlphotolst に変換
    if 'tabelog.com' in parsed.netloc:
        # 例: /tokyo/A1303/A130302/13215961/ → /tokyo/A1303/A130302/13215961/dtlphotolst/
        if '/dtlbordtl/' in path or '/dtlrvwlst/' in path:
            path = path.split('/dtl')[0]
        if 'dtlphotolst' not in path:
            base = path.split('/dtl')[0] if '/dtl' in path else path
            return f"{parsed.scheme}://{parsed.netloc}{base}/dtlphotolst/"

    # ホットペッパー: 店舗ページに /photo や /photos を付与
    if 'hotpepper.jp' in parsed.netloc or 'hotpepper' in parsed.netloc:
        if '/photo' not in path and '/photos' not in path:
            return f"{parsed.scheme}://{parsed.netloc}{path}/photo/"
        return url

    return url


def _add_image_url(results: list, seen_urls: set, url: str, base_url: str) -> None:
    """重複チェックして画像URLを追加"""
    if not url or len(url) < 20:
        return
    if 'pixel' in url.lower() or 'tracking' in url.lower() or 'blank' in url.lower():
        return
    if 'avatar' in url.lower() or 'icon' in url.lower():
        return
    if 'imgvc.com' in url.lower():  # トラッキング用画像
        return
    if not any(x in url.lower() for x in ['.jpg', '.jpeg', '.png', '.webp']):
        return
    full_url = normalize_image_url(url, base_url)
    # 極小は除外。食べログの 150px は to_high_res で 1024 に昇格する前にここへ来ないよう、変換後に判定
    if '100x100' in full_url:
        return
    if '150x150' in full_url and 'tblg.k-img.com' not in full_url.lower():
        return
    if full_url in seen_urls:
        return
    seen_urls.add(full_url)
    results.append({"url": full_url, "thumb_url": url})


def _extract_from_page(page, base_url: str, seen_urls: set, results: list) -> None:
    """ページから画像URLを抽出（共通処理）"""
    for img in page.query_selector_all('img[src]'):
        src = img.get_attribute("src")
        _add_image_url(results, seen_urls, src or "", base_url)
    for img in page.query_selector_all('img[data-src], img[data-lazy-src]'):
        src = img.get_attribute("data-src") or img.get_attribute("data-lazy-src")
        _add_image_url(results, seen_urls, src or "", base_url)
    for a in page.query_selector_all('a[href*="tblg.k-img.com"], a[href*=".jpg"], a[href*=".jpeg"], a[href*=".png"]'):
        href = a.get_attribute("href")
        _add_image_url(results, seen_urls, href or "", base_url)
    if len(results) < 5:
        urls = page.evaluate("""
            () => {
                const urls = new Set();
                document.querySelectorAll('img[src], a[href]').forEach(el => {
                    const u = el.getAttribute('src') || el.getAttribute('href') || '';
                    if (u.match(/\\.(jpg|jpeg|png|webp)/i) && (u.includes('tblg.k-img.com') || u.includes('imgfp.hotp'))) {
                        urls.add(u);
                    }
                });
                return Array.from(urls);
            }
        """)
        for u in urls or []:
            _add_image_url(results, seen_urls, u, base_url)


def extract_photos_from_url(input_url: str, headless: bool = True) -> list[dict]:
    """
    指定URLから写真を抽出
    Returns: [{"url": str, "thumb_url": str}, ...]
    """
    photo_page = get_photo_page_url(input_url)
    if not photo_page:
        photo_page = input_url

    seen_urls: set[str] = set()
    results: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP",
        )
        page = context.new_page()

        try:
            page.goto(photo_page, wait_until="load", timeout=90000)
            time.sleep(5)

            # スクロールして遅延読み込み画像を表示
            last_height = 0
            scroll_attempts = 0
            max_scrolls = 50

            while scroll_attempts < max_scrolls:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    scroll_attempts += 1
                    if scroll_attempts >= 3:
                        break
                else:
                    scroll_attempts = 0
                last_height = new_height

            base_url = page.url
            _extract_from_page(page, base_url, seen_urls, results)

            # 食べログ: 少ない場合のフォールバック
            if len(results) < 3 and 'tabelog.com' in input_url:
                # 1) カテゴリ付きURL（/1/など）→ 全写真ページを試行
                fallback = get_fallback_photo_url(input_url)
                if fallback and fallback != photo_page:
                    try:
                        page.goto(fallback, wait_until="load", timeout=60000)
                        time.sleep(4)
                        for _ in range(8):
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(1)
                        base_url = page.url
                        _extract_from_page(page, base_url, seen_urls, results)
                    except Exception:
                        pass
                # 2) まだ少なければ smp2（元URL）を試行
                if len(results) < 3 and '/smp2' in input_url:
                    try:
                        page.goto(input_url, wait_until="load", timeout=60000)
                        time.sleep(4)
                        for _ in range(5):
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(1)
                        base_url = page.url
                        _extract_from_page(page, base_url, seen_urls, results)
                    except Exception:
                        pass

        except PlaywrightTimeout:
            pass
        except Exception:
            raise
        finally:
            browser.close()

    return results

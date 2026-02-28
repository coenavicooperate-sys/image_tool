"""
Google Maps 写真抽出モジュール - Playwright を使用
キーワード検索 → 施設の写真タブ（オーナー提供）へ遷移 → 最大30枚をスクロール収集
サーバー実行想定: headless=True, args=['--no-sandbox']
"""

import re
import time
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# 取得枚数の上限
MAX_IMAGES_DEFAULT = 30

# Google 画像URLのサムネイル→高解像度変換パターン
# lh3.googleusercontent.com: =w100-h100, =s100, =w400 などを =s2048 に置換
GOOGLE_IMAGE_SIZE_PATTERNS = [
    (re.compile(r'=w\d+-h\d+', re.I), '=s2048'),
    (re.compile(r'=w\d+', re.I), '=s2048'),
    (re.compile(r'=h\d+', re.I), '=s2048'),
    (re.compile(r'=s\d+', re.I), '=s2048'),
    (re.compile(r'/s\d+/', re.I), '/s2048/'),
]


def to_high_res_google_url(url: str) -> str:
    """Google画像URLを高解像度版に変換"""
    if not url or 'googleusercontent.com' not in url:
        return url
    result = url
    for pattern, replacement in GOOGLE_IMAGE_SIZE_PATTERNS:
        result = pattern.sub(replacement, result)
    # サイズ指定が無い場合に追加
    if '=s' not in result and '=w' not in result and '/s' not in result:
        if '?' in result:
            result = result.rstrip('&') + '&s2048'
        else:
            result = result + '=s2048'
    return result


def normalize_image_url(url: str, base_url: str) -> str:
    """相対URLを絶対URLに変換し、高解像度版に変換"""
    if not url:
        return ""
    if url.startswith('//'):
        url = 'https:' + url
    elif url.startswith('/'):
        parsed = urlparse(base_url)
        url = f"{parsed.scheme}://{parsed.netloc}{url}"
    elif not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)
    if 'googleusercontent.com' in url:
        return to_high_res_google_url(url)
    return url


def _add_image_url(
    results: list,
    seen_urls: set,
    url: str,
    base_url: str,
    max_count: int,
) -> bool:
    """重複チェックして画像URLを追加。max_countに達したらFalseを返す"""
    if len(results) >= max_count:
        return False
    if not url or len(url) < 20:
        return True
    if any(x in url.lower() for x in ['pixel', 'tracking', 'blank', 'avatar', 'icon', '1x1']):
        return True
    if not any(x in url.lower() for x in ['.jpg', '.jpeg', '.png', 'googleusercontent.com']):
        return True
    full_url = normalize_image_url(url, base_url)
    if full_url in seen_urls:
        return True
    seen_urls.add(full_url)
    results.append({"url": full_url, "thumb_url": url})
    return len(results) < max_count


def extract_photos_from_google_maps(
    keyword: str,
    max_images: int = MAX_IMAGES_DEFAULT,
    headless: bool = True,
) -> list[dict]:
    """
    キーワードでGoogle Mapsを検索し、最初の施設の写真タブ（オーナー提供優先）から
    最大 max_images 枚の画像URLを収集する。

    Returns: [{"url": str, "thumb_url": str}, ...]
    """
    if max_images <= 0:
        max_images = MAX_IMAGES_DEFAULT
    max_images = min(max_images, 30)

    seen_urls: set[str] = set()
    results: list[dict] = []

    search_url = f"https://www.google.com/maps/search/{keyword.replace(' ', '+')}"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-setuid-sandbox'],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ja-JP",
        )
        page = context.new_page()

        try:
            # 1. 検索ページへ遷移
            page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)

            # 2. 最初の検索結果（施設）をクリック
            try:
                # 検索結果の最初の施設カードをクリック（複数のセレクタを試行）
                place_selectors = [
                    'a[href*="/maps/place/"]',
                    '[role="feed"] a[href*="/place/"]',
                    'a[data-index="0"]',
                    '.Nv2PK',  # 施設カード
                ]
                clicked = False
                for sel in place_selectors:
                    try:
                        first_place = page.locator(sel).first
                        if first_place.count() > 0:
                            first_place.click(timeout=5000)
                            clicked = True
                            break
                    except Exception:
                        continue
                if not clicked:
                    # フォールバック: 最初のリンクをクリック
                    page.locator('a[href*="/maps/place/"]').first.click(timeout=8000)
            except Exception as e:
                raise RuntimeError(f"検索結果から施設を選択できませんでした: {e}")

            time.sleep(2)

            # 3. 「写真」タブをクリック
            try:
                photo_tab_selectors = [
                    'button[aria-label="写真"]',
                    'button[aria-label="Photos"]',
                    '[data-tab-index="1"]',  # 写真タブのインデックス
                    'button:has-text("写真")',
                    'button:has-text("Photos")',
                    '[role="tab"]:has-text("写真")',
                    '[role="tab"]:has-text("Photos")',
                ]
                tab_clicked = False
                for sel in photo_tab_selectors:
                    try:
                        tab = page.locator(sel).first
                        if tab.count() > 0:
                            tab.click(timeout=3000)
                            tab_clicked = True
                            break
                    except Exception:
                        continue
                if not tab_clicked:
                    # パネル内の「オーナー提供」や写真セクションを探す
                    page.evaluate("window.scrollTo(0, 300)")
                    time.sleep(1)
            except Exception:
                pass  # 写真タブが無くても続行

            time.sleep(2)

            # 4. オーナー提供セクションを探してクリック（あれば）
            try:
                owner_selectors = [
                    'button:has-text("オーナー提供")',
                    'button:has-text("Owner")',
                    '[aria-label*="オーナー"]',
                    '[aria-label*="Owner"]',
                    'span:has-text("オーナー提供")',
                ]
                for sel in owner_selectors:
                    try:
                        el = page.locator(sel).first
                        if el.count() > 0:
                            el.click(timeout=2000)
                            time.sleep(1.5)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            base_url = page.url

            # 5. 写真一覧をスクロールしながら画像URLを収集（最大 max_images 枚）
            scroll_container_selectors = [
                '[role="main"]',
                '.m6QErb[aria-label]',
                '.scrollable-show',
                '[class*="scroll"]',
                'body',
            ]

            last_count = 0
            no_new_count = 0
            max_no_new = 5

            for scroll_attempt in range(30):
                if len(results) >= max_images:
                    break

                # 画像要素からURLを収集
                for img in page.query_selector_all('img[src*="googleusercontent.com"]'):
                    try:
                        src = img.get_attribute("src")
                        if src and _add_image_url(results, seen_urls, src, base_url, max_images) is False:
                            break
                    except Exception:
                        pass

                # data-src など遅延読み込み
                for img in page.query_selector_all('img[data-src*="googleusercontent.com"]'):
                    try:
                        src = img.get_attribute("data-src")
                        if src and _add_image_url(results, seen_urls, src, base_url, max_images) is False:
                            break
                    except Exception:
                        pass

                # 背景画像スタイル
                for el in page.query_selector_all('[style*="googleusercontent.com"]'):
                    try:
                        style = el.get_attribute("style") or ""
                        urls = re.findall(r'url\(["\']?([^"\')\s]+)["\']?\)', style)
                        for u in urls:
                            if 'googleusercontent' in u and _add_image_url(results, seen_urls, u, base_url, max_images) is False:
                                break
                    except Exception:
                        pass

                if len(results) >= max_images:
                    break

                if len(results) == last_count:
                    no_new_count += 1
                    if no_new_count >= max_no_new:
                        break
                else:
                    no_new_count = 0
                last_count = len(results)

                # スクロール
                try:
                    page.evaluate("""
                        () => {
                            const scrollables = document.querySelectorAll('[role="main"] .m6QErb, .scrollable-show, [class*="scroll"]');
                            for (const el of scrollables) {
                                if (el.scrollHeight > el.clientHeight) {
                                    el.scrollTop = el.scrollHeight;
                                    return;
                                }
                            }
                            window.scrollTo(0, document.body.scrollHeight);
                        }
                    """)
                except Exception:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

                time.sleep(1.2)

        except PlaywrightTimeout:
            pass
        except Exception:
            raise
        finally:
            browser.close()

    return results[:max_images]

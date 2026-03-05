"""
店舗写真 抽出・選択・一括加工 Webアプリ
ホットペッパー/食べログのURLから写真を取得し、指定サイズで加工・ZIPダウンロード
"""

import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import requests
import streamlit as st
from PIL import Image

from dotenv import load_dotenv
from image_processor import LOGO_POSITIONS, SIZE_PRESETS, process_image, save_as_webp

load_dotenv()

st.set_page_config(page_title="店舗写真加工ツール", page_icon="📷", layout="wide")

# 認証用（環境変数 IMAGE_TOOL_USERNAME, IMAGE_TOOL_PASSWORD で設定）
AUTH_USERNAME = os.environ.get("IMAGE_TOOL_USERNAME", "")
AUTH_PASSWORD = os.environ.get("IMAGE_TOOL_PASSWORD", "")

# session_state 初期化
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "extracted_photos" not in st.session_state:
    st.session_state.extracted_photos = []
if "selected_indices" not in st.session_state:
    st.session_state.selected_indices = set()
if "processed_images" not in st.session_state:
    st.session_state.processed_images = []
if "processed_size_choice" not in st.session_state:
    st.session_state.processed_size_choice = ""
if "logo_img" not in st.session_state:
    st.session_state.logo_img = None
if "image_cache" not in st.session_state:
    st.session_state.image_cache = {}


def _fetch_image_bytes_inner(url: str, headers: dict) -> bytes | None:
    """画像取得の内部実装"""
    try:
        r = requests.get(url, timeout=20, headers=headers)
        r.raise_for_status()
        if len(r.content) < 500:
            return None
        return r.content
    except Exception:
        return None


def fetch_image_bytes(url: str, fallback_url: str | None = None) -> bytes | None:
    """URLから画像を取得（食べログCDNはReferer推奨、失敗時はフォールバックURLを試行）"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    if "tblg.k-img.com" in url or "imgfp.hotp" in url:
        headers["Referer"] = "https://tabelog.com/"
    elif "hotpepper" in url:
        headers["Referer"] = "https://www.hotpepper.jp/"

    data = _fetch_image_bytes_inner(url, headers)
    if data:
        return data
    if fallback_url and fallback_url != url:
        return _fetch_image_bytes_inner(fallback_url, headers)
    return None


def fetch_image_bytes_cached(url: str, fallback_url: str | None = None) -> bytes | None:
    """URLから画像を取得（session_state にキャッシュして再利用）"""
    cache = st.session_state.image_cache
    cache_key = url
    if cache_key not in cache:
        data = fetch_image_bytes(url, fallback_url)
        if data:
            cache[cache_key] = data
        return data
    return cache[cache_key]


def extract_photos_via_subprocess(url: str) -> tuple[list[dict], str | None]:
    """
    サブプロセスでPlaywrightを実行（Windows + Streamlit の NotImplementedError 回避）
    Returns: (photos, error_message)
    """
    cli_path = Path(__file__).parent / "extract_cli.py"
    try:
        result = subprocess.run(
            [sys.executable, str(cli_path), url],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path(__file__).parent),
        )
        if result.returncode != 0:
            try:
                err_data = json.loads(result.stderr)
                return [], err_data.get("error", result.stderr)
            except json.JSONDecodeError:
                return [], result.stderr or "不明なエラー"
        data = json.loads(result.stdout)
        if "error" in data:
            return [], data["error"]
        return data.get("photos", []), None
    except subprocess.TimeoutExpired:
        return [], "タイムアウト（120秒）"
    except Exception as e:
        return [], str(e)


def reset_workflow():
    """作業をリセットして最初からやり直せるようにする"""
    st.session_state.extracted_photos = []
    st.session_state.selected_indices = set()
    st.session_state.image_cache = {}
    st.session_state.processed_images = []
    st.session_state.processed_size_choice = ""
    for key in list(st.session_state.keys()):
        if key.startswith("photo_sel_"):
            del st.session_state[key]


def show_login_page() -> bool:
    """ログイン画面を表示。認証成功で True を返す"""
    if not AUTH_USERNAME or not AUTH_PASSWORD:
        return True
    if st.session_state.authenticated:
        return True

    st.title("🔐 ログイン")
    st.caption("関係者のみアクセスできます")
    with st.form("login_form"):
        username = st.text_input("ID（ユーザー名）")
        password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン")
        if submitted:
            if username == AUTH_USERNAME and password == AUTH_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("ID または パスワードが正しくありません")
    return False


def main():
    if not show_login_page():
        return

    st.title("📷 店舗写真 抽出・選択・一括加工")
    st.caption("ホットペッパー / 食べログのURLから写真を取得し、SNS用に加工できます")

    # ========== サイドバー: 加工設定 ==========
    with st.sidebar:
        st.header("⚙️ 加工設定")

        size_choice = st.selectbox(
            "サイズ",
            options=list(SIZE_PRESETS.keys()),
            index=0,
        )
        size_preset = SIZE_PRESETS[size_choice]

        st.divider()
        logo_file = st.file_uploader(
            "ロゴ画像（任意）",
            type=["png", "jpg", "jpeg", "webp"],
            help="透過PNG推奨",
            key="logo_uploader",
        )
        if logo_file:
            st.session_state.logo_img = Image.open(logo_file).convert("RGBA")
        logo_img = st.session_state.logo_img
        if logo_img is not None and st.button("ロゴをクリア", key="clear_logo"):
            st.session_state.logo_img = None
            st.rerun()

        logo_width_pct = st.slider(
            "ロゴサイズ（画像横幅に対する割合）",
            min_value=20,
            max_value=40,
            value=25,
            step=1,
            format="%d%%",
            help="20%〜40%の範囲で指定",
        )
        logo_width_pct /= 100

        logo_pos_label = st.selectbox(
            "ロゴ位置",
            options=list(LOGO_POSITIONS.keys()) + ["自分で調整"],
            index=0,
        )

        logo_custom_x = None
        logo_custom_y = None
        if logo_pos_label == "自分で調整":
            st.caption("0=左/上、100=右/下")
            logo_custom_x = st.slider("水平位置（左→右）", 0, 100, 85, format="%d%%")
            logo_custom_y = st.slider("垂直位置（上→下）", 0, 100, 85, format="%d%%")
            logo_position = "custom"
        else:
            logo_position = LOGO_POSITIONS[logo_pos_label]

        st.divider()
        if st.button("🔄 作業をリセット", key="reset_btn", help="抽出した写真・選択・加工結果をクリアして最初からやり直します"):
            reset_workflow()
            st.rerun()

        if AUTH_USERNAME and AUTH_PASSWORD and st.button("🚪 ログアウト", key="logout_btn"):
            st.session_state.authenticated = False
            st.rerun()

    # ========== STEP 1: 写真抽出 ==========
    st.header("STEP 1: 写真の抽出")
    url_input = st.text_input(
        "ホットペッパー または 食べログのURL",
        placeholder="https://tabelog.com/... または https://...hotpepper.jp/...",
        key="url_input",
    )

    if st.button("🔍 写真を抽出", type="primary"):
        if not url_input or not url_input.strip():
            st.error("URLを入力してください")
        else:
            with st.spinner("写真を取得中…（数十秒かかる場合があります）"):
                photos, err = extract_photos_via_subprocess(url_input.strip())
                if err:
                    st.error(f"**抽出に失敗しました:** {err}")
                    st.info(
                        "**対処法:** ターミナルで `playwright install chromium` を実行してブラウザをインストールしてください。"
                    )
                    st.session_state.extracted_photos = []
                else:
                    st.session_state.extracted_photos = photos
                    st.session_state.selected_indices = set()
                    st.session_state.image_cache = {}
                    st.success(f"{len(photos)} 枚の写真を取得しました")

    photos = st.session_state.extracted_photos
    if not photos:
        st.info("URLを入力して「写真を抽出」をクリックしてください")
        return

    # ========== STEP 2: 選択用チェックボックス付き一覧 ==========
    st.header("STEP 2: 写真の選択")
    st.caption("加工する写真を選択して「選択を反映」をクリックしてください（チェック中は画面が再読み込みされません）")

    col_select, _ = st.columns([1, 4])
    with col_select:
        if st.button("全選択"):
            st.session_state.selected_indices = set(range(len(photos)))
            st.rerun()
        if st.button("全解除"):
            st.session_state.selected_indices = set()
            st.rerun()

    with st.form("photo_selection_form"):
        for row_start in range(0, len(photos), 5):
            cols = st.columns(5)
            for col_idx in range(5):
                i = row_start + col_idx
                if i >= len(photos):
                    break
                with cols[col_idx]:
                    try:
                        img_data = fetch_image_bytes_cached(
                            photos[i]["url"],
                            fallback_url=photos[i].get("thumb_url"),
                        )
                        if img_data:
                            img = Image.open(io.BytesIO(img_data))
                            st.image(img, use_container_width=True)
                        else:
                            st.caption("読み込みエラー")
                    except Exception:
                        st.caption("読み込みエラー")

                    st.checkbox(
                        f"選択 #{i+1}",
                        value=(i in st.session_state.selected_indices),
                        key=f"photo_sel_{i}",
                    )

        submitted = st.form_submit_button("選択を反映")
        if submitted:
            new_selected = set()
            for i in range(len(photos)):
                if st.session_state.get(f"photo_sel_{i}", False):
                    new_selected.add(i)
            st.session_state.selected_indices = new_selected
            st.rerun()

    selected = sorted(st.session_state.selected_indices)
    st.info(f"選択中: {len(selected)} 枚 / 全 {len(photos)} 枚")

    if not selected:
        st.warning("加工する写真を1枚以上選択して「選択を反映」をクリックしてください")
        return

    # ========== STEP 3 & 4: 加工・プレビュー・ZIP ==========
    st.header("STEP 3 & 4: 加工・出力")

    if st.button("🖼️ 加工を実行"):
        processed = []
        progress = st.progress(0)
        for idx, i in enumerate(selected):
            progress.progress((idx + 1) / len(selected))
            photo = photos[i]
            img_bytes = fetch_image_bytes_cached(
                photo["url"],
                fallback_url=photo.get("thumb_url"),
            )
            if not img_bytes:
                continue
            try:
                result = process_image(
                    img_bytes,
                    size_preset,
                    logo=logo_img,
                    logo_width_percent=logo_width_pct,
                    logo_position=logo_position,
                    logo_custom_x=logo_custom_x,
                    logo_custom_y=logo_custom_y,
                )
                webp_bytes = save_as_webp(result)
                processed.append((i + 1, webp_bytes))
            except Exception:
                pass
        progress.empty()
        st.session_state.processed_images = processed
        st.session_state.processed_size_choice = size_choice
        st.rerun()

    proc = st.session_state.processed_images
    size_used = st.session_state.get("processed_size_choice", "")
    if proc:
        st.success(f"{len(proc)} 枚を加工しました")
        st.subheader("プレビュー")
        prev_cols = st.columns(min(5, len(proc)))
        for idx, (num, img_bytes) in enumerate(proc):
            with prev_cols[idx % 5]:
                st.image(Image.open(io.BytesIO(img_bytes)), use_container_width=True)
                st.caption(f"#{num}")

        st.subheader("ZIPダウンロード（WebP形式・約100KB/枚）")
        file_prefix = "TOP_tate" if "縦型" in size_used else "TOP"
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for num, img_bytes in proc:
                zf.writestr(f"{file_prefix}_{num}.webp", img_bytes)
        zip_buf.seek(0)

        st.download_button(
            "📦 全画像をZIPでダウンロード",
            data=zip_buf,
            file_name="processed_photos.zip",
            mime="application/zip",
        )


if __name__ == "__main__":
    main()

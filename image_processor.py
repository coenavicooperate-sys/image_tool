"""
画像加工モジュール - Pillow を使用したリサイズ・クロップ・ロゴ合成
"""

import io
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

# 出力サイズプリセット
SIZE_PRESETS = {
    "縦型 (1080x1350px)": (1080, 1350),
    "横型 (1024x682px)": (1024, 682),
}

# WebP出力の目標ファイルサイズ（バイト）
WEBP_TARGET_BYTES = 100_000

# 縦型画像（スマホ表示向け）の補正
MOBILE_BRIGHTNESS = 1.12  # 若干明るく
MOBILE_CONTRAST = 1.15   # コントラストを上げる


def enhance_for_mobile(img: Image.Image) -> Image.Image:
    """スマホ表示向けに明るさ・コントラストを補正"""
    img = ImageEnhance.Brightness(img).enhance(MOBILE_BRIGHTNESS)
    img = ImageEnhance.Contrast(img).enhance(MOBILE_CONTRAST)
    return img


def save_as_webp(img: Image.Image, target_bytes: int = WEBP_TARGET_BYTES) -> bytes:
    """
    WebP形式で保存し、目標ファイルサイズ（約100KB）になるよう品質を調整
    """
    img = img.convert("RGB")
    quality = 82
    for _ in range(15):
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=quality, method=6)
        size = len(buf.getvalue())
        if target_bytes * 0.7 <= size <= target_bytes * 1.3:
            return buf.getvalue()
        if size > target_bytes:
            quality = max(20, quality - 8)
        else:
            quality = min(95, quality + 5)
    return buf.getvalue()


# ロゴ位置オプション
LOGO_POSITIONS = {
    "右下": "bottom_right",
    "左下": "bottom_left",
    "右上": "top_right",
    "左上": "top_left",
}


def center_crop_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """中央合わせクロップ＆リサイズ"""
    img = img.convert("RGB")
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    elif src_ratio < target_ratio:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))

    return img.resize((target_w, target_h), Image.Resampling.LANCZOS)


def add_logo_outline(logo: Image.Image, stroke_width: int = 2, stroke_color: tuple = (255, 255, 255)) -> Image.Image:
    """
    ロゴに縁取りを追加して背景に溶け込まないようにする
    白い縁取りで暗い背景でも、黒い縁取りで明るい背景でも見やすくする
    """
    logo = logo.convert("RGBA")
    r, g, b, a = logo.split()
    dilated = a.filter(ImageFilter.MaxFilter(2 * stroke_width + 1))
    outline_a = ImageChops.subtract_modulo(dilated, a)
    stroke_layer = Image.new("RGBA", logo.size, (*stroke_color, 0))
    stroke_layer.putalpha(outline_a)
    return Image.alpha_composite(stroke_layer, logo)


def resize_logo_by_width(logo: Image.Image, base_width: int, width_percent: float) -> Image.Image:
    """
    ロゴを画像横幅に対するパーセンテージでリサイズ
    width_percent: 0.2 〜 0.4 (20%〜40%)
    """
    target_width = int(base_width * width_percent)
    ratio = target_width / logo.width
    new_h = int(logo.height * ratio)
    return logo.resize((target_width, new_h), Image.Resampling.LANCZOS)


def paste_logo(
    base_img: Image.Image,
    logo: Image.Image,
    position: str,
    margin_percent: float = 0.03,
    custom_x_percent: float | None = None,
    custom_y_percent: float | None = None,
) -> Image.Image:
    """
    ベース画像にロゴを合成
    position: "bottom_right", "bottom_left", "top_right", "top_left", "custom"
    margin_percent: 余白（画像サイズに対する割合、デフォルト3%）
    custom_x_percent, custom_y_percent: position="custom" 時の位置（0〜100、0=左/上、100=右/下）
    """
    base = base_img.copy()
    logo = logo.convert("RGBA")
    bw, bh = base.size
    lw, lh = logo.size
    margin = int(min(bw, bh) * margin_percent)

    if position == "custom" and custom_x_percent is not None and custom_y_percent is not None:
        # 0=左端/上端、100=右端/下端（ロゴの左上座標）
        x = int((bw - lw) * custom_x_percent / 100)
        y = int((bh - lh) * custom_y_percent / 100)
        x = max(0, min(bw - lw, x))
        y = max(0, min(bh - lh, y))
    elif position == "bottom_right":
        x = bw - lw - margin
        y = bh - lh - margin
    elif position == "bottom_left":
        x = margin
        y = bh - lh - margin
    elif position == "top_right":
        x = bw - lw - margin
        y = margin
    else:  # top_left
        x = margin
        y = margin

    base.paste(logo, (x, y), logo)
    return base


def process_image(
    image_source: bytes | Path | Image.Image,
    size_preset: tuple[int, int],
    logo: Image.Image | None = None,
    logo_width_percent: float = 0.25,
    logo_position: str = "bottom_right",
    logo_custom_x: float | None = None,
    logo_custom_y: float | None = None,
) -> Image.Image:
    """
    画像を加工して返す
    image_source: 画像データ（bytes, パス, またはPIL Image）
    """
    if isinstance(image_source, Image.Image):
        img = image_source
    elif isinstance(image_source, bytes):
        img = Image.open(io.BytesIO(image_source)).convert("RGB")
    else:
        img = Image.open(image_source).convert("RGB")

    target_w, target_h = size_preset
    result = center_crop_resize(img, target_w, target_h)

    if logo is not None:
        logo_resized = resize_logo_by_width(logo, target_w, logo_width_percent)
        # 縁取りを追加して背景に溶け込まないようにする（内側に黒、外側に白）
        logo_resized = add_logo_outline(logo_resized, stroke_width=1, stroke_color=(0, 0, 0))
        logo_resized = add_logo_outline(logo_resized, stroke_width=2, stroke_color=(255, 255, 255))
        result = paste_logo(
            result,
            logo_resized,
            logo_position,
            custom_x_percent=logo_custom_x,
            custom_y_percent=logo_custom_y,
        )

    # 縦型（スマホ表示）の場合は明るさ・コントラストを補正
    if target_h > target_w:
        result = enhance_for_mobile(result)

    return result

"""
画像加工ツール - スマホ閲覧向け画像最適化
Pillow + Tkinter ベースのGUIアプリケーション
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageEnhance
from pathlib import Path


BRIGHTNESS_FACTOR = 1.15
CONTRAST_FACTOR = 1.20


def auto_enhance(img: Image.Image) -> Image.Image:
    """明るさ・コントラストを自動補正（スマホ閲覧向け）"""
    img = ImageEnhance.Brightness(img).enhance(BRIGHTNESS_FACTOR)
    img = ImageEnhance.Contrast(img).enhance(CONTRAST_FACTOR)
    return img


def center_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """中央基準でクロップしてからリサイズ"""
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

    return img.resize((target_w, target_h), Image.LANCZOS)


def save_webp(img: Image.Image, path: Path):
    img.save(str(path), "WEBP", quality=85)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("画像加工ツール")
        self.resizable(False, False)

        self.output_dir: Path | None = None

        self._build_header()
        self._build_notebook()
        self._center_window()

    def _build_header(self):
        frame = ttk.LabelFrame(self, text="共通設定", padding=10)
        frame.pack(fill="x", padx=12, pady=(12, 4))

        ttk.Label(frame, text="保存先フォルダ:").grid(row=0, column=0, sticky="w")
        self.dir_var = tk.StringVar(value="（未選択）")
        ttk.Label(frame, textvariable=self.dir_var, width=50).grid(
            row=0, column=1, padx=(6, 6), sticky="w"
        )
        ttk.Button(frame, text="選択…", command=self._pick_dir).grid(row=0, column=2)

    def _pick_dir(self):
        d = filedialog.askdirectory(title="保存先フォルダを選択")
        if d:
            self.output_dir = Path(d)
            self.dir_var.set(str(self.output_dir))

    def _build_notebook(self):
        nb = ttk.Notebook(self, padding=6)
        nb.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        nb.add(ThumbTab(nb, self), text=" ツール1: 3枚サムネイル ")
        nb.add(VerticalTab(nb, self), text=" ツール2: 縦長加工 ")
        nb.add(SquareTab(nb, self), text=" ツール3: 正方形加工 ")

    def _center_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    def get_output_dir(self) -> Path | None:
        if self.output_dir is None:
            messagebox.showwarning("未設定", "先に保存先フォルダを選択してください。")
            return None
        return self.output_dir


IMAGE_FILETYPES = [
    ("画像ファイル", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
    ("すべてのファイル", "*.*"),
]


class ThumbTab(ttk.Frame):
    """ツール1: 3枚写真合体加工 → 384×128 サムネイル"""

    def __init__(self, parent, app: App):
        super().__init__(parent, padding=14)
        self.app = app
        self.paths: list[str] = ["", "", ""]

        ttk.Label(self, text="店名:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.name_var, width=30).grid(
            row=0, column=1, columnspan=2, sticky="w", pady=4
        )

        for i in range(3):
            r = i + 1
            ttk.Label(self, text=f"画像{r}:").grid(row=r, column=0, sticky="w")
            var = tk.StringVar(value="（未選択）")
            setattr(self, f"lbl{i}", var)
            ttk.Label(self, textvariable=var, width=44).grid(
                row=r, column=1, sticky="w", padx=4
            )
            ttk.Button(
                self, text="選択…", command=lambda idx=i: self._pick(idx)
            ).grid(row=r, column=2)

        ttk.Button(self, text="実行", command=self._run).grid(
            row=4, column=0, columnspan=3, pady=(12, 0)
        )

    def _pick(self, idx: int):
        p = filedialog.askopenfilename(filetypes=IMAGE_FILETYPES)
        if p:
            self.paths[idx] = p
            getattr(self, f"lbl{idx}").set(Path(p).name)

    def _run(self):
        out = self.app.get_output_dir()
        if out is None:
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("入力エラー", "店名を入力してください。")
            return
        if any(p == "" for p in self.paths):
            messagebox.showwarning("入力エラー", "画像を3枚すべて選択してください。")
            return

        tiles: list[Image.Image] = []
        for p in self.paths:
            img = Image.open(p).convert("RGB")
            img = auto_enhance(img)
            img = center_crop(img, 128, 128)
            tiles.append(img)

        combined = Image.new("RGB", (384, 128))
        for i, tile in enumerate(tiles):
            combined.paste(tile, (128 * i, 0))

        dest = out / f"{name}_thumb.webp"
        save_webp(combined, dest)
        messagebox.showinfo("完了", f"保存しました:\n{dest}")


class VerticalTab(ttk.Frame):
    """ツール2: 縦長加工 → 540×720"""

    KEYWORDS = ["commitment", "interior", "menu", "mosquedetail"]

    def __init__(self, parent, app: App):
        super().__init__(parent, padding=14)
        self.app = app
        self.path = ""

        ttk.Label(self, text="店名:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.name_var, width=30).grid(
            row=0, column=1, columnspan=2, sticky="w", pady=4
        )

        ttk.Label(self, text="種類:").grid(row=1, column=0, sticky="w")
        self.kw_var = tk.StringVar(value=self.KEYWORDS[0])
        ttk.Combobox(
            self,
            textvariable=self.kw_var,
            values=self.KEYWORDS,
            state="readonly",
            width=20,
        ).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(self, text="画像:").grid(row=2, column=0, sticky="w")
        self.file_var = tk.StringVar(value="（未選択）")
        ttk.Label(self, textvariable=self.file_var, width=44).grid(
            row=2, column=1, sticky="w", padx=4
        )
        ttk.Button(self, text="選択…", command=self._pick).grid(row=2, column=2)

        ttk.Button(self, text="実行", command=self._run).grid(
            row=3, column=0, columnspan=3, pady=(12, 0)
        )

    def _pick(self):
        p = filedialog.askopenfilename(filetypes=IMAGE_FILETYPES)
        if p:
            self.path = p
            self.file_var.set(Path(p).name)

    def _run(self):
        out = self.app.get_output_dir()
        if out is None:
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("入力エラー", "店名を入力してください。")
            return
        if not self.path:
            messagebox.showwarning("入力エラー", "画像を選択してください。")
            return

        img = Image.open(self.path).convert("RGB")
        img = auto_enhance(img)
        img = center_crop(img, 540, 720)

        kw = self.kw_var.get()
        dest = out / f"{name}_{kw}.webp"
        save_webp(img, dest)
        messagebox.showinfo("完了", f"保存しました:\n{dest}")


class SquareTab(ttk.Frame):
    """ツール3: 正方形加工 → 480×480"""

    def __init__(self, parent, app: App):
        super().__init__(parent, padding=14)
        self.app = app
        self.path = ""

        ttk.Label(self, text="店名:").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.name_var, width=30).grid(
            row=0, column=1, columnspan=2, sticky="w", pady=4
        )

        ttk.Label(self, text="画像:").grid(row=1, column=0, sticky="w")
        self.file_var = tk.StringVar(value="（未選択）")
        ttk.Label(self, textvariable=self.file_var, width=44).grid(
            row=1, column=1, sticky="w", padx=4
        )
        ttk.Button(self, text="選択…", command=self._pick).grid(row=1, column=2)

        ttk.Button(self, text="実行", command=self._run).grid(
            row=2, column=0, columnspan=3, pady=(12, 0)
        )

    def _pick(self):
        p = filedialog.askopenfilename(filetypes=IMAGE_FILETYPES)
        if p:
            self.path = p
            self.file_var.set(Path(p).name)

    def _run(self):
        out = self.app.get_output_dir()
        if out is None:
            return
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("入力エラー", "店名を入力してください。")
            return
        if not self.path:
            messagebox.showwarning("入力エラー", "画像を選択してください。")
            return

        img = Image.open(self.path).convert("RGB")
        img = auto_enhance(img)
        img = center_crop(img, 480, 480)

        dest = out / f"{name}_top.webp"
        save_webp(img, dest)
        messagebox.showinfo("完了", f"保存しました:\n{dest}")


if __name__ == "__main__":
    app = App()
    app.mainloop()

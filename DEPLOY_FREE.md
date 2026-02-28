# 完全無料で公開する方法（クレジットカード不要）

以下のサービスは**無料**で利用でき、**クレジットカード登録不要**です。

---

## 方法A: Render（使い慣れている方におすすめ）

**無料・クレジットカード不要・GitHub連携が簡単**

> 15分間アクセスがないとスリープします。次回アクセス時に30秒〜1分ほど起動時間がかかります。

### 手順

1. **[render.com](https://render.com)** にアクセスし、GitHub でログイン

2. **「New」** → **「Web Service」** をクリック

3. **「Connect a repository」** で `image_tool` を選択

4. 設定
   - **Name:** `image_tool`（任意）
   - **Region:** Singapore または Oregon
   - **Branch:** `main`
   - **Runtime:** **Docker** を選択（Dockerfile を自動検出）
   - **Instance type:** **Free** を選択

5. **「Create Web Service」** をクリック

6. ビルドが完了すると公開URLが発行されます  
   - URL例: `https://image-tool-xxxx.onrender.com`

---

## 方法B: Hugging Face Spaces

**完全無料・クレジットカード不要・ずっと使える**

### 手順

1. **[huggingface.co](https://huggingface.co)** でアカウント作成（無料）

2. **[huggingface.co/spaces](https://huggingface.co/spaces)** を開く

3. **「Create new Space」** をクリック

4. 設定
   - **Space name:** `image_tool`（任意）
   - **License:** 任意
   - **SDK:** **Docker** を選択（重要）
   - **Space hardware:** 無料のまま（CPU basic）

5. **「Create Space」** をクリック

6. 作成後、以下のファイルをアップロード
   - `app.py`
   - `extract_cli.py`
   - `photo_extractor.py`
   - `image_processor.py`
   - `requirements.txt`
   - `Dockerfile`

   **アップロード方法:** 「Add file」→「Upload files」でまとめてアップロード

7. 数分待つとビルドが完了し、公開URLが発行されます  
   - URL例: `https://あなたのユーザー名-image-tool.hf.space`

---

## 方法C: Streamlit Community Cloud

**完全無料・クレジットカード不要**

> ⚠️ Playwright（写真抽出）はメモリ制限で動かない場合があります。  
> 写真抽出が使えない場合は、**画像を手動アップロード**する機能を別途追加する必要があります。

### 手順

1. **[share.streamlit.io](https://share.streamlit.io)** にアクセス

2. GitHub でログイン

3. **「New app」** をクリック

4. 設定
   - **Repository:** `coenavicooperate-sys/image_tool`
   - **Branch:** `main`
   - **Main file path:** `app.py`

5. **「Advanced settings」** を開く
   - Python version: `3.11`
   - **Use Dockerfile:** オンにする（Dockerfile がある場合）

6. **「Deploy」** をクリック

7. ビルド完了後、公開URLが発行されます

---

## ログイン認証の設定（全プラットフォーム共通）

関係者以外のアクセスを防ぐため、ID/パスワード認証を設定できます。

### 環境変数の設定

| 変数名 | 説明 |
|--------|------|
| `IMAGE_TOOL_USERNAME` | ログインID |
| `IMAGE_TOOL_PASSWORD` | パスワード |

**未設定の場合:** 認証はスキップされ、誰でもアクセスできます（開発用）。

### 各プラットフォームでの設定方法

- **Render:** サービス → Environment → Add Environment Variable
- **Hugging Face:** Space → Settings → Repository secrets（または Variables）
- **Streamlit Cloud:** アプリ設定 → Secrets

---

## 比較

| サービス | 料金 | クレジットカード | 写真抽出 | スリープ |
|----------|------|------------------|----------|----------|
| **Render** | 無料 | 不要 | ✅ | 15分でスリープ |
| **Hugging Face Spaces** | 無料 | 不要 | ✅ | なし |
| **Streamlit Cloud** | 無料 | 不要 | ⚠️ メモリ不足の可能性 | なし |
| Railway | トライアル後有料 | 必要 | ✅ | なし |

**結論:**  
- **Render** … 使い慣れているなら手軽。スリープはあるが無料で使える  
- **Hugging Face Spaces** … スリープなしで常時稼働させたい場合

# 店舗写真 抽出・選択・一括加工 Webアプリ

ホットペッパー / 食べログのURLから写真を自動取得し、SNS用サイズに加工してZIPで一括ダウンロードできるStreamlitアプリです。

## 機能

- **STEP 1:** Playwrightで写真一覧ページから全画像をスクロール取得（高画質URLに変換）
- **STEP 2:** サイドバーで加工設定（サイズ・ロゴ・位置）
- **STEP 3:** Pillowで中央クロップ＆リサイズ、ロゴ合成
- **STEP 4:** プレビュー表示＆ZIP一括ダウンロード

## ローカル実行

```bash
pip install -r requirements.txt
playwright install chromium
streamlit run app.py
```

### 同じネットワーク内の他の端末からアクセスする場合

```bash
streamlit run app.py --server.address=0.0.0.0
```

起動後、同じWi-Fi内のスマホやタブレットから `http://あなたのPCのIP:8501` でアクセスできます。

---

## クラウド公開（誰でもWebで使えるようにする）

### 方法1: Streamlit Community Cloud（無料・簡単）

1. **GitHub にリポジトリを作成**
   - このフォルダの内容をプッシュ

2. **[share.streamlit.io](https://share.streamlit.io)** にアクセス
   - GitHub でログイン
   - 「New app」→ リポジトリ・ブランチ・`app.py` を指定

3. **Advanced settings** で以下を設定
   - Python version: `3.11`
   - ビルドコマンド（空のまま）
   - **重要:** 「Use Dockerfile」を有効化（リポジトリに Dockerfile がある場合）

4. **Deploy** をクリック  
   - 初回ビルドに 5〜10 分かかることがあります

> **注意:** Streamlit Cloud の無料枠では、Dockerfile を使うとメモリ制限（1GB）に引っかかる場合があります。その場合は方法2を検討してください。

---

### 方法2: Railway（推奨・無料枠あり）

1. **[railway.app](https://railway.app)** でアカウント作成

2. 「New Project」→「Deploy from GitHub repo」
   - リポジトリを選択

3. Railway が自動で Dockerfile を検出してビルド

4. 「Settings」→「Networking」→「Generate Domain」で公開URLを取得

5. 無料枠: 月 $5 分のクレジット（個人利用なら十分なことが多い）

---

### 方法3: Render

1. **[render.com](https://render.com)** でアカウント作成

2. 「New」→「Web Service」
   - GitHub リポジトリを接続

3. 設定
   - **Build Command:** （空欄でOK、Dockerfile を使用）
   - **Start Command:** `streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT`
   - または Docker を有効にして Dockerfile でビルド

4. 無料枠: スリープあり（アクセス時に起動に数十秒かかります）

---

### 方法4: Hugging Face Spaces

1. **[huggingface.co/spaces](https://huggingface.co/spaces)** でログイン

2. 「Create new Space」
   - SDK: **Docker**
   - リポジトリ名を入力

3. 作成後、ファイルをアップロード
   - `Dockerfile`, `app.py`, `photo_extractor.py`, `image_processor.py`, `extract_cli.py`, `requirements.txt`

4. 無料で公開可能

---

## デプロイ前のチェックリスト

- [ ] `app.py`, `photo_extractor.py`, `image_processor.py`, `extract_cli.py`, `requirements.txt` をリポジトリに含める
- [ ] `Dockerfile` をリポジトリのルートに配置
- [ ] GitHub にプッシュ済み

## ファイル構成

```
image_tool/
├── app.py
├── extract_cli.py
├── photo_extractor.py
├── image_processor.py
├── requirements.txt
├── Dockerfile
├── .streamlit/
│   └── config.toml
└── README.md
```

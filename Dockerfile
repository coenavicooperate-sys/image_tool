# Playwright + Python 公式イメージ（Chromium 同梱）
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# 依存関係
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体
COPY app.py extract_cli.py photo_extractor.py image_processor.py ./

EXPOSE 8501

# PORT 環境変数があれば使用（Railway/Render 対応）
CMD ["sh", "-c", "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8501}"]

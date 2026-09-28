# SkillSprint AI API
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf \
    TOKENIZERS_PARALLELISM=false

WORKDIR /app

# CPU-only PyTorch keeps the image small; sentence-transformers needs nothing more.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the embedding model into the image, so a cold start never downloads it
# (that download alone would break the 30-second budget).
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
# From here on the model is local; never reach out to the hub at runtime.
ENV HF_HUB_OFFLINE=1

COPY . .
RUN chmod +x docker/entrypoint.sh && mkdir -p uploads docs

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/health', timeout=4)"

ENTRYPOINT ["docker/entrypoint.sh"]

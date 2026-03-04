FROM ghcr.io/astral-sh/uv:0.6-python3.11-bookworm-slim
WORKDIR /app
COPY services/api/requirements.txt /app/requirements.txt
RUN uv pip install --system -r /app/requirements.txt
COPY services/api/main.py /app/main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

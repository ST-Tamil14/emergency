FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libatomic1 \
    libgl1 \
    libglu1-mesa \
    libgomp1 \
    libx11-6 \
    libxerces-c3.2 \
    libfox-1.6-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements*.txt ./

RUN pip install --no-cache-dir -r requirements-lock.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
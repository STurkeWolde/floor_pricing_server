FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Copy ONLY requirements (they are directly inside context root)
COPY requirements.txt ./requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

# Copy backend sources into a top-level `app` package location
COPY . /src/app/backend

CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

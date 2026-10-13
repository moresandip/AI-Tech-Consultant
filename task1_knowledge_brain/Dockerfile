FROM python:3.12-slim

WORKDIR /app

# System deps for lxml, Pillow
RUN apt-get update && apt-get install -y \
    libxml2-dev libxslt-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY . .

EXPOSE 8001 8501

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libfreetype6-dev \
    libportmidi-dev \
    libjpeg-dev \
    libpng-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -e ".[dev,gui]" \
 && pip install --no-cache-dir torch matplotlib seaborn pandas

COPY . .

RUN mkdir -p reports experiments

CMD ["pytest", "--tb=short", "-q"]

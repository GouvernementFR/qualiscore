FROM python:3.14-slim

ENV NODE_VERSION=24

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gnupg \
    ca-certificates \
    zlib1g-dev \
    libjpeg-dev \
    libtiff-dev \
    libopenjp2-7-dev \
    libwebp-dev \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libx11-xcb1 \
    libxrender1 \
    libxrandr2 \
    libxt6 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgdk-pixbuf-2.0-0 \
    libxdamage1 \
    libxss1 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libnss3 \
    libxcomposite1 \
    libxfixes3 \
    libxcb1 \
    libxkbcommon0 \
    libwayland-client0 \
    libwayland-cursor0 \
    libwayland-egl1 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sL https://deb.nodesource.com/setup_$NODE_VERSION.x | bash - \
    && apt-get update && apt-get install -y nodejs

COPY pyproject.toml requirements.txt package.json ./

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir . \
    && python -m pip cache purge

RUN npm install \
    && npm cache clean --force

RUN playwright install --with-deps chromium \
    && camoufox fetch

COPY . .

ENTRYPOINT ["python", "main.py"]

FROM mcr.microsoft.com/playwright/python:v1.59.0

ENV NODE_VERSION=24
ENV UV_PYTHON=3.14
ENV PATH="/root/.local/bin:/app/.venv/bin:$PATH"

WORKDIR /app

RUN curl -sL https://deb.nodesource.com/setup_$NODE_VERSION.x | bash - \
    && apt-get update && apt-get install -y nodejs \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml uv.lock package.json ./

RUN uv sync --frozen --no-dev --no-install-project

RUN camoufox fetch

RUN npm install \
    && npm cache clean --force

COPY . .

RUN uv sync --frozen --no-dev

RUN adduser --system --no-create-home qualiscore
USER qualiscore

ENTRYPOINT ["python", "main.py"]

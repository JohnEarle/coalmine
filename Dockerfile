FROM python:3.11-slim AS python-base

# Install system dependencies and OpenTofu
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install OpenTofu
# Instructions derived from https://opentofu.org/docs/intro/install/
RUN curl --proto '=https' --tlsv1.2 -fsSL https://get.opentofu.org/install-opentofu.sh -o install-opentofu.sh && \
    chmod +x install-opentofu.sh && \
    ./install-opentofu.sh --install-method deb && \
    rm install-opentofu.sh

# =============================================================================
# Stage 2: Build WebUI
# =============================================================================
FROM node:20-slim AS webui-builder

WORKDIR /webui

# Copy package files first for layer caching
COPY webui/package*.json ./

# Install dependencies
RUN npm ci --ignore-scripts

# Copy source and build
COPY webui/ ./
RUN npm run build

# =============================================================================
# Stage 3: Final Image
# =============================================================================
FROM python-base AS final

WORKDIR /app

# Copy and install Python package
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install in editable mode with dev dependencies
RUN pip install --no-cache-dir -e ".[dev]"

# Copy WebUI build output (completely segmented - can be omitted for API-only image)
COPY --from=webui-builder /webui/dist ./webui/dist

# Copy remaining application files
COPY config/ ./config/
COPY tofu_templates/ ./tofu_templates/
COPY entrypoint.sh ./

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Set standard entrypoint for DB init
ENTRYPOINT ["./entrypoint.sh"]

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "src.main"]

FROM python:3.11-slim

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

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set standard entrypoint for DB init
ENTRYPOINT ["./entrypoint.sh"]

# Default command (can be overridden in docker-compose)
CMD ["python", "-m", "src.main"]

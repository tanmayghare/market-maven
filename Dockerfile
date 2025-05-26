# Multi-stage build for production-ready MarketMaven
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION=1.0.0

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set metadata
LABEL maintainer="MarketMaven Team" \
      version="${VERSION}" \
      description="Production-grade AI market intelligence agent" \
      build-date="${BUILD_DATE}"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    ENVIRONMENT=production

# Create non-root user
RUN groupadd -r marketmaven && useradd -r -g marketmaven marketmaven

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY market_maven/ ./market_maven/
COPY pyproject.toml ./

# Create necessary directories
RUN mkdir -p logs data && \
    chown -R marketmaven:marketmaven /app

# Switch to non-root user
USER marketmaven

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import market_maven; print('Health check passed')" || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "-m", "market_maven.cli", "health"] 
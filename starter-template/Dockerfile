# =============================================================================
# Lozzalingo Starter Template - Dockerfile
# =============================================================================
# Build: docker build -t mysite .
# Run:   docker run -p 5000:5000 mysite

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy lozzalingo framework (if building with local framework)
# Comment this out if using published package
COPY --from=lozzalingo /lozzalingo /lozzalingo
RUN pip install -e /lozzalingo || true

# Copy application code
COPY . .

# Create databases directory
RUN mkdir -p databases

# Expose port
EXPOSE 5000

# Health check using Python stdlib (no curl needed)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')"

# Run with gunicorn in production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]

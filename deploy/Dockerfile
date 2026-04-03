# Multi-stage build for smaller image
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies and Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.12-slim

# Build arguments for versioning
ARG BUILD_VERSION=dev
ENV BUILD_VERSION=${BUILD_VERSION}

# Create non-root user for security
RUN groupadd -r nonroot && useradd -r -g nonroot -m nonroot

# Set working directory
WORKDIR /app

# Copy Python packages from builder (installed in /usr/local)
COPY --from=builder /usr/local /usr/local

# Copy application code
COPY . .

# Create logs directory with proper permissions
RUN mkdir -p logs && chown -R nonroot:nonroot /app

# Switch to non-root user
USER nonroot

# Declare volume for persistent logs
VOLUME ["/app/logs"]

# Expose port
EXPOSE 5001

# Health check using Python (no curl needed)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5001/health')" || exit 1

# Run with Gunicorn (production WSGI server)
# --timeout 60: Increased from default 30s due to resource limits (0.5 CPU, 512MB RAM)
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

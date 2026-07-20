# Multi-stage Dockerfile for Flask + nginx

# Stage 1: Build Python dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY reports/requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt


# Stage 2: Runtime with nginx + Python
FROM python:3.11-slim

# Install nginx и supervisord
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Set working directory
WORKDIR /app

# Copy application files
COPY reports/app.py /app/app.py
COPY pyrus_export.py /app/
COPY process_quality_data_full.py /app/
COPY scripts/export_retailcrm.py /app/scripts/export_retailcrm.py
COPY scripts/export_retailcrm_sales.py /app/scripts/export_retailcrm_sales.py
COPY scripts/test_sales_analytics.py /app/scripts/test_sales_analytics.py
COPY data/ /app/data/
COPY index.html /usr/share/nginx/html/index.html
COPY sales-analytics.html /usr/share/nginx/html/sales-analytics.html
COPY quality-report-14-18.html /usr/share/nginx/html/quality-report-14-18.html
COPY brand/tokens.css /usr/share/nginx/html/brand/tokens.css
COPY brand/brand.css /usr/share/nginx/html/brand/brand.css
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/app.conf

# Create logs directory
RUN mkdir -p /var/log/supervisor

# Add RetailCRM to /etc/hosts to bypass DNS issues in container
RUN echo "93.77.160.100 barhatretailcrm.retailcrm.ru" >> /etc/hosts

# Expose port
EXPOSE 80

# Start supervisord
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/app.conf"]

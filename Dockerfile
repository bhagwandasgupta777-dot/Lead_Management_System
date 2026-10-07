FROM python:3.13-slim

# Prevent Python from creating .pyc files
ENV PYTHONDONTWRITEBYTECODE=1

# Show Python output immediately
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system packages required by mysqlclient
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        default-libmysqlclient-dev \
        build-essential \
        pkg-config \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*



# Copy requirements first for better Docker caching
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Django project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Railway provides the PORT environment variable
EXPOSE 8080

# Start Django using Gunicorn
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080}"]
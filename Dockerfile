# Mandom — headless container image (for sharing / self-hosting).
# Note: Send-to-Kobo (USB detection) and the OS keychain are not available in a
# container; secrets fall back to a file under /app/data (MANDOM_SECRET_BACKEND=file).
FROM python:3.13-slim

WORKDIR /app

# Install deps first for better layer caching.
COPY pyproject.toml README.md ./
COPY app ./app
COPY run.py ./
RUN pip install --no-cache-dir -e ".[web]" \
    && mkdir -p data downloads wallpapers

# Headless: no browser, file-based secret store, listen on all interfaces.
ENV MANDOM_SECRET_BACKEND=file
EXPOSE 8000

CMD ["python", "run.py", "--host", "0.0.0.0", "--no-browser"]

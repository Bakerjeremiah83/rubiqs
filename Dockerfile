# Use official slim Python image
FROM python:3.11-slim

# Set working directory to the project root
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full app (including app/, templates/, static/, etc.)
COPY . .

# Set environment variables
ENV FLASK_APP=app/main.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Run the app using gunicorn from the app.main module
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app.main:app"]

# For the background worker, specify it in Render settings when creating a worker
# (Do not include ENTRYPOINT here unless using it directly in Docker, which is not recommended for workers)

# Use official slim Python image
FROM python:3.11-slim

# Set working directory to the project root
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy everything into /app
COPY . .

# Set environment variables for Flask
ENV FLASK_APP=app/main.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Use Gunicorn to serve the app from app/main.py
CMD ["gunicorn", "app.main:app"]

FROM python:3.11-slim

WORKDIR /app

# Only copy requirements.txt — source code is mounted via volume
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# No need to copy app/, templates/, etc. — mounted live from host

CMD ["python", "app/main.py"]

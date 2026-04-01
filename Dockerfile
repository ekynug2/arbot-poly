FROM python:3.11-slim

WORKDIR /app

# Install dependencies required for py-clob-client
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -v -r requirements.txt

COPY . .

# Default command to run the bot in paper trading mode
CMD ["python", "main.py"]

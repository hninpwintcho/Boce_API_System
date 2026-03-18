# 🐍 Production Dockerfile for Boce Unified Proxy
FROM python:3.11-slim

# 🛡️ 1. Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=3000

# 📁 2. Set working directory
WORKDIR /app

# ⚙️ 3. Install system dependencies (SQLite)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 📦 4. Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 📂 5. Copy project files
COPY . .

# 🚢 6. Expose the API port
EXPOSE 3000

# 🚀 7. Launch the app with Uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]

# Lab 9 — Dockerfile for the Onboarding Agent
# Base image: Python 3.11 slim for minimal footprint
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Layer 1: Install dependencies (cached if requirements.txt unchanged)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer 2: Copy application code
COPY . .

# Expose the FastAPI port
EXPOSE 8000

# Environment variables (override at runtime)
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Launch the FastAPI server
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]

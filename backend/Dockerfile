FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
# Shell form so Render's injected PORT is honored; 8000 remains the local default.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}


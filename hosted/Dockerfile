FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    asyncpg \
    bcrypt \
    python-multipart \
    jinja2 \
    itsdangerous

# Copy application
COPY . .

# Run
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

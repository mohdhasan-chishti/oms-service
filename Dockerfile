FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /application

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /application/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY application /application

# Make the entrypoint script executable
RUN ["chmod", "+x", "/application/docker-entrypoint.sh"]

ENTRYPOINT ["bash", "/application/docker-entrypoint.sh"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

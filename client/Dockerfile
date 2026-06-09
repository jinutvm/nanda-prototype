FROM python:3.12-alpine

WORKDIR /app
COPY requirements.txt .
RUN apk add --no-cache gcc musl-dev libffi-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apk del gcc musl-dev libffi-dev

COPY shared/ ./shared/
COPY client/ ./client/

ENTRYPOINT ["python", "-m", "client.resolve"]

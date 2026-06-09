FROM python:3.12-alpine

WORKDIR /app
COPY requirements.txt .
RUN apk add --no-cache gcc musl-dev libffi-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apk del gcc musl-dev libffi-dev

COPY shared/ ./shared/
COPY index_server/ ./index_server/

EXPOSE 5001
CMD ["uvicorn", "index_server.app:app", "--host", "0.0.0.0", "--port", "5001"]

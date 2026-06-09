FROM python:3.12-alpine

WORKDIR /app
COPY requirements.txt .
RUN apk add --no-cache gcc musl-dev libffi-dev && \
    pip install --no-cache-dir -r requirements.txt && \
    apk del gcc musl-dev libffi-dev

COPY shared/ ./shared/
COPY agent_facts_server/ ./agent_facts_server/

EXPOSE 5002
CMD ["uvicorn", "agent_facts_server.app:app", "--host", "0.0.0.0", "--port", "5002"]

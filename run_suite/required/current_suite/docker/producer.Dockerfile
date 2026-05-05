FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir redis==5.2.1
COPY docker/producer.py /app/producer.py
CMD ["python3", "/app/producer.py"]

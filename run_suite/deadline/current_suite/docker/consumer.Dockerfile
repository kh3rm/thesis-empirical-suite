FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir redis==5.2.1
COPY docker/consumer.py /app/consumer.py
CMD ["python3", "/app/consumer.py"]

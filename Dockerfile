FROM python:3.12-slim

WORKDIR /app

COPY . /app

# Install ffmpeg and other dependencies
RUN apt-get update && apt-get install -y ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir setuptools \
    && pip install --no-cache-dir .


RUN mkdir -p /app/data

EXPOSE 5728

CMD ["bilipod", "--config=/app/config.yaml", "--db=/app/data.db"]
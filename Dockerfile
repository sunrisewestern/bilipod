FROM python:3.12.10-slim

WORKDIR /app

# Install ffmpeg and other dependencies
RUN apt-get update && apt-get install -y ffmpeg git\
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir setuptools \
    && pip install --no-cache-dir .

RUN apt remove -y git

RUN mkdir -p /app/data
RUN mkdir -p /app/db

EXPOSE 5728
EXPOSE 41942
EXPOSE 41943
EXPOSE 41944

CMD ["bilipod", "--config=/app/config.yaml", "--db=/app/db/data.db"]

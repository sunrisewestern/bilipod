# bilipod: Turn Bilibili Users into Podcast Feeds

**Easily convert Bilibili user uploads into podcast feeds**

[![GitHub release](https://img.shields.io/github/v/release/sunrisewestern/bilipod)](https://github.com/sunrisewestern/bilipod/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## Features

- **Generates podcast feeds** from Bilibili user uploads.
- **Flexible configuration:**
    - Choose video or audio-only feeds.
    - Select high or low quality output.
    - Filter episodes by keywords.
    - Customize feed metadata (artwork, category, language, etc.).
- **OPML export** for easy importing into podcast apps.
- **Episode cleanup** to keep your feed tidy (keep last X episodes).
- **Docker support** for simplified deployment (under development).
- **Endorse the uploader** (like, coins, favorite; 点赞|投币|收藏|三连)

## Getting Started

### Prerequisites

- **Python 3.7+**
- **Bilibili account** (and cookies - see below)

### Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sunrisewestern/bilipod.git
   cd bilipod
   ```

2. **Create a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install .
   ```

4. **Obtain your Bilibili cookies:**
   - Follow the instructions in the [bilibili-api documentation](https://nemo2011.github.io/bilibili-api/#/get-credential).

5. **Configure `config.yaml`:**
   - Provide your Bilibili cookies.
   - Customize feed settings (output format, quality, filters, etc.).

6. **Create your podcast feed:**
   ```bash
   bilipod --config config.yaml --db data.db
   ```

7. **Subscribe to the generated feed URL** in any podcast app

## Docker

 The Docker image is available on Docker Hub under `sunrisewestern/bilipod`.

### Running the Docker Container

1. **Prepare Configuration and Data Directories**:
   Ensure you have your `config.yaml` file ready and create a directory for the database if it doesn't exist:

   ```bash
   mkdir -p data
   ```

2. **Run the Docker Container**:
   Use the following command to run the Docker container, mounting the configuration file and data directory:

   ```bash
   docker run -d \
       --name bilipod \
       -v $(pwd)/config.yaml:/app/config.yaml \
       -v $(pwd)/data:/app/data \
       -p 5728:5728 \
       sunrisewestern/bilipod:latest
   ```

### Using Docker Compose

 Create a `docker-compose.yml` file with the following content:

```yaml
version: '3.8'

services:
  bilipod:
    image: sunrisewestern/bilipod:latest
    container_name: bilipod
    volumes:
      - ./config.yaml:/app/config.yaml
      - ./data:/app/data
    ports:
      - "5728:5728"
```

1. **Run with Docker Compose**:
   Run the following commands to start the application using Docker Compose:

   ```bash
   docker-compose up -d
   ```

   This command starts the container in detached mode.

2. **Stopping the Docker Compose Services**:
   To stop the services, run:

   ```bash
   docker-compose down
   ```


## Documentation

- **Configuration:** Detailed instructions in `config_example.yaml`
- **Bilibili Cookies:** [https://nemo2011.github.io/bilibili-api/#/get-credential](https://nemo2011.github.io/bilibili-api/#/get-credential)

## Acknowledgements

- Inspired by [podsync](https://github.com/mxpv/podsync)
- Utilizes the [bilibili-api](https://github.com/Nemo2011/bilibili-api) library.
- Feed generation powered by [python-feedgen](https://github.com/lkiesow/python-feedgen).

## License

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0).

# bilipod: Turn Bilibili Users into Podcast Feeds

**Easily convert Bilibili user uploads into podcast feeds you can listen to anywhere!**

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
- **Docker support** for simplified deployment (coming soon!).

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
   pip install -r requirements.txt
   ```

4. **Obtain your Bilibili cookies:**
   - Follow the instructions in the [bilibili-api documentation](https://nemo2011.github.io/bilibili-api/#/get-credential).

5. **Configure `config.yaml`:**
   - Provide your Bilibili cookies.
   - Customize feed settings (output format, quality, filters, etc.).

6. **Create your podcast feed:**
   ```bash
   python ./src/bilipod/main.py --config config.yaml --db data.db
   ```

7. **Subscribe to the generated feed URL** in your favorite podcast app!

## Docker

Docker support is currently under development.

## Documentation

- **Configuration:** Detailed instructions in `config_example.yaml`
- **Bilibili Cookies:** [https://nemo2011.github.io/bilibili-api/#/get-credential](https://nemo2011.github.io/bilibili-api/#/get-credential)

## Acknowledgements

- Inspired by [podsync](https://github.com/mxpv/podsync)
- Utilizes the [bilibili-api](https://github.com/Nemo2011/bilibili-api) library.
- Feed generation powered by [python-feedgen](https://github.com/lkiesow/python-feedgen).

## License

This project is licensed under the [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0).

# Bilipod：将 [Bilibili](https://www.bilibili.com/) 用户上传内容或播放列表转换为播客订阅源

[English](./README.md) / 简体中文

<p align="center">
  <img src="assets/icon.png" alt="Bilipod App Icon" width="128"/>
</p>

**轻松将 Bilibili 用户上传内容转换为播客订阅源**

[![GitHub release](https://img.shields.io/github/v/release/sunrisewestern/bilipod)](https://github.com/sunrisewestern/bilipod/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

## 功能

- **生成播客订阅源** 从 Bilibili 用户上传内容或播放列表生成播客订阅源。
- **灵活配置：**
  - 选择视频或仅音频订阅源。
  - 选择高质量或低质量输出。
  - 通过关键词过滤剧集。
  - 自定义订阅源元数据（封面、类别、语言等）。
- **OPML 导出** 便于导入到播客应用中。
- **剧集清理** 保持订阅源整洁（保留最近 X 个剧集）。
- **Docker 支持** 简化部署。
- **支持上传者**（点赞|投币|收藏|三连）

## 快速开始

### 前提条件

- **Python 3.8+**
- **Bilibili 账号**（和 cookies - 见下文）

### 安装和使用

1. **克隆仓库：**

   ```bash
   git clone https://github.com/sunrisewestern/bilipod.git
   cd bilipod
   ```

2. **创建虚拟环境（推荐）：**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **安装依赖：**

   ```bash
   pip install .
   ```

4. **获取你的 Bilibili cookies：**

   - 按照[bilibili-api 文档](https://nemo2011.github.io/bilibili-api/#/get-credential)中的说明操作。

5. **配置 `config.yaml`：**

   - 提供你的 Bilibili cookies。
   - 自定义订阅源设置（输出格式、质量、过滤器等）。

6. **创建你的播客订阅源：**

   ```bash
   bilipod --config config.yaml --db data.db
   ```

7. **在任何播客应用中订阅生成的订阅源 URL**

## Docker

Docker 镜像可在 Docker Hub 上找到，名称为 `sunrisewestern/bilipod`。

### 运行 Docker 容器

1. **准备配置和数据目录**：
   确保你已经准备好 `config.yaml` 文件，并创建一个数据库目录（如果不存在）：

   ```bash
   mkdir -p data
   ```

2. **运行 Docker 容器**：
   使用以下命令运行 Docker 容器，挂载配置文件和数据目录：

   ```bash
   docker run -d \
       --name bilipod \
       -v $(pwd)/config.yaml:/app/config.yaml \
       -v $(pwd)/data:/app/data \
       -p 5728:5728 \
       sunrisewestern/bilipod:latest
   ```

### 使用 Docker Compose

创建一个 `docker-compose.yml` 文件，内容如下：

```yaml
version: "3.8"

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

1. **使用 Docker Compose 运行**：
   使用以下命令启动应用：

   ```bash
   docker-compose up -d
   ```

   该命令以分离模式启动容器。

2. **停止 Docker Compose 服务**：
   使用以下命令停止服务：

   ```bash
   docker-compose down
   ```

## 文档

- **配置：** 在 `config_example.yaml` 中有详细说明
- **Bilibili Cookies：** [https://nemo2011.github.io/bilibili-api/#/get-credential](https://nemo2011.github.io/bilibili-api/#/get-credential)

## 致谢

- 灵感来自 [podsync](https://github.com/mxpv/podsync)
- 使用了 [bilibili-api](https://github.com/Nemo2011/bilibili-api) 库。
- 订阅源生成由 [python-feedgen](https://github.com/lkiesow/python-feedgen) 提供支持。

## 许可证

本项目采用 [GNU 通用公共许可证 v3.0](https://www.gnu.org/licenses/gpl-3.0) 许可。

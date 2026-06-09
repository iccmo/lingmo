# 灵墨部署指南

## 前置条件

### macOS

安装 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)

### Windows

安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)。安装后可能需要重启。

---

## 部署步骤

### 1. 导入镜像

```bash
docker load -i lingmo-app-版本号.tar
```

### 2. 配置

```bash
cp .env.example .env
```

用记事本打开 `.env`，填入 DeepSeek API Key：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 3. 启动

```bash
docker compose up -d
```

### 4. 访问

浏览器打开 `http://localhost:8000`

---

## 管理

| 操作 | 命令 |
|------|------|
| 启动 | `docker compose up -d` |
| 停止 | `docker compose stop` |
| 重启 | `docker compose restart` |
| 备份数据 | 复制 `./data/` 目录 |

## 数据

所有小说数据存在本地 `./data/` 目录，定期备份即可。

## 更新

```bash
docker compose down
docker load -i lingmo-app-新版本号.tar
docker compose up -d
```

`data/` 不会被覆盖。

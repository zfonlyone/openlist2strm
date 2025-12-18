# OpenList2STRM

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Docker-Ready-blue.svg" alt="Docker">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

轻量级的 OpenList/AList 到 STRM 文件转换 Docker 项目，支持定时/手动同步、增量更新、Telegram 机器人控制和响应式 Web 管理界面。

## ✨ 功能特性

### 核心功能
- 🔄 **自动扫描转换** - 自动扫描 OpenList 中的视频文件并生成 STRM 文件
- ⚡ **增量更新** - 基于文件修改时间的增量更新，避免重复扫描
- 🚦 **QoS 限流** - 可配置的请求速率限制，避免对 OpenList 造成压力
- 💾 **轻量级缓存** - SQLite 缓存，无需额外数据库服务

### 安全功能
- 🔐 **用户认证** - Web 界面登录保护，防止未授权访问
- 🔑 **API Token** - 支持 Bearer Token 认证的 API 调用
- 🛡️ **密码加密** - 密码使用 SHA256 哈希存储

### 管理功能
- 🌐 **响应式 Web 界面** - 现代化的管理界面，完美适配移动设备
- 🤖 **Telegram 机器人** - 通过 Telegram 远程控制和接收通知
- ⏰ **定时任务** - 支持 Cron 表达式的定时扫描
- 📂 **文件夹选择** - 手动选择特定文件夹进行更新

## 🚀 快速开始

### 使用 Docker Compose (推荐)

1. **创建目录**
```bash
mkdir -p /opt/openlist2strm/{config,data}
mkdir -p /etc/media-server/movie/strm  # STRM 输出目录
```

2. **创建配置文件**
```bash
# 复制配置模板
cp config.example.yml /opt/openlist2strm/config/config.yml

# 编辑配置
nano /opt/openlist2strm/config/config.yml
```

3. **启动服务**
```bash
docker-compose up -d
```

4. **访问管理界面**
```
http://your-server-ip:9527
默认用户名: admin
密码: 在配置文件中设置
```

### 使用 Docker 命令

```bash
docker run -d \
  --name openlist2strm \
  -p 127.0.0.1:9527:9527 \
  -v /opt/openlist2strm/config:/config:ro \
  -v /opt/openlist2strm/data:/data \
  -v /etc/media-server/movie/strm:/strm \
  -e TZ=Asia/Shanghai \
  zfonlyone/openlist2strm:latest
```

## ⚙️ 配置说明

### 完整配置示例

```yaml
# OpenList 配置
openlist:
  host: http://openlist:5244   # OpenList 地址
  token: your-api-token        # API Token (从 OpenList 后台获取)
  timeout: 30                  # 请求超时时间

# 路径配置
paths:
  source:                      # 要监控的源路径
    - /115/电影
    - /115/电视剧
    - /115/动漫
  output: /strm                # STRM 输出路径

# 路径映射 (OpenList 路径 -> STRM 中的 URL)
path_mapping:
  /115: http://openlist:5244/d/115

# QoS 限流
qos:
  qps: 5                       # 每秒请求数
  max_concurrent: 3            # 最大并发
  interval: 200                # 请求间隔(ms)

# 定时任务
schedule:
  enabled: true
  cron: "0 2 * * *"           # 每天凌晨2点
  on_startup: false           # 启动时执行

# 增量更新
incremental:
  enabled: true
  check_method: mtime         # mtime | size | both

# Telegram 机器人
telegram:
  enabled: false
  token: your-bot-token
  allowed_users: []           # 留空允许所有用户
  notify:
    on_scan_start: true
    on_scan_complete: true
    on_error: true

# Web 界面
web:
  enabled: true
  port: 9527
  auth:
    enabled: true             # 强烈建议启用
    username: admin
    password: your-password-hash  # 使用 SHA256 哈希
    api_token: ""             # API Token (可选)
```

### 获取 OpenList API Token

1. 登录 OpenList 管理后台
2. 进入 **设置** -> **其他**
3. 复制 **令牌** 字段的值

## 🔐 认证说明

### Web 界面登录

访问 Web 界面时需要输入用户名和密码登录。

- **用户名**: 默认 `admin`
- **密码**: 在配置文件中设置

### API Token 认证

对于程序化 API 调用，可以使用 Bearer Token：

```bash
curl -X POST http://localhost:9527/api/scan \
  -H "Authorization: Bearer <your-api-token>" \
  -H "Content-Type: application/json" \
  -d '{"folders": ["/115/电影"]}'
```

### 豁免端点

以下端点无需认证：
- `GET /api/health` - 健康检查
- `GET /login` - 登录页面
- `GET /static/*` - 静态资源

## 🤖 Telegram 机器人

### 可用命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用 |
| `/scan` | 扫描所有文件夹 |
| `/scan /path` | 扫描指定文件夹 |
| `/scan force` | 强制全量扫描 |
| `/status` | 查看当前状态 |
| `/folders` | 列出监控文件夹 |
| `/select` | 选择文件夹扫描 |
| `/history` | 扫描历史 |
| `/settings` | 查看设置 |
| `/cancel` | 取消当前扫描 |

### 创建 Telegram 机器人

1. 在 Telegram 中找到 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 并按提示操作
3. 获取 Bot Token 并填入配置文件
4. (可选) 获取你的用户 ID 并添加到 `allowed_users`

## 🌐 Web 界面

### 功能页面

- **仪表盘** - 概览统计、快捷操作、扫描状态
- **文件夹** - 管理监控的文件夹、浏览 OpenList 目录
- **任务** - 定时任务设置、扫描历史
- **设置** - QoS 配置、连接测试、缓存管理

### API 文档

访问 `/docs` 查看自动生成的 API 文档 (Swagger UI)。

主要 API 端点：

```
GET  /api/health          # 健康检查 (无需认证)
POST /api/auth/login      # 登录
POST /api/auth/logout     # 登出
GET  /api/status          # 系统状态
POST /api/scan            # 触发扫描
GET  /api/scan/progress   # 扫描进度
POST /api/scan/cancel     # 取消扫描
GET  /api/folders         # 文件夹列表
GET  /api/tasks/schedule  # 定时任务状态
PUT  /api/settings/qos    # 更新 QoS 设置
```

## 🔧 高级配置

### 与 Emby/Jellyfin 集成

STRM 文件生成后，添加 STRM 输出目录到媒体服务器的媒体库即可。

```
Emby/Jellyfin 媒体库路径: /strm
```

### 路径映射说明

`path_mapping` 用于将 OpenList 中的路径转换为 STRM 文件中的播放 URL。

例如：
- OpenList 路径: `/115/电影/Avatar.mkv`
- path_mapping: `/115: http://openlist:5244/d/115`
- 生成的 STRM 内容: `http://openlist:5244/d/115/电影/Avatar.mkv`

### 网络配置

确保 Docker 容器可以访问 OpenList 服务：

```yaml
# docker-compose.yml
networks:
  media-server:
    external: true
```

或使用 host 网络模式：

```yaml
services:
  openlist2strm:
    network_mode: host
```

## 📊 监控与日志

### 查看日志

```bash
docker-compose logs -f openlist2strm
```

### 健康检查

```bash
curl http://localhost:9527/api/health
```

## 🤝 常见问题

### Q: 扫描很慢怎么办？

调整 QoS 设置增加请求速率：
```yaml
qos:
  qps: 10
  max_concurrent: 5
  interval: 100
```

### Q: 如何只扫描特定文件夹？

通过 Web 界面或 Telegram 机器人选择特定文件夹，或使用 API：
```bash
curl -X POST http://localhost:9527/api/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"folders": ["/115/电影"]}'
```

### Q: 如何强制重新生成所有 STRM？

使用强制扫描模式：
```bash
curl -X POST http://localhost:9527/api/scan \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

或通过 Telegram: `/scan force`

### Q: 连接 OpenList 失败？

1. 检查 OpenList 地址是否正确
2. 确保 API Token 有效
3. 检查网络连接和防火墙设置
4. 使用设置页面的"测试连接"功能

### Q: 忘记登录密码怎么办？

编辑配置文件 `/config/config.yml`，修改 `web.auth.password` 为新密码的 SHA256 哈希值，或联系管理员通过 `ms` 工具重置。

## 📄 许可证

MIT License

## 🙏 鸣谢

- [OpenList](https://github.com/OpenListTeam/OpenList) - 文件列表程序
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [python-telegram-bot](https://python-telegram-bot.org/) - Telegram Bot API

---

**Made with ❤️ for the media server community**

# OpenList2STRM

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.2.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Docker-Ready-blue.svg" alt="Docker">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

轻量级的 OpenList/AList 到 STRM 文件转换管理器。它不仅能将云端资源映射为本地媒体库文件，还提供了一套**现代化的多任务调度系统**、增量扫描引擎、Emby 深度集成以及人性化的 Web 管理界面。

## ✨ v1.2.0 核心改进：现代化任务调度

不再需要记忆复杂的 Cron 表达式。新版本引入了更直观的任务调度方式：
- **⏱️ 间隔模式**: 每隔指定分钟运行一次（如：每 60 分钟）。
- **📅 每天定时**: 在每天的固定时间运行（如：每天 04:00）。
- **🚀 立即执行**: 创建后立即运行一次。
- **⚙️ 高级模式**: 依然保留对标准 Cron 表达式的支持，满足极客需求。

---

## 🚀 部署指南

### 1. 快速部署 (Docker-Compose)

推荐使用 Docker Compose 部署，易于维护和升级。

```bash
# 创建必要的映射目录
mkdir -p /opt/openlist2strm/{config,data}
mkdir -p /mnt/media/strm

# 获取 env 模板并填写
wget https://raw.githubusercontent.com/zfonlyone/openlist2strm/main/env.example -O /opt/openlist2strm/env.example
cp /opt/openlist2strm/env.example /opt/openlist2strm/.env

# 启动容器
docker-compose up -d
```

### 2. 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `CONFIG_PATH` | 配置文件在容器内的路径 | `/config/config.yml` |
| `TZ` | 系统时区 | `Asia/Shanghai` |
| `OPENLIST_HOST` | OpenList 服务地址 | `http://openlist:5244` |
| `OPENLIST_TOKEN` | OpenList API Token | 空 |
| `PATHS_SOURCE` | 扫描路径，多个用逗号分隔 | `/115/流媒体` |
| `WEB_AUTH_ENABLED` | 是否启用 Web/API 鉴权 | `true` |
| `WEB_AUTH_USERNAME` | Web 管理员用户名 | `admin` |
| `WEB_AUTH_PASSWORD` | Web 管理员密码 | 空 |
| `WEB_AUTH_API_TOKEN` | Web/API 访问 Token | 空（建议设置） |

---

## 📖 核心功能教程

### 🔐 Web/API 鉴权

系统支持两种受保护访问方式：
- **网页登录会话**：适合人工在浏览器里操作后台
- **Bearer API Key**：适合脚本、自动化任务、外部服务调用

#### 在设置页生成 API Key
1. 打开 **设置** 页面
2. 找到 **🛡️ API 鉴权设置**
3. 可选：开启/关闭鉴权、修改管理员用户名、设置新密码
4. 点击 **⚡ 生成 API Key**
5. 系统会生成一个带 `sk-` 前缀的强 key，并自动保存到配置文件

生成后的请求头格式：

```bash
Authorization: Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

#### API 调用示例

```bash
# 健康检查（无需鉴权）
curl http://127.0.0.1:9527/api/health

# 获取系统状态（需鉴权）
curl http://127.0.0.1:9527/api/status \
  -H "Authorization: Bearer sk-your-generated-key"

# 获取当前设置
curl http://127.0.0.1:9527/api/settings \
  -H "Authorization: Bearer sk-your-generated-key"

# 触发扫描
curl -X POST http://127.0.0.1:9527/api/scan \
  -H "Authorization: Bearer sk-your-generated-key" \
  -H "Content-Type: application/json" \
  -d '{"folders": ["/115/电影"], "force": false}'
```

#### 配置文件说明
- `web.auth.enabled`：是否启用 Web/API 鉴权
- `web.auth.username`：后台管理员用户名
- `web.auth.password`：后台管理员密码（建议保存 hash）
- `web.auth.api_token`：API Key，支持 Bearer 鉴权

#### 环境变量说明
你也可以在 `.env` / compose 中预设：

```bash
WEB_AUTH_ENABLED=true
WEB_AUTH_USERNAME=admin
WEB_AUTH_PASSWORD=
WEB_AUTH_API_TOKEN=sk-your-own-strong-key
```

> 注意：如果应用启动时通过环境变量注入 `WEB_AUTH_API_TOKEN`，它会覆盖配置文件中的值。

### ⚡ 自动化媒体库同步
1.  **添加文件夹**: 在“文件夹”页面添加 OpenList 中需要监控的路径（如 `/115/电影`）。
2.  **创建任务**: 在“任务”页面新建任务，选择“每天定时 (Daily)”并设置 04:00。
3.  **刷新 Emby**: 在“设置”中配置 Emby 地址和 API Key，扫描完成后媒体库将自动更新。

### 📁 STRM 生成模式详解
- **路径模式 (path)**: 适合本地已通过 Rclone/CloudDrive2 挂载了 WebDAV 的环境。STRM 文件内容为文件的相对路径。
- **直链模式 (direct_link)**: 适合没有本地挂载的环境。STRM 文件内容为 OpenList 提供的完整下载链接。

---

## 🛠️ 运维工具

### 管理脚本 `openlist2strm.sh`
项目中包含一个全能管理脚本，支持交互式操作：
```bash
chmod +x openlist2strm.sh
./openlist2strm.sh
```
部署行为说明：
- 脚本会先将当前仓库中的 `openlist2strm` 源码同步到 `/etc/media-server/openlist2strm`
- 然后在 `/etc/media-server/openlist2strm` 目录执行 `docker compose build/up`

主要功能：
- 服务状态一键启停
- 查看实时日志
- 导出/恢复任务配置
- 手动触发全局清理

---

## 🔧 API 参考 (v1.2.0)

### 任务管理
```json
// POST /api/tasks
{
  "name": "每日电影更新",
  "folder": "/115/电影",
  "schedule_type": "daily",
  "schedule_value": "04:00"
}
```

### 设置管理
```bash
# 获取当前所有系统设置
GET /api/settings

# 更新 QoS/限速设置
PUT /api/settings/qos
```

---

## 📄 许可证

MIT License. 欢迎提交 Issue 和 PR。

---

**Made with ❤️ for the media server community**

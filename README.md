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

# 获取配置文件模板
wget https://raw.githubusercontent.com/zfonlyone/openlist2strm/main/config.example.yml -O /opt/openlist2strm/config/config.yml

# 启动容器
docker-compose up -d
```

### 2. 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `CONFIG_PATH` | 配置文件在容器内的路径 | `/config/config.yml` |
| `TZ` | 系统时区 | `Asia/Shanghai` |
| `PUID` / `PGID` | 运行容器的用户/组 ID | `1000/1000` |

---

## 📖 核心功能教程

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

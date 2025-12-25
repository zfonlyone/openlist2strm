# OpenList2STRM

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.1.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/Docker-Ready-blue.svg" alt="Docker">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

轻量级的 OpenList/AList 到 STRM 文件转换 Docker 项目，支持**多任务定时调度**、增量更新、Emby 媒体库刷新、Telegram 机器人控制和响应式 Web 管理界面。

## ✨ v1.1.0 新功能

### 🆕 多任务调度
- 支持创建多个独立的定时任务
- 每个任务可配置不同的文件夹和 Cron 表达式
- 任务生命周期管理：启用、停用、暂停、恢复、删除
- 支持一次性任务（运行一次后自动停用）

### 🆕 Emby 媒体库刷新
- 扫描完成后自动通知 Emby 刷新媒体库
- 支持指定特定媒体库或刷新全部
- 可通过 Web 界面配置和测试连接

### 🆕 STRM 生成模式
- **路径模式 (path)**: 使用相对路径，适合本地 WebDAV 挂载
- **直链模式 (direct_link)**: 使用完整 URL，适合远程访问
- 可配置 URL 编码开关

### 🆕 清理功能
- 自动检测并清理无效软链接
- 清理空目录
- 保持本地与云端一致性

### 🆕 增强的 QoS/线程配置
- 单线程/多线程模式切换
- 可配置线程池大小
- 请求速率限制

---

## 🚀 快速开始

### 使用 Docker Compose (推荐)

1. **创建目录**
```bash
mkdir -p /opt/openlist2strm/{config,data}
mkdir -p /etc/media-server/movie/strm
```

2. **创建配置文件**
```bash
cp config.example.yml /opt/openlist2strm/config/config.yml
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
```

---

## ⚙️ 配置说明

### 完整配置示例

```yaml
# OpenList 配置
openlist:
  host: http://openlist:5244
  token: your-api-token
  timeout: 30

# 路径配置
paths:
  source:
    - /115/电影
    - /115/电视剧
  output: /strm

# STRM 生成配置 (v1.1.0)
strm:
  mode: path              # path | direct_link
  url_encode: true
  output_path: /strm

# 扫描模式 (v1.1.0)
scan:
  mode: incremental       # incremental | full
  data_source: cache      # cache | realtime

# QoS 配置 (v1.1.0 增强)
qos:
  qps: 5
  max_concurrent: 3
  threading_mode: multi   # single | multi
  thread_pool_size: 4
  rate_limit: 100

# 多任务调度 (v1.1.0)
schedule:
  enabled: true
  tasks:
    - id: movies
      name: "电影扫描"
      folder: /115/电影
      cron: "0 2 * * *"
      enabled: true
      one_time: false

# Emby 通知 (v1.1.0)
emby:
  enabled: true
  host: http://emby:8096
  api_key: your-emby-api-key
  notify_on_scan: true
```

---

## 📅 Cron 表达式

| 表达式 | 说明 |
|--------|------|
| `*/30 * * * *` | 每 30 分钟 |
| `0 * * * *` | 每小时整点 |
| `0 2 * * *` | 每天凌晨 2 点 |
| `0 2 * * 0` | 每周日凌晨 2 点 |
| `0 2 1 * *` | 每月 1 号凌晨 2 点 |
| `0 4 * * 1-5` | 工作日凌晨 4 点 |

格式: `分 时 日 月 周`

---

## 🎬 Emby 集成

### 获取 API Key

1. 登录 Emby 管理后台
2. 进入 **设置** → **高级** → **API 密钥**
3. 点击 **新建应用程序**
4. 复制生成的 API Key

### 配置示例

```yaml
emby:
  enabled: true
  host: http://emby:8096
  api_key: your-emby-api-key
  library_id: ""          # 留空刷新所有媒体库
  notify_on_scan: true    # 扫描完成后自动刷新
```

---

## 🧹 清理功能

清理无效文件和目录，保持本地与云端一致：

### 通过 Web 界面
1. 进入设置页面
2. 点击"清理预览"查看待清理项
3. 确认后点击"执行清理"

### 通过命令行
```bash
# 使用管理脚本
./openlist2strm.sh cleanup

# 或通过 API
curl -X POST http://localhost:9527/api/cleanup/preview
curl -X POST http://localhost:9527/api/cleanup -d '{"dry_run":false}'
```

---

## 🤖 Telegram 机器人

### 可用命令

| 命令 | 说明 |
|------|------|
| `/start` | 开始使用 |
| `/scan` | 扫描所有文件夹 |
| `/scan /path` | 扫描指定文件夹 |
| `/status` | 查看当前状态 |
| `/tasks` | 查看定时任务 |
| `/cancel` | 取消当前扫描 |

---

## 🔧 API 参考

### 任务管理 (v1.1.0)

```bash
# 列出所有任务
GET /api/tasks

# 创建任务
POST /api/tasks
{"name":"电影扫描","folder":"/115/电影","cron":"0 2 * * *"}

# 更新任务
PUT /api/tasks/{task_id}

# 删除任务
DELETE /api/tasks/{task_id}

# 启用/停用/暂停/恢复
POST /api/tasks/{task_id}/enable
POST /api/tasks/{task_id}/disable
POST /api/tasks/{task_id}/pause
POST /api/tasks/{task_id}/resume

# 立即执行
POST /api/tasks/{task_id}/run

# Cron 表达式示例
GET /api/tasks/cron/examples
```

### 设置 (v1.1.0)

```bash
# Telegram 设置
GET/PUT /api/settings/telegram

# Emby 设置
GET/PUT /api/settings/emby
POST /api/settings/emby/test

# STRM 设置
GET/PUT /api/settings/strm

# 扫描模式
GET/PUT /api/settings/scan

# QoS 设置
GET/PUT /api/settings/qos
```

### 清理 (v1.1.0)

```bash
# 预览清理
POST /api/cleanup/preview

# 执行清理
POST /api/cleanup

# 目录统计
GET /api/cleanup/stats
```

---

## 🛠️ 管理脚本

使用 `openlist2strm.sh` 管理脚本：

```bash
# 基础操作
./openlist2strm.sh start|stop|restart|status|logs

# 任务管理 (v1.1.0)
./openlist2strm.sh tasks

# 清理功能 (v1.1.0)
./openlist2strm.sh cleanup

# Emby 配置 (v1.1.0)
./openlist2strm.sh emby

# 交互式菜单
./openlist2strm.sh
```

---

## 📊 升级指南

### 从 v1.0.0 升级

1. **备份配置**
```bash
cp /config/config.yml /config/config.yml.bak
```

2. **更新镜像**
```bash
docker pull zfonlyone/openlist2strm:latest
docker-compose up -d
```

3. **配置迁移**
- 原有的单任务配置会自动迁移为多任务格式
- 新功能需要手动配置（Emby、STRM 模式等）

---

## 🤝 常见问题

### Q: 多个任务会同时运行吗？
每个任务按照自己的 Cron 表达式独立运行。如果两个任务同时触发，会排队执行。

### Q: Emby 刷新没有生效？
1. 确认 API Key 正确
2. 使用"测试连接"验证连通性
3. 检查 Emby 日志

### Q: 如何切换 STRM 生成模式？
通过 Web 界面的设置页面，或使用 API：
```bash
curl -X PUT http://localhost:9527/api/settings/strm \
  -d '{"mode":"direct_link"}'
```

---

## 📄 许可证

MIT License

---

**Made with ❤️ for the media server community**

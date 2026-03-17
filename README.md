# OpenList2STRM

轻量级 OpenList/AList 到 STRM 文件转换管理器，包含多任务调度、增量扫描、Emby 通知和 Web 管理界面。

## 架构

项目已按 `ai-proxy` 的模式改造为“源码构建、环境隔离、纯净运行”：

- 源码目录：`/root/code/media-server/openlist2strm`
- 运行目录：`/etc/media-server/openlist2strm`
- 运行时环境变量：`/etc/media-server/openlist2strm/.env`
- 应用配置：`/etc/media-server/openlist2strm/config/config.yml`
- 持久化数据：`/etc/media-server/openlist2strm/data`
- 默认 STRM 输出：`/etc/media-server/openlist2strm/data/strm`

约束：

- 所有代码改动只能在源码目录完成。
- Docker 镜像必须在源码目录构建。
- `/etc/media-server/openlist2strm` 只保留 compose、`.env`、`config/`、`data/` 等运行时文件，不再存放源码。

## 部署

首次部署或代码发布统一执行：

```bash
cd /root/code/media-server/openlist2strm
sudo ./scripts/deploy.sh
```

部署脚本会自动完成：

- 初始化 `/etc/media-server/openlist2strm/{config,data}`
- 创建 `/etc/media-server/openlist2strm/.env`
- 迁移旧版 `config.yml`、`cache.db`、`movie/strm`
- 在源码目录执行 `docker build -t openlist2strm:latest .`
- 将运行目录 `docker-compose.yml` 链接到源码目录版本
- 清理运行目录中的源码残留
- 在 `/etc/media-server/openlist2strm` 启动容器

## 配置

运行时优先修改 `/etc/media-server/openlist2strm/.env`：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `CONFIG_PATH` | 容器内配置文件路径 | `/config/config.yml` |
| `OPENLIST2STRM_BIND_IP` | Web 绑定地址 | `127.0.0.1` |
| `OPENLIST2STRM_WEB_PORT` | Web 端口 | `9527` |
| `OPENLIST2STRM_CONFIG_DIR` | 宿主机配置目录 | `/etc/media-server/openlist2strm/config` |
| `OPENLIST2STRM_DATA_DIR` | 宿主机数据目录 | `/etc/media-server/openlist2strm/data` |
| `OPENLIST2STRM_STRM_DIR` | 宿主机 STRM 输出目录 | `/etc/media-server/openlist2strm/data/strm` |
| `OPENLIST_HOST` | OpenList 服务地址 | `http://openlist:5244` |
| `OPENLIST_TOKEN` | OpenList API Token | 空 |
| `WEB_AUTH_PASSWORD` | Web 管理密码或哈希 | 空 |
| `WEB_AUTH_API_TOKEN` | API Token | 空 |
| `EMBY_API_KEY` | Emby API Key | 空 |
| `TELEGRAM_TOKEN` | Telegram Bot Token | 空 |

非敏感业务配置仍可写在 `config.yml`，例如扫描路径、任务计划、STRM 模式、QoS 等。

## 密钥管理

以下字段推荐只放在 `/etc/media-server/openlist2strm/.env`：

- `OPENLIST_TOKEN`
- `TELEGRAM_TOKEN`
- `EMBY_API_KEY`
- `WEB_AUTH_PASSWORD`
- `WEB_AUTH_API_TOKEN`

如果这些字段已经通过环境变量注入，Web 界面/API 不会再覆盖它们，避免把密钥回写进 `config.yml`。

## 常用检查

```bash
docker compose --env-file /etc/media-server/openlist2strm/.env \
  -f /etc/media-server/openlist2strm/docker-compose.yml ps

docker inspect openlist2strm

curl http://127.0.0.1:9527/api/health
```

## API 示例

```bash
curl http://127.0.0.1:9527/api/health

curl http://127.0.0.1:9527/api/status \
  -H "Authorization: Bearer sk-your-generated-key"

curl -X POST http://127.0.0.1:9527/api/scan \
  -H "Authorization: Bearer sk-your-generated-key" \
  -H "Content-Type: application/json" \
  -d '{"folders":["/115/电影"],"force":false}'
```

## 许可证

MIT

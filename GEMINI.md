# OpenList2STRM 项目架构与部署规范

## 1. 核心架构：源码构建、环境隔离、纯净运行
本项目遵循与 `ai-proxy` 一致的运行模型：

- 源码目录：`/root/code/media-server/openlist2strm`
  - 负责代码修改、镜像构建、文档维护。
  - Docker 镜像只打包应用逻辑，禁止把 `.env`、运行时 `config.yml`、数据库或缓存文件打进镜像。
- 运行目录：`/etc/media-server/openlist2strm`
  - 负责容器启动、持久化配置、业务数据、STRM 输出目录映射。
  - 运行目录内允许存在 `docker-compose.yml`、`.env`、`config/`、`data/` 等控制文件。
  - 禁止在该目录放置或修改 Python/HTML/JS 等源码文件。

## 2. 配置规范
- 唯一运行时环境变量文件：`/etc/media-server/openlist2strm/.env`
- YAML 配置目录：`/etc/media-server/openlist2strm/config/`
- 持久化数据目录：`/etc/media-server/openlist2strm/data/`
- 默认 STRM 输出目录：`/etc/media-server/openlist2strm/data/strm`

敏感字段优先放到运行时 `.env`：
- `OPENLIST_TOKEN`
- `TELEGRAM_TOKEN`
- `EMBY_API_KEY`
- `WEB_AUTH_PASSWORD`
- `WEB_AUTH_API_TOKEN`

如果这些变量已经在 `.env` 中配置，Web 界面不会再把它们写回 `config.yml`。

## 3. 部署流程
代码变更后，只能在源码目录执行部署：

```bash
cd /root/code/media-server/openlist2strm
sudo ./scripts/deploy.sh
```

部署脚本负责：
1. 初始化 `/etc/media-server/openlist2strm/{config,data}`
2. 迁移旧版 `config.yml`、`cache.db`、`movie/strm` 等存量文件
3. 在源码目录执行 `docker build -t openlist2strm:latest .`
4. 将运行目录中的 `docker-compose.yml` 指向源码目录版本
5. 清理运行目录中的源码残留
6. 在运行目录执行 `docker compose up -d`

## 4. AI 助手操作约束
- 修改逻辑代码：只在 `/root/code/media-server/openlist2strm`
- 修改运行参数：改 `/etc/media-server/openlist2strm/.env`
- 修改非敏感应用配置：改 `/etc/media-server/openlist2strm/config/config.yml`
- 发布变更：执行 `sudo ./scripts/deploy.sh`
- 严禁在 `/etc/media-server/openlist2strm` 直接改源码

#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_DIR="/etc/media-server/openlist2strm"
ENV_FILE="${BASE_DIR}/.env"
ENV_TEMPLATE="${PROJECT_DIR}/env.example"
CONFIG_DIR="${BASE_DIR}/config"
DATA_DIR="${BASE_DIR}/data"
DEFAULT_STRM_DIR="${DATA_DIR}/strm"
IMAGE_NAME="openlist2strm:latest"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[✓]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1" >&2
}

require_root() {
    if [ "${EUID}" -ne 0 ]; then
        error "请使用 root 权限运行：sudo ./scripts/deploy.sh"
        exit 1
    fi
}

require_cmd() {
    local cmd="$1"
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        error "缺少命令: ${cmd}"
        exit 1
    fi
}

read_env_key() {
    local file="$1"
    local key="$2"
    [ -f "${file}" ] || return 0
    awk -F= -v k="${key}" '$1==k {sub(/^[^=]*=/, ""); print; exit}' "${file}"
}

upsert_env_key() {
    local file="$1"
    local key="$2"
    local value="$3"
    mkdir -p "$(dirname "${file}")"
    touch "${file}"

    if grep -q "^${key}=" "${file}"; then
        local escaped
        escaped=$(printf '%s' "${value}" | sed 's/[\/&]/\\&/g')
        sed -i "s/^${key}=.*/${key}=${escaped}/" "${file}"
    else
        echo "${key}=${value}" >> "${file}"
    fi
}

ensure_env_key() {
    local key="$1"
    local fallback="$2"
    local current
    current="$(read_env_key "${ENV_FILE}" "${key}")"
    if [ -z "${current:-}" ]; then
        upsert_env_key "${ENV_FILE}" "${key}" "${fallback}"
        log ".env 补充字段: ${key}"
    fi
}

migrate_legacy_layout() {
    if [ -f "${BASE_DIR}/config.yml" ] && [ ! -f "${CONFIG_DIR}/config.yml" ]; then
        mv "${BASE_DIR}/config.yml" "${CONFIG_DIR}/config.yml"
        log "已迁移旧版 config.yml -> config/config.yml"
    fi

    if [ -f "${BASE_DIR}/config.yaml" ] && [ ! -f "${CONFIG_DIR}/config.yaml" ]; then
        mv "${BASE_DIR}/config.yaml" "${CONFIG_DIR}/config.yaml"
        log "已迁移旧版 config.yaml -> config/config.yaml"
    fi

    if [ -f "${BASE_DIR}/cache.db" ] && [ ! -f "${DATA_DIR}/cache.db" ]; then
        mv "${BASE_DIR}/cache.db" "${DATA_DIR}/cache.db"
        log "已迁移 cache.db -> data/cache.db"
    fi

    if [ -f "${BASE_DIR}/weekly-sync-state.json" ] && [ ! -f "${DATA_DIR}/weekly-sync-state.json" ]; then
        mv "${BASE_DIR}/weekly-sync-state.json" "${DATA_DIR}/weekly-sync-state.json"
        log "已迁移 weekly-sync-state.json -> data/"
    fi

    if [ -d "${BASE_DIR}/movie/strm" ] && [ ! -d "${DEFAULT_STRM_DIR}" ]; then
        mkdir -p "${DATA_DIR}"
        mv "${BASE_DIR}/movie/strm" "${DEFAULT_STRM_DIR}"
        log "已迁移 movie/strm -> data/strm"
    fi
}

migrate_config_secrets_to_env() {
    local config_path=""

    if [ -f "${CONFIG_DIR}/config.yml" ]; then
        config_path="${CONFIG_DIR}/config.yml"
    elif [ -f "${CONFIG_DIR}/config.yaml" ]; then
        config_path="${CONFIG_DIR}/config.yaml"
    fi

    [ -n "${config_path}" ] || return 0

    if ! python3 -c "import yaml" >/dev/null 2>&1; then
        warn "宿主机缺少 PyYAML，跳过运行时密钥迁移"
        return 0
    fi

    CONFIG_PATH_FOR_MIGRATION="${config_path}" ENV_FILE_FOR_MIGRATION="${ENV_FILE}" python3 <<'PY'
import os
from pathlib import Path

import yaml

config_path = Path(os.environ["CONFIG_PATH_FOR_MIGRATION"])
env_file = Path(os.environ["ENV_FILE_FOR_MIGRATION"])

if not config_path.exists():
    raise SystemExit(0)

with config_path.open("r", encoding="utf-8") as fh:
    data = yaml.safe_load(fh) or {}

env_values = {}
if env_file.exists():
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        if not raw or raw.lstrip().startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        env_values[key] = value

bindings = {
    "OPENLIST_TOKEN": ("openlist", "token"),
    "TELEGRAM_TOKEN": ("telegram", "token"),
    "EMBY_API_KEY": ("emby", "api_key"),
    "WEB_AUTH_PASSWORD": ("web", "auth", "password"),
    "WEB_AUTH_API_TOKEN": ("web", "auth", "api_token"),
}

changed_env = False
changed_yaml = False

for env_key, path in bindings.items():
    node = data
    for part in path[:-1]:
        if not isinstance(node, dict):
            node = None
            break
        node = node.get(part)
    if not isinstance(node, dict):
        continue

    leaf = path[-1]
    value = node.get(leaf)
    if value in (None, ""):
        continue

    if not env_values.get(env_key):
        env_values[env_key] = str(value)
        changed_env = True

    if node.get(leaf) != "":
        node[leaf] = ""
        changed_yaml = True

if changed_env:
    lines = []
    seen = set()
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            if "=" not in raw or raw.lstrip().startswith("#"):
                lines.append(raw)
                continue
            key, _ = raw.split("=", 1)
            if key in env_values:
                lines.append(f"{key}={env_values[key]}")
                seen.add(key)
            else:
                lines.append(raw)
                seen.add(key)
    for key, value in env_values.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    env_file.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

if changed_yaml:
    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)
PY

    log "已完成运行时密钥迁移到 .env"
}

ensure_runtime_config() {
    if [ ! -f "${CONFIG_DIR}/config.yml" ] && [ ! -f "${CONFIG_DIR}/config.yaml" ]; then
        cp "${PROJECT_DIR}/config/config.example.yml" "${CONFIG_DIR}/config.yml"
        log "已创建运行时配置: ${CONFIG_DIR}/config.yml"
    fi
}

link_control_files() {
    ln -sfn "${PROJECT_DIR}/docker-compose.yml" "${BASE_DIR}/docker-compose.yml"
    log "运行目录 compose 已链接到源码目录"
}

clean_runtime_code() {
    rm -rf \
        "${BASE_DIR}/app" \
        "${BASE_DIR}/.git" \
        "${BASE_DIR}/.github" \
        "${BASE_DIR}/Dockerfile" \
        "${BASE_DIR}/requirements.txt" \
        "${BASE_DIR}/README.md" \
        "${BASE_DIR}/AGENTS.md" \
        "${BASE_DIR}/GEMINI.md" \
        "${BASE_DIR}/env.example" \
        "${BASE_DIR}/etc" \
        "${BASE_DIR}/scripts"
}

ensure_network() {
    if ! docker network inspect media-server >/dev/null 2>&1; then
        docker network create media-server >/dev/null
        log "已创建 Docker 网络: media-server"
    fi
}

main() {
    require_root
    require_cmd docker
    require_cmd python3

    mkdir -p "${CONFIG_DIR}" "${DATA_DIR}" "${DEFAULT_STRM_DIR}"
    log "已初始化运行目录: ${BASE_DIR}"

    migrate_legacy_layout

    if [ ! -f "${ENV_FILE}" ]; then
        cp "${ENV_TEMPLATE}" "${ENV_FILE}"
        chmod 600 "${ENV_FILE}"
        log "已创建运行时 .env"
    fi

    ensure_env_key "CONFIG_PATH" "/config/config.yml"
    ensure_env_key "OPENLIST2STRM_BIND_IP" "127.0.0.1"
    ensure_env_key "OPENLIST2STRM_WEB_PORT" "9527"
    ensure_env_key "OPENLIST2STRM_CONFIG_DIR" "${CONFIG_DIR}"
    ensure_env_key "OPENLIST2STRM_DATA_DIR" "${DATA_DIR}"
    ensure_env_key "OPENLIST2STRM_STRM_DIR" "${DEFAULT_STRM_DIR}"

    ensure_runtime_config
    migrate_config_secrets_to_env

    log "在源码目录构建镜像..."
    docker build -t "${IMAGE_NAME}" "${PROJECT_DIR}"

    link_control_files
    clean_runtime_code
    ensure_network

    log "在运行目录启动服务..."
    cd "${BASE_DIR}"
    docker compose up -d --remove-orphans

    log "部署完成"
}

main "$@"

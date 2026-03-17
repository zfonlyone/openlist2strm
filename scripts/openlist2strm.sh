#!/bin/bash

# ==========================================================
# OpenList2STRM 服务管理脚本 v2.4
# 功能: 管理 OpenList2STRM 容器 (v1.2.0)
# 特性: 简化任务管理 (间隔/每日), Emby通知, 清理功能
# 证书管理: 使用 Certbot 管理
# ==========================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ===== 配置 =====
BASE_DIR="/etc/media-server"
GLOBAL_CONFIG="$BASE_DIR/config.yml"
CONTAINER="openlist2strm"
SERVICE="openlist2strm"
IMAGE="local/openlist2strm:dev"
WEB_PORT=9527
APP_DIR="$BASE_DIR/openlist2strm"
CONFIG_DIR="$APP_DIR/config"
CONFIG_FILE="$CONFIG_DIR/config.yml"
ENV_FILE="$APP_DIR/.env"
VERSION="1.2.0"
CERT_DIR="/etc/letsencrypt/live"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_SRC_DIR="${PROJECT_DIR}"

log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
info()  { echo -e "${CYAN}[i]${NC} $1"; }

# ===== 全局配置读取/保存 =====
load_global_config() {
    if [ -f "$GLOBAL_CONFIG" ]; then
        WEB_PORT=$(grep -E "^\s*strm:" "$GLOBAL_CONFIG" | awk '{print $2}' | head -1)
        WEB_PORT=${WEB_PORT:-9527}
    fi
}

save_global_config() {
    if [ -f "$GLOBAL_CONFIG" ]; then
        sed -i "s/^\(\s*strm:\s*\)[0-9]*/\1${WEB_PORT}/" "$GLOBAL_CONFIG"
        log "配置已保存到 $GLOBAL_CONFIG"
    fi
}

load_global_config

load_env_file() {
    [ -f "$ENV_FILE" ] || return 0
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        case "$key" in
            \#*|"") continue ;;
        esac
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
        export "$key=$value"
    done < "$ENV_FILE"
}

set_env_value() {
    local key="$1"
    local value="$2"
    mkdir -p "$(dirname "$ENV_FILE")"
    touch "$ENV_FILE"

    local escaped
    escaped=$(printf '%s' "$value" | sed 's/[\/&]/\\&/g')
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s/^${key}=.*/${key}=${escaped}/" "$ENV_FILE"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

extract_first_source_path() {
    local file="$1"
    awk '
        /^\s*paths:\s*$/ {in_paths=1; next}
        in_paths && /^\s*source:\s*$/ {in_source=1; next}
        in_source && /^\s*-\s*/ {sub(/^\s*-\s*/, "", $0); print; exit}
        in_source && !/^\s*-\s*/ {exit}
    ' "$file" 2>/dev/null
}

extract_in_section() {
    local file="$1"
    local section="$2"
    local key="$3"
    awk -v sec="$section" -v k="$key" '
        $0 ~ "^[[:space:]]*"sec":[[:space:]]*$" {in_sec=1; next}
        in_sec && $0 ~ "^[^[:space:]]" {in_sec=0}
        in_sec && $0 ~ "^[[:space:]]*"k":[[:space:]]*" {
            sub(/^[[:space:]]*[A-Za-z0-9_]+:[[:space:]]*/, "", $0)
            gsub(/"/, "", $0)
            print $0
            exit
        }
    ' "$file" 2>/dev/null
}

extract_in_web_auth() {
    local file="$1"
    local key="$2"
    awk -v k="$key" '
        /^\s*web:\s*$/ {in_web=1; next}
        in_web && /^[^[:space:]]/ {in_web=0}
        in_web && /^\s*auth:\s*$/ {in_auth=1; next}
        in_auth && /^\s{2}[a-zA-Z0-9_]+:\s*$/ && $0 !~ /^\s*auth:\s*$/ {in_auth=0}
        in_auth && $0 ~ "^[[:space:]]*"k":[[:space:]]*" {
            sub(/^[[:space:]]*[A-Za-z0-9_]+:[[:space:]]*/, "", $0)
            gsub(/"/, "", $0)
            print $0
            exit
        }
    ' "$file" 2>/dev/null
}

write_env_file() {
    mkdir -p "$APP_DIR"
    [ -z "${TZ:-}" ] && TZ="Asia/Shanghai"
    [ -z "${OPENLIST2STRM_BIND_IP:-}" ] && OPENLIST2STRM_BIND_IP="127.0.0.1"
    [ -z "${OPENLIST2STRM_WEB_PORT:-}" ] && OPENLIST2STRM_WEB_PORT="$WEB_PORT"
    [ -z "${OPENLIST2STRM_CONFIG_DIR:-}" ] && OPENLIST2STRM_CONFIG_DIR="./config"
    [ -z "${OPENLIST2STRM_DATA_DIR:-}" ] && OPENLIST2STRM_DATA_DIR="./data"
    [ -z "${OPENLIST2STRM_STRM_DIR:-}" ] && OPENLIST2STRM_STRM_DIR="${BASE_DIR}/movie/strm"
    [ -z "${CONFIG_PATH:-}" ] && CONFIG_PATH="/config/config.yml"

    [ -z "${OPENLIST_HOST:-}" ] && OPENLIST_HOST="http://openlist:5244"
    [ -z "${OPENLIST_TIMEOUT:-}" ] && OPENLIST_TIMEOUT="30"
    [ -z "${PATHS_SOURCE:-}" ] && PATHS_SOURCE="/115/流媒体"
    [ -z "${PATHS_OUTPUT:-}" ] && PATHS_OUTPUT="/strm"

    [ -z "${STRM_MODE:-}" ] && STRM_MODE="path"
    [ -z "${STRM_URL_ENCODE:-}" ] && STRM_URL_ENCODE="true"
    [ -z "${STRM_KEEP_STRUCTURE:-}" ] && STRM_KEEP_STRUCTURE="true"
    [ -z "${STRM_OUTPUT_PATH:-}" ] && STRM_OUTPUT_PATH="/strm"

    [ -z "${WEB_AUTH_ENABLED:-}" ] && WEB_AUTH_ENABLED="true"
    [ -z "${WEB_AUTH_USERNAME:-}" ] && WEB_AUTH_USERNAME="admin"
    [ -z "${WEB_AUTH_PASSWORD:-}" ] && WEB_AUTH_PASSWORD=""
    [ -z "${WEB_AUTH_API_TOKEN:-}" ] && WEB_AUTH_API_TOKEN="$(openssl rand -hex 16)"

    [ -z "${EMBY_ENABLED:-}" ] && EMBY_ENABLED="false"
    [ -z "${EMBY_NOTIFY_ON_SCAN:-}" ] && EMBY_NOTIFY_ON_SCAN="true"

    [ -z "${LOG_LEVEL:-}" ] && LOG_LEVEL="INFO"
    [ -z "${LOG_RETENTION_DAYS:-}" ] && LOG_RETENTION_DAYS="7"
    [ -z "${LOG_COLORIZE:-}" ] && LOG_COLORIZE="true"

    cat > "$ENV_FILE" <<EOF
TZ=${TZ}
CONFIG_PATH=${CONFIG_PATH}
OPENLIST2STRM_BIND_IP=${OPENLIST2STRM_BIND_IP}
OPENLIST2STRM_WEB_PORT=${OPENLIST2STRM_WEB_PORT}
OPENLIST2STRM_CONFIG_DIR=${OPENLIST2STRM_CONFIG_DIR}
OPENLIST2STRM_DATA_DIR=${OPENLIST2STRM_DATA_DIR}
OPENLIST2STRM_STRM_DIR=${OPENLIST2STRM_STRM_DIR}
OPENLIST_HOST=${OPENLIST_HOST}
OPENLIST_TOKEN=${OPENLIST_TOKEN:-}
OPENLIST_TIMEOUT=${OPENLIST_TIMEOUT}
PATHS_SOURCE=${PATHS_SOURCE}
PATHS_OUTPUT=${PATHS_OUTPUT}
STRM_MODE=${STRM_MODE}
STRM_URL_ENCODE=${STRM_URL_ENCODE}
STRM_KEEP_STRUCTURE=${STRM_KEEP_STRUCTURE}
STRM_OUTPUT_PATH=${STRM_OUTPUT_PATH}
WEB_AUTH_ENABLED=${WEB_AUTH_ENABLED}
WEB_AUTH_USERNAME=${WEB_AUTH_USERNAME}
WEB_AUTH_PASSWORD=${WEB_AUTH_PASSWORD}
WEB_AUTH_API_TOKEN=${WEB_AUTH_API_TOKEN}
EMBY_ENABLED=${EMBY_ENABLED}
EMBY_HOST=${EMBY_HOST:-}
EMBY_API_KEY=${EMBY_API_KEY:-}
EMBY_LIBRARY_ID=${EMBY_LIBRARY_ID:-}
EMBY_NOTIFY_ON_SCAN=${EMBY_NOTIFY_ON_SCAN}
LOG_LEVEL=${LOG_LEVEL}
LOG_RETENTION_DAYS=${LOG_RETENTION_DAYS}
LOG_COLORIZE=${LOG_COLORIZE}
EOF
    chmod 600 "$ENV_FILE"
    WEB_PORT="$OPENLIST2STRM_WEB_PORT"
    log ".env 已生成: $ENV_FILE"
}

migrate_legacy_config_to_env() {
    [ -f "$CONFIG_FILE" ] || return 0
    if [ -f "$ENV_FILE" ]; then
        load_env_file
        WEB_PORT="${OPENLIST2STRM_WEB_PORT:-$WEB_PORT}"
        return 0
    fi

    log "检测到旧配置文件，开始迁移到 .env"
    OPENLIST_HOST=$(extract_in_section "$CONFIG_FILE" "openlist" "host")
    [ -z "$OPENLIST_HOST" ] && OPENLIST_HOST=$(extract_in_section "$CONFIG_FILE" "openlist" "url")
    OPENLIST_TOKEN=$(extract_in_section "$CONFIG_FILE" "openlist" "token")
    OPENLIST2STRM_WEB_PORT=$(extract_in_section "$CONFIG_FILE" "web" "port")
    [ -z "$OPENLIST2STRM_WEB_PORT" ] && OPENLIST2STRM_WEB_PORT=$(extract_in_section "$CONFIG_FILE" "server" "port")
    PATHS_SOURCE=$(extract_first_source_path "$CONFIG_FILE")
    WEB_AUTH_USERNAME=$(extract_in_web_auth "$CONFIG_FILE" "username")
    WEB_AUTH_PASSWORD=$(extract_in_web_auth "$CONFIG_FILE" "password")
    WEB_AUTH_API_TOKEN=$(extract_in_web_auth "$CONFIG_FILE" "api_token")
    [ -z "$WEB_AUTH_API_TOKEN" ] && WEB_AUTH_API_TOKEN=$(extract_in_section "$CONFIG_FILE" "server" "token")
    EMBY_HOST=$(extract_in_section "$CONFIG_FILE" "emby" "host")
    EMBY_API_KEY=$(extract_in_section "$CONFIG_FILE" "emby" "api_key")

    WEB_PORT=${OPENLIST2STRM_WEB_PORT:-$WEB_PORT}
    write_env_file
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak.$(date +%Y%m%d_%H%M%S)"
    log "旧配置已迁移并备份"
}

write_yaml_config_from_env() {
    mkdir -p "$CONFIG_DIR"
    local source_yaml
    source_yaml=$(echo "${PATHS_SOURCE:-/115/流媒体}" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed '/^$/d' | sed 's/^/    - /')
    [ -z "$source_yaml" ] && source_yaml="    - /115/流媒体"

    cat > "$CONFIG_FILE" <<EOF
openlist:
  host: ${OPENLIST_HOST:-http://openlist:5244}
  token: ${OPENLIST_TOKEN:-}
  timeout: ${OPENLIST_TIMEOUT:-30}
paths:
  source:
${source_yaml}
  output: ${PATHS_OUTPUT:-/strm}
strm:
  mode: ${STRM_MODE:-path}
  url_encode: ${STRM_URL_ENCODE:-true}
  keep_structure: ${STRM_KEEP_STRUCTURE:-true}
  output_path: ${STRM_OUTPUT_PATH:-/strm}
scan:
  mode: incremental
  data_source: cache
qos:
  qps: 5
  max_concurrent: 3
  interval: 200
  threading_mode: multi
  thread_pool_size: 4
  rate_limit: 100
schedule:
  enabled: false
  on_startup: false
  tasks: []
emby:
  enabled: ${EMBY_ENABLED:-false}
  host: ${EMBY_HOST:-}
  api_key: ${EMBY_API_KEY:-}
  library_id: ${EMBY_LIBRARY_ID:-}
  notify_on_scan: ${EMBY_NOTIFY_ON_SCAN:-true}
telegram:
  enabled: false
  token: ""
  chat_id: ""
  allowed_users: []
  notify:
    on_scan_start: true
    on_scan_complete: true
    on_error: true
incremental:
  enabled: true
  check_method: mtime
web:
  enabled: true
  port: ${OPENLIST2STRM_WEB_PORT:-9527}
  auth:
    enabled: ${WEB_AUTH_ENABLED:-true}
    username: ${WEB_AUTH_USERNAME:-admin}
    password: "${WEB_AUTH_PASSWORD:-}"
    api_token: "${WEB_AUTH_API_TOKEN:-}"
logging:
  level: ${LOG_LEVEL:-INFO}
  retention_days: ${LOG_RETENTION_DAYS:-7}
  colorize: ${LOG_COLORIZE:-true}
EOF
}

ensure_runtime_config() {
    migrate_legacy_config_to_env
    [ -f "$ENV_FILE" ] || write_env_file
    load_env_file
    WEB_PORT="${OPENLIST2STRM_WEB_PORT:-$WEB_PORT}"
    write_yaml_config_from_env
}

dc() {
    if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
        error "未找到部署编排文件: $APP_DIR/docker-compose.yml"
        return 1
    fi
    cd "$APP_DIR" || exit 1
    if command -v docker-compose &>/dev/null; then
        docker-compose "$@"
    else
        docker compose "$@"
    fi
}

sync_local_source() {
    if [ ! -d "$LOCAL_SRC_DIR" ] || [ ! -f "$LOCAL_SRC_DIR/Dockerfile" ]; then
        error "未找到本地源码目录: $LOCAL_SRC_DIR"
        error "请确认 openlist2strm 子目录存在且包含 Dockerfile"
        return 1
    fi

    mkdir -p "$APP_DIR"
    if command -v rsync &>/dev/null; then
        rsync -a --delete \
            --exclude '.git/' \
            --exclude '__pycache__/' \
            --exclude '*.pyc' \
            --exclude '.env' \
            --filter 'P config/' \
            --filter 'P data/' \
            --filter 'P movie/' \
            "$LOCAL_SRC_DIR"/ "$APP_DIR"/
    else
        find "$APP_DIR" -mindepth 1 -maxdepth 1 \
            ! -name config \
            ! -name data \
            ! -name movie \
            ! -name .env \
            -exec rm -rf {} +
        cp -a "$LOCAL_SRC_DIR"/. "$APP_DIR"/
        rm -rf "$APP_DIR/.git" 2>/dev/null || true
        find "$APP_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
        find "$APP_DIR" -type f -name '*.pyc' -delete 2>/dev/null || true
    fi
}

ensure_local_build_service() {
    local compose_file="$APP_DIR/docker-compose.yml"
    [ -f "$compose_file" ] || return 0

    if grep -q "image: zfonlyone/openlist2strm:latest" "$compose_file"; then
        sed -i "/^[[:space:]]*openlist2strm:/,/^[[:space:]]*[a-zA-Z0-9_-]\+:/ s|^[[:space:]]*image:[[:space:]]*zfonlyone/openlist2strm:latest|    build:\\n      context: .\\n      dockerfile: Dockerfile\\n    image: $IMAGE|" "$compose_file"
        log "已切换 openlist2strm 为本地构建模式"
    fi
}

build_local_image() {
    sync_local_source || return 1
    ensure_local_build_service
    log "构建本地镜像: $IMAGE"
    dc build "$SERVICE"
}

show_menu() {
    echo -e "${CYAN}=== OpenList2STRM 管理工具 v2.4 (App v${VERSION}) ===${NC}"
    echo "1. 启动服务"
    echo "2. 停止服务"
    echo "3. 重启服务"
    echo "4. 本地构建并更新"
    echo "5. 查看状态"
    echo "6. 查看日志"
    echo "7. 编辑配置"
    echo "8. 触发扫描"
    echo "9. 查看 STRM 文件"
    echo "10. 单独安装"
    echo "11. 重新配置"
    echo -e "${CYAN}--- v1.1.0 新功能 ---${NC}"
    echo "12. 任务管理"
    echo "13. 清理功能"
    echo "14. Emby 通知配置"
    echo "15. Nginx 配置"
    echo -e "${RED}16. 卸载服务${NC}"
    echo "0. 退出"
}

# ===== 基础操作 =====
start_service() {
    log "启动 OpenList2STRM（本地构建，仅此服务）..."
    ensure_runtime_config
    build_local_image || return 1
    dc up -d --no-deps "$SERVICE"
}
stop_service()  { log "停止 OpenList2STRM..."; dc stop $SERVICE; }
restart_service() {
    log "重启 OpenList2STRM（本地构建，仅此服务）..."
    ensure_runtime_config
    build_local_image || return 1
    dc up -d --no-deps --force-recreate "$SERVICE"
}

update_service() {
    log "从本地源码构建并更新 OpenList2STRM..."
    ensure_runtime_config
    build_local_image || return 1
    dc up -d --no-deps --force-recreate "$SERVICE"
    log "更新完成（未影响其它服务）"
}

show_status() {
    ensure_runtime_config
    echo -e "${CYAN}=== OpenList2STRM 状态 ===${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAMES|$CONTAINER"
    echo
    docker stats --no-stream --format "CPU: {{.CPUPerc}}  内存: {{.MemUsage}}" $CONTAINER 2>/dev/null
    echo
    info "配置文件: $CONFIG_FILE"
    info "版本: $VERSION"
    
    # 显示 STRM 统计
    STRM_DIR="$BASE_DIR/movie/strm"
    if [ -d "$STRM_DIR" ]; then
        info "STRM 文件数: $(find "$STRM_DIR" -name "*.strm" 2>/dev/null | wc -l)"
    fi
    
    # 显示任务状态
    echo
    info "定时任务状态:"
    curl -s "http://localhost:$WEB_PORT/api/tasks" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tasks = data.get('tasks', [])
    if not tasks:
        print('  无定时任务')
    for t in tasks:
        status = '启用' if t.get('enabled') else '停用'
        if t.get('paused'):
            status = '暂停'
        print(f\"  [{status}] {t.get('name', 'Unknown')} - {t.get('cron', '')}\")
except:
    print('  无法获取任务状态')
" 2>/dev/null || warn "无法连接到 API"
}

show_logs() {
    echo "1. 实时日志 (Ctrl+C 退出)"
    echo "2. 最近 100 行"
    echo "3. 错误日志"
    echo "4. 扫描日志"
    read -p "选择: " choice
    case $choice in
        1) docker logs -f --tail=50 $CONTAINER ;;
        2) docker logs --tail=100 $CONTAINER ;;
        3) docker logs $CONTAINER 2>&1 | grep -iE "error|fail|exception" | tail -50 ;;
        4) docker logs $CONTAINER 2>&1 | grep -iE "scan|strm|生成" | tail -50 ;;
    esac
}

# ===== 配置管理 =====
edit_config() {
    echo -e "${CYAN}=== 配置管理 ===${NC}"
    echo "1. 编辑 .env"
    echo "2. 查看当前配置"
    echo "3. 备份配置"
    echo "4. 恢复配置"
    echo "5. 修改源路径"
    echo "6. 修改 OpenList 连接"
    echo "7. 配置 STRM 生成规则"
    echo "8. 配置线程/QoS 设置"
    read -p "选择: " choice
    
    case $choice in
        1)
            ensure_runtime_config
            ${EDITOR:-vim} "$ENV_FILE"
            load_env_file
            write_yaml_config_from_env
            read -p "是否重启服务? [Y/n]: " restart
            [[ ! "$restart" =~ ^[Nn]$ ]] && restart_service
            ;;
        2) [ -f "$CONFIG_FILE" ] && cat "$CONFIG_FILE" ;;
        3)
            ensure_runtime_config
            BACKUP="$ENV_FILE.bak.$(date +%Y%m%d_%H%M%S)"
            cp "$ENV_FILE" "$BACKUP"
            log "配置已备份到: $BACKUP"
            ;;
        4)
            ls -la "$APP_DIR"/.env.bak.* 2>/dev/null || echo "无备份"
            read -p "输入备份文件名: " backup
            [ -f "$APP_DIR/$backup" ] && cp "$APP_DIR/$backup" "$ENV_FILE" && restart_service
            ;;
        5) modify_source_paths ;;
        6) modify_openlist_connection ;;
        7) configure_strm_rules ;;
        8) configure_qos ;;
    esac
}

modify_source_paths() {
    echo -e "${CYAN}=== 修改源路径 ===${NC}"
    ensure_runtime_config
    info "当前源路径:"
    echo "${PATHS_SOURCE:-/115/流媒体}" | tr ',' '\n' | sed 's/^/  - /'
    echo
    read -p "请输入新的源路径 (多个用逗号分隔): " NEW_PATHS
    
    if [ -n "$NEW_PATHS" ]; then
        set_env_value "PATHS_SOURCE" "$NEW_PATHS"
        load_env_file
        write_yaml_config_from_env
        log "源路径已更新"
        read -p "是否重启服务? [Y/n]: " restart
        [[ ! "$restart" =~ ^[Nn]$ ]] && restart_service
    fi
}

modify_openlist_connection() {
    echo -e "${CYAN}=== 修改 OpenList 连接 ===${NC}"
    ensure_runtime_config
    read -p "OpenList 地址 [${OPENLIST_HOST:-http://openlist:5244}]: " ALIST_URL
    read -sp "OpenList Token: " ALIST_TOKEN
    echo
    
    set_env_value "OPENLIST_HOST" "${ALIST_URL:-${OPENLIST_HOST:-http://openlist:5244}}"
    [ -n "$ALIST_TOKEN" ] && set_env_value "OPENLIST_TOKEN" "$ALIST_TOKEN"
    load_env_file
    write_yaml_config_from_env
    log "OpenList 连接已更新"
    restart_service
}

configure_strm_rules() {
    echo -e "${CYAN}=== STRM 生成规则 ===${NC}"
    echo "当前设置:"
    curl -s "http://localhost:$WEB_PORT/api/settings/strm" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  模式: {data.get('mode', 'path')}\")
print(f\"  URL编码: {data.get('url_encode', True)}\")
print(f\"  输出路径: {data.get('output_path', '/strm')}\")
" 2>/dev/null || warn "无法获取设置"
    
    echo
    echo "1. 使用路径模式 (path)"
    echo "2. 使用直链模式 (direct_link)"
    echo "3. 切换 URL 编码"
    echo "4. 修改输出路径"
    read -p "选择: " choice
    
    case $choice in
        1) curl -X PUT "http://localhost:$WEB_PORT/api/settings/strm" \
            -H "Content-Type: application/json" -d '{"mode":"path"}' 2>/dev/null && log "已切换到路径模式" ;;
        2) curl -X PUT "http://localhost:$WEB_PORT/api/settings/strm" \
            -H "Content-Type: application/json" -d '{"mode":"direct_link"}' 2>/dev/null && log "已切换到直链模式" ;;
        3) 
            read -p "是否启用 URL 编码? [Y/n]: " encode
            val="true"
            [[ "$encode" =~ ^[Nn]$ ]] && val="false"
            curl -X PUT "http://localhost:$WEB_PORT/api/settings/strm" \
                -H "Content-Type: application/json" -d "{\"url_encode\":$val}" 2>/dev/null
            ;;
        4)
            read -p "输入新的输出路径: " new_path
            [ -n "$new_path" ] && curl -X PUT "http://localhost:$WEB_PORT/api/settings/strm" \
                -H "Content-Type: application/json" -d "{\"output_path\":\"$new_path\"}" 2>/dev/null
            ;;
    esac
}

configure_qos() {
    echo -e "${CYAN}=== QoS / 线程设置 ===${NC}"
    echo "当前设置:"
    curl -s "http://localhost:$WEB_PORT/api/settings/qos" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
cfg = data.get('config', {})
print(f\"  线程模式: {cfg.get('threading_mode', 'multi')}\")
print(f\"  线程池大小: {cfg.get('thread_pool_size', 4)}\")
print(f\"  QPS: {cfg.get('qps', 5)}\")
print(f\"  最大并发: {cfg.get('max_concurrent', 3)}\")
" 2>/dev/null || warn "无法获取设置"
    
    echo
    echo "1. 单线程模式"
    echo "2. 多线程模式"
    echo "3. 修改 QPS 限制"
    read -p "选择: " choice
    
    case $choice in
        1) info "请通过 Web 界面修改线程模式" ;;
        2) info "请通过 Web 界面修改线程模式" ;;
        3) 
            read -p "输入新的 QPS 值: " qps
            [ -n "$qps" ] && curl -X PUT "http://localhost:$WEB_PORT/api/settings/qos" \
                -H "Content-Type: application/json" -d "{\"qps\":$qps}" 2>/dev/null
            ;;
    esac
}

trigger_scan() {
    info "触发 STRM 扫描..."
    
    ensure_runtime_config
    PORT=${OPENLIST2STRM_WEB_PORT:-9527}
    TOKEN=${WEB_AUTH_API_TOKEN:-}
    
    if [ -n "$TOKEN" ]; then
        read -p "扫描路径 [/115/流媒体]: " SCAN_PATH
        SCAN_PATH=${SCAN_PATH:-/115/流媒体}
        
        curl -X POST "http://localhost:$PORT/api/scan" \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"folders\": [\"$SCAN_PATH\"]}"
        echo
    else
        warn "未找到 API Token，请通过 Web 界面触发扫描"
    fi
}

show_strm_files() {
    STRM_DIR="$BASE_DIR/movie/strm"
    echo -e "${CYAN}=== STRM 文件统计 ===${NC}"
    if [ -d "$STRM_DIR" ]; then
        echo "目录: $STRM_DIR"
        echo "文件数: $(find "$STRM_DIR" -name "*.strm" 2>/dev/null | wc -l)"
        echo
        echo "最近生成 (1小时内):"
        find "$STRM_DIR" -name "*.strm" -mmin -60 2>/dev/null | head -10
    else
        warn "STRM 目录不存在"
    fi
}

# ===== 任务管理 (v1.2.0) =====
manage_tasks() {
    echo -e "${CYAN}=== 定时任务管理 (现代化调度) ===${NC}"
    echo "1. 查看所有任务"
    echo "2. 创建新任务 (简化版)"
    echo "3. 删除任务"
    echo "4. 启用/停用任务"
    echo "5. 暂停/恢复任务"
    echo "6. 立即执行任务"
    echo "7. 调度类型参考"
    read -p "选择: " choice
    
    case $choice in
        1) # 列出任务
            curl -s "http://localhost:$WEB_PORT/api/tasks" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tasks = data.get('tasks', [])
if not tasks:
    print('无定时任务')
else:
    for t in tasks:
        status = '启用' if t.get('enabled') else '停用'
        if t.get('paused'): status = '暂停'
        one_time = ' [一次性]' if t.get('one_time') else ''
        print(f\"ID: {t['id']}\")
        print(f\"  名称: {t.get('name')}\")
        print(f\"  文件夹: {t.get('folder') or '全部'}\")
        print(f\"  类型: {t.get('schedule_type')}\")
        print(f\"  值: {t.get('schedule_value')}\")
        print(f\"  状态: {status}{one_time}\")
        print(f\"  下次运行: {t.get('next_run', 'N/A')}\")
        print()
" 2>/dev/null || error "无法获取任务列表"
            ;;
        2) # 创建任务
            read -p "任务名称 (如: 自动扫描): " name
            read -p "扫描文件夹 (留空则扫描所有): " folder
            echo "选择调度类型:"
            echo "  1. 间隔 (分钟)"
            echo "  2. 每日 (HH:MM)"
            echo "  3. Cron (标准 Cron 表达式)"
            read -p "请选择 [1-3]: " type_choice
            
            case $type_choice in
                1) 
                    stype="interval"
                    read -p "间隔分钟数 [30]: " sval
                    sval=${sval:-30}
                    ;;
                2)
                    stype="daily"
                    read -p "每日执行时间 [04:00]: " sval
                    sval=${sval:-"04:00"}
                    ;;
                3)
                    stype="cron"
                    read -p "Cron 表达式 [0 2 * * *]: " sval
                    sval=${sval:-"0 2 * * *"}
                    ;;
                *) error "无效选择"; return ;;
            esac
            
            read -p "是否一次性任务? [y/N]: " one_time
            ot="false"
            [[ "$one_time" =~ ^[Yy]$ ]] && ot="true"
            
            curl -X POST "http://localhost:$WEB_PORT/api/tasks" \
                -H "Content-Type: application/json" \
                -d "{\"name\":\"$name\",\"folder\":\"$folder\",\"schedule_type\":\"$stype\",\"schedule_value\":\"$sval\",\"one_time\":$ot}" 2>/dev/null
            echo
            log "任务已创建"
            ;;
        3) # 删除任务
            read -p "输入任务 ID: " task_id
            curl -X DELETE "http://localhost:$WEB_PORT/api/tasks/$task_id" 2>/dev/null
            echo
            ;;
        4) # 启用/停用
            read -p "输入任务 ID: " task_id
            echo "1. 启用  2. 停用"
            read -p "选择: " action
            if [ "$action" = "1" ]; then
                curl -X POST "http://localhost:$WEB_PORT/api/tasks/$task_id/enable" 2>/dev/null
            else
                curl -X POST "http://localhost:$WEB_PORT/api/tasks/$task_id/disable" 2>/dev/null
            fi
            echo
            ;;
        5) # 暂停/恢复
            read -p "输入任务 ID: " task_id
            echo "1. 暂停  2. 恢复"
            read -p "选择: " action
            if [ "$action" = "1" ]; then
                curl -X POST "http://localhost:$WEB_PORT/api/tasks/$task_id/pause" 2>/dev/null
            else
                curl -X POST "http://localhost:$WEB_PORT/api/tasks/$task_id/resume" 2>/dev/null
            fi
            echo
            ;;
        6) # 立即执行
            read -p "输入任务 ID: " task_id
            curl -X POST "http://localhost:$WEB_PORT/api/tasks/$task_id/run" 2>/dev/null
            echo
            ;;
        7) # 调度参考
            echo -e "${CYAN}调度类型说明:${NC}"
            echo "  interval - 固定间隔运行。值: 1-1440 (分钟)"
            echo "  daily    - 每天固定时间。值: HH:MM (如 04:30)"
            echo "  cron     - 标准 Cron 表达式。值: * * * * * (分 时 日 月 周)"
            echo "  once     - 立即加入队列并运行一次。"
            echo
            ;;
    esac
}

# ===== 清理功能 (v1.1.0) =====
run_cleanup() {
    echo -e "${CYAN}=== 清理功能 ===${NC}"
    echo "1. 预览清理 (不删除)"
    echo "2. 执行清理"
    echo "3. 仅清理空目录"
    echo "4. 仅清理无效软链接"
    echo "5. 查看 STRM 目录统计"
    read -p "选择: " choice
    
    case $choice in
        1) # 预览
            info "正在扫描..."
            curl -s -X POST "http://localhost:$WEB_PORT/api/cleanup/preview" \
                -H "Content-Type: application/json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"无效文件夹: {len(data.get('invalid_folders', []))}\")
print(f\"无效软链接: {len(data.get('broken_symlinks', []))}\")
print(f\"空目录: {len(data.get('empty_dirs', []))}\")
print(f\"总问题数: {data.get('total_issues', 0)}\")
" 2>/dev/null
            ;;
        2) # 执行清理
            warn "将删除无效软链接和空目录!"
            read -p "确定执行清理? [y/N]: " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                curl -s -X POST "http://localhost:$WEB_PORT/api/cleanup" \
                    -H "Content-Type: application/json" \
                    -d '{"dry_run":false}' | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"已删除: {data.get('deleted_count', 0)} 项\")
if data.get('errors'):
    print('错误:')
    for e in data['errors']:
        print(f\"  - {e}\")
"
            fi
            ;;
        3) # 空目录
            curl -s -X POST "http://localhost:$WEB_PORT/api/cleanup/empty-dirs?dry_run=true" | python3 -c "
import sys, json
data = json.load(sys.stdin)
dirs = data.get('empty_directories', [])
print(f\"发现 {len(dirs)} 个空目录\")
for d in dirs[:10]:
    print(f\"  {d}\")
if len(dirs) > 10:
    print(f\"  ... 还有 {len(dirs)-10} 个\")
"
            ;;
        4) # 软链接
            curl -s -X POST "http://localhost:$WEB_PORT/api/cleanup/symlinks?dry_run=true" | python3 -c "
import sys, json
data = json.load(sys.stdin)
links = data.get('broken_symlinks', [])
print(f\"发现 {len(links)} 个无效软链接\")
for l in links[:10]:
    print(f\"  {l}\")
"
            ;;
        5) # 统计
            curl -s "http://localhost:$WEB_PORT/api/cleanup/stats" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"路径: {data.get('path')}\")
print(f\"STRM 文件数: {data.get('strm_files', 0)}\")
print(f\"总文件数: {data.get('total_files', 0)}\")
print(f\"总目录数: {data.get('total_dirs', 0)}\")
print(f\"总大小: {data.get('total_size_bytes', 0) / 1024:.2f} KB\")
"
            ;;
    esac
}

# ===== Emby 配置 (v1.1.0) =====
configure_emby() {
    echo -e "${CYAN}=== Emby 通知配置 ===${NC}"
    echo
    info "获取 API Key 教程:"
    echo "  Emby: 设置 → 高级 → API 密钥 → 新建应用程序"
    echo
    
    echo "当前设置:"
    curl -s "http://localhost:$WEB_PORT/api/settings/emby" 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"  启用: {'是' if data.get('enabled') else '否'}\")
print(f\"  地址: {data.get('host', '未设置')}\")
print(f\"  API Key: {data.get('api_key', '未设置')}\")
print(f\"  媒体库ID: {data.get('library_id') or '全部'}\")
" 2>/dev/null || warn "无法获取设置"
    
    echo
    echo "1. 配置 Emby 连接"
    echo "2. 测试连接"
    echo "3. 启用/停用通知"
    echo "4. 获取媒体库列表"
    read -p "选择: " choice
    
    case $choice in
        1)
            read -p "Emby 地址 (如 http://emby:8096): " host
            read -p "API Key: " api_key
            read -p "媒体库 ID (留空扫描全部): " lib_id
            
            curl -X PUT "http://localhost:$WEB_PORT/api/settings/emby" \
                -H "Content-Type: application/json" \
                -d "{\"host\":\"$host\",\"api_key\":\"$api_key\",\"library_id\":\"$lib_id\",\"enabled\":true}" 2>/dev/null
            echo
            log "Emby 配置已保存"
            ;;
        2)
            info "测试 Emby 连接..."
            curl -s -X POST "http://localhost:$WEB_PORT/api/settings/emby/test" | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('success'):
    print(f\"连接成功! 服务器: {data.get('server_name')} (v{data.get('version')})\")
else:
    print(f\"连接失败: {data.get('error', '未知错误')}\")
" 2>/dev/null
            ;;
        3)
            echo "1. 启用  2. 停用"
            read -p "选择: " action
            val="true"
            [ "$action" = "2" ] && val="false"
            curl -X PUT "http://localhost:$WEB_PORT/api/settings/emby" \
                -H "Content-Type: application/json" \
                -d "{\"enabled\":$val}" 2>/dev/null
            echo
            ;;
        4)
            curl -s "http://localhost:$WEB_PORT/api/settings/emby/libraries" | python3 -c "
import sys, json
data = json.load(sys.stdin)
libs = data.get('libraries', [])
if not libs:
    print('未获取到媒体库')
else:
    for lib in libs:
        print(f\"ID: {lib['id']}  名称: {lib['name']}  类型: {lib.get('type', 'unknown')}\")
" 2>/dev/null
            ;;
    esac
}

# ===== Nginx 配置 =====
setup_nginx() {
    echo -e "${CYAN}=== Nginx 配置 (Certbot) ===${NC}"
    
    # 安装 Nginx 和 Certbot
    if ! command -v nginx &> /dev/null; then
        log "正在安装 Nginx..."
        apt-get update && apt-get install -y nginx
    fi
    if ! command -v certbot &> /dev/null; then
        log "正在安装 Certbot..."
        apt-get update && apt-get install -y certbot python3-certbot-nginx
    fi
    if systemctl list-unit-files | grep -q "^certbot.timer"; then
        systemctl enable --now certbot.timer >/dev/null 2>&1 || true
        info "已启用 certbot.timer（自动续期）"
    else
        warn "未检测到 certbot.timer，请确认系统自动续期策略"
    fi
    
    if [ -f "$GLOBAL_CONFIG" ]; then
        DOMAIN=$(grep -E "^domain:" "$GLOBAL_CONFIG" | awk '{print $2}' | tr -d '"' | head -1)
    fi
    
    read -p "域名 [openlist2strm.${DOMAIN:-example.com}]: " INPUT_DOMAIN
    SUBDOMAIN=${INPUT_DOMAIN:-openlist2strm.${DOMAIN:-example.com}}
    
    read -p "HTTPS 端口 [443]: " HTTPS_PORT
    HTTPS_PORT=${HTTPS_PORT:-443}
    
    NGINX_CONF="/etc/nginx/sites-available/openlist2strm"
    
    # 基础 HTTP 配置
    cat > "$NGINX_CONF" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $SUBDOMAIN;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / {
        proxy_pass http://127.0.0.1:${WEB_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
    
    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/openlist2strm 2>/dev/null
    
    if nginx -t 2>/dev/null; then
        nginx -s reload
        log "Nginx 基础配置成功，开始申请证书..."
        
        # 申请证书
        certbot --nginx -d "$SUBDOMAIN" --non-interactive --agree-tos --register-unsafely-without-email
        
        if [ $? -eq 0 ]; then
            log "证书申请成功！"
            
            # 更新为 HTTPS 配置
            cat > "$NGINX_CONF" <<EOF
# OpenList2STRM Nginx 配置 (由 openlist2strm.sh 自动生成)
server {
    listen 80;
    listen [::]:80;
    server_name $SUBDOMAIN;
    return 301 https://\$host\$request_uri;
}
server {
    listen ${HTTPS_PORT} ssl;
    listen [::]:${HTTPS_PORT} ssl;
    
    server_name $SUBDOMAIN;
    
    ssl_certificate /etc/letsencrypt/live/$SUBDOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$SUBDOMAIN/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:${WEB_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
    }
}
EOF
            nginx -s reload
            log "HTTPS 配置成功！"
            info "访问地址: https://$SUBDOMAIN:$HTTPS_PORT"
        else
            warn "证书申请失败，请手动检查: certbot --nginx -d $SUBDOMAIN"
        fi
    else
        error "Nginx 配置语法错误"
    fi
}

# ===== 卸载服务 =====
uninstall_service() {
    echo -e "${CYAN}=== 卸载 OpenList2STRM ===${NC}"
    
    if [ -f "$GLOBAL_CONFIG" ]; then
        DOMAIN=$(grep -E "^domain:" "$GLOBAL_CONFIG" | awk '{print $2}' | tr -d '"' | head -1)
    fi
    FULL_DOMAIN="openlist2strm.${DOMAIN:-example.com}"
    
    read -p "是否停止并删除 Docker 容器? [y/N]: " del_container
    if [[ "$del_container" =~ ^[Yy]$ ]]; then
        docker stop $CONTAINER 2>/dev/null
        docker rm $CONTAINER 2>/dev/null
        log "已删除容器 $CONTAINER"
    fi
    
    read -p "是否删除 Nginx 配置? [y/N]: " del_nginx
    if [[ "$del_nginx" =~ ^[Yy]$ ]]; then
        rm -f "/etc/nginx/sites-enabled/openlist2strm"
        rm -f "/etc/nginx/sites-available/openlist2strm"
        nginx -s reload 2>/dev/null
        log "已删除 Nginx 配置: openlist2strm"
    fi
    
    read -p "是否删除 SSL 证书? [y/N]: " del_cert
    if [[ "$del_cert" =~ ^[Yy]$ ]]; then
        SUBDOMAIN=$(grep "server_name" "/etc/nginx/sites-available/openlist2strm" 2>/dev/null | head -1 | awk '{print $2}' | tr -d ';')
        CERT_NAME=${SUBDOMAIN:-$FULL_DOMAIN}
        if [ -d "$CERT_DIR/$CERT_NAME" ]; then
            certbot delete --cert-name "$CERT_NAME" --non-interactive
            log "已删除 SSL 证书: $CERT_NAME"
        fi
    fi
    
    read -p "是否删除本地配置和数据目录? [y/N]: " del_local
    if [[ "$del_local" =~ ^[Yy]$ ]]; then
        rm -rf "$BASE_DIR/openlist2strm"
        log "已删除本地配置目录"
    fi
    
    log "卸载完成"
}

# ===== 单独安装 =====
install_standalone() {
    echo -e "${CYAN}=== 单独安装 OpenList2STRM v$VERSION ===${NC}"
    
    if ! command -v docker &>/dev/null; then
        log "正在安装 Docker..."
        curl -fsSL https://get.docker.com | bash
        systemctl enable --now docker
    fi
    
    read -p "安装目录 [$BASE_DIR]: " INPUT_DIR
    BASE_DIR=${INPUT_DIR:-$BASE_DIR}
    APP_DIR="$BASE_DIR/openlist2strm"
    CONFIG_DIR="$APP_DIR/config"
    CONFIG_FILE="$CONFIG_DIR/config.yml"
    ENV_FILE="$APP_DIR/.env"
    
    read -p "Web 端口 [$WEB_PORT]: " INPUT_PORT
    WEB_PORT=${INPUT_PORT:-$WEB_PORT}
    
    read -p "OpenList 地址 [http://openlist:5244]: " ALIST_URL
    OPENLIST_HOST=${ALIST_URL:-http://openlist:5244}
    read -sp "OpenList Token: " OPENLIST_TOKEN
    echo
    
    read -p "源路径 [/115/流媒体]: " SOURCE_PATHS
    PATHS_SOURCE=${SOURCE_PATHS:-/115/流媒体}
    
    # Emby 配置
    echo
    read -p "是否配置 Emby 通知? [y/N]: " config_emby
    EMBY_ENABLED="false"
    EMBY_HOST="${EMBY_HOST:-}"
    EMBY_API_KEY="${EMBY_API_KEY:-}"
    if [[ "$config_emby" =~ ^[Yy]$ ]]; then
        read -p "Emby 地址 (如 http://emby:8096): " EMBY_HOST
        read -p "Emby API Key: " EMBY_API_KEY
        EMBY_ENABLED="true"
    fi
    
    # 创建目录
    OPENLIST2STRM_WEB_PORT="$WEB_PORT"
    OPENLIST2STRM_BIND_IP="127.0.0.1"
    OPENLIST2STRM_CONFIG_DIR="./config"
    OPENLIST2STRM_DATA_DIR="./data"
    OPENLIST2STRM_STRM_DIR="${BASE_DIR}/movie/strm"
    PATHS_OUTPUT="/strm"
    STRM_MODE="path"
    STRM_URL_ENCODE="true"
    STRM_KEEP_STRUCTURE="true"
    STRM_OUTPUT_PATH="/strm"
    WEB_AUTH_ENABLED="true"
    WEB_AUTH_USERNAME="admin"
    WEB_AUTH_PASSWORD=""
    WEB_AUTH_API_TOKEN="$(openssl rand -hex 16)"
    CONFIG_PATH="/config/config.yml"
    TZ="Asia/Shanghai"
    LOG_LEVEL="INFO"
    LOG_RETENTION_DAYS="7"
    LOG_COLORIZE="true"

    mkdir -p "$APP_DIR" "$CONFIG_DIR" "$BASE_DIR/movie/strm"
    sync_local_source || return 1
    ensure_local_build_service
    write_env_file
    write_yaml_config_from_env

    ensure_runtime_config
    log "构建并启动服务..."
    dc build "$SERVICE"
    dc up -d --no-deps "$SERVICE"
    
    echo
    log "OpenList2STRM v$VERSION 安装完成！"
    echo -e "访问地址: ${CYAN}http://localhost:$WEB_PORT${NC}"
    echo -e "API Token: ${YELLOW}${WEB_AUTH_API_TOKEN}${NC}"
    echo
    info "新功能提示:"
    echo "  - 多任务调度: 可创建多个定时任务"
    echo "  - Emby 通知: 扫描完成自动刷新媒体库"
    echo "  - 清理功能: 清理无效文件和软链接"
    echo "  - STRM 规则: 路径/直链模式切换"
}

# ===== 命令行处理 =====
case "$1" in
    start)   start_service ;;
    stop)    stop_service ;;
    restart) restart_service ;;
    update)  update_service ;;
    status)  show_status ;;
    logs)    docker logs -f --tail=100 $CONTAINER ;;
    config)  edit_config ;;
    scan)    trigger_scan ;;
    strm)    show_strm_files ;;
    install) install_standalone ;;
    tasks)   manage_tasks ;;
    cleanup) run_cleanup ;;
    emby)    configure_emby ;;
    nginx)   setup_nginx ;;
    uninstall) uninstall_service ;;
    *)
        while true; do
            show_menu
            read -p "请选择 [0-16]: " choice
            echo
            case $choice in
                1) start_service ;;
                2) stop_service ;;
                3) restart_service ;;
                4) update_service ;;
                5) show_status ;;
                6) show_logs ;;
                7) edit_config ;;
                8) trigger_scan ;;
                9) show_strm_files ;;
                10) install_standalone ;;
                11) edit_config ;;
                12) manage_tasks ;;
                13) run_cleanup ;;
                14) configure_emby ;;
                15) setup_nginx ;;
                16) uninstall_service ;;
                0) exit 0 ;;
                *) error "无效选择" ;;
            esac
            echo
            read -p "按回车继续..."
        done
        ;;
esac

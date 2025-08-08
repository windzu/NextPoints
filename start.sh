#!/bin/bash

# NextPoints 完整服务启动脚本
# 包含 Redis、Celery Workers、FastAPI 服务等所有组件

set -e  # 遇到错误时退出

# 配置变量
REDIS_PORT=6379
FASTAPI_PORT=10081
FLOWER_PORT=5555
LOG_DIR="logs"
PID_DIR="pids"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 创建必要的目录
create_directories() {
    log_step "Creating necessary directories..."
    mkdir -p $LOG_DIR $PID_DIR /tmp/exports
    log_info "Directories created successfully"
}

# 检查依赖
check_dependencies() {
    log_step "Checking dependencies..."
    
    # 检查 Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 is not installed"
        exit 1
    fi
    
    # 检查 pip 包
    if ! python3 -c "import fastapi, celery, redis" &> /dev/null; then
        log_warn "Some Python packages are missing. Installing..."
        pip3 install -r requirements.txt
        if [ -f requirements_celery.txt ]; then
            pip3 install -r requirements_celery.txt
        fi
    fi
    
    log_info "All dependencies are available"
}

# 检查端口是否被占用
check_port() {
    local port=$1
    local service=$2
    
    if netstat -tuln | grep ":$port " > /dev/null 2>&1; then
        log_warn "$service port $port is already in use"
        return 1
    fi
    return 0
}


# 启动 Celery Worker
start_celery_worker() {
    log_step "Starting Celery Worker..."
    
    export PYTHONPATH="${PWD}:${PYTHONPATH}"
    
    celery -A app.celery_app worker \
        --loglevel=info \
        --concurrency=4 \
        --queues=export,cleanup \
        --logfile=$LOG_DIR/celery_worker.log \
        --pidfile=$PID_DIR/celery_worker.pid \
        --detach
    
    if [ $? -eq 0 ]; then
        log_info "Celery Worker started successfully"
    else
        log_error "Failed to start Celery Worker"
        exit 1
    fi
}

# 启动 Celery Beat
start_celery_beat() {
    log_step "Starting Celery Beat..."
    
    export PYTHONPATH="${PWD}:${PYTHONPATH}"
    
    celery -A app.celery_app beat \
        --loglevel=info \
        --logfile=$LOG_DIR/celery_beat.log \
        --pidfile=$PID_DIR/celery_beat.pid \
        --detach
    
    if [ $? -eq 0 ]; then
        log_info "Celery Beat started successfully"
    else
        log_error "Failed to start Celery Beat"
        exit 1
    fi
}

# 启动 Flower 监控
start_flower() {
    log_step "Starting Flower monitoring..."
    
    if ! command -v flower &> /dev/null; then
        log_warn "Flower is not installed, skipping..."
        return 0
    fi
    
    if ! check_port $FLOWER_PORT "Flower"; then
        log_warn "Flower port $FLOWER_PORT is in use, skipping..."
        return 0
    fi
    
    export PYTHONPATH="${PWD}:${PYTHONPATH}"
    
    nohup celery -A app.celery_app flower \
        --port=$FLOWER_PORT \
        --logging=info \
        > $LOG_DIR/flower.log 2>&1 &
    
    echo $! > $PID_DIR/flower.pid
    log_info "Flower started successfully on http://localhost:$FLOWER_PORT"
}

# 启动 FastAPI 服务
start_fastapi() {
    log_step "Starting FastAPI server..."
    
    if ! check_port $FASTAPI_PORT "FastAPI"; then
        log_warn "FastAPI port $FASTAPI_PORT is in use"
        read -p "Do you want to use a different port? (y/N): " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            read -p "Enter port number: " NEW_PORT
            FASTAPI_PORT=$NEW_PORT
        else
            log_error "Cannot start FastAPI on port $FASTAPI_PORT"
            exit 1
        fi
    fi
    
    export PYTHONPATH="${PWD}:${PYTHONPATH}"
    
    # 使用 uvicorn 启动 FastAPI
    nohup uvicorn app.main:app \
        --host 0.0.0.0 \
        --port $FASTAPI_PORT \
        --log-level info \
        --access-log \
        > $LOG_DIR/fastapi.log 2>&1 &
    
    echo $! > $PID_DIR/fastapi.pid
    
    # 等待 FastAPI 启动
    for i in {1..15}; do
        if curl -s http://localhost:$FASTAPI_PORT/docs > /dev/null 2>&1; then
            log_info "FastAPI started successfully on http://localhost:$FASTAPI_PORT"
            return 0
        fi
        sleep 1
    done
    
    log_error "Failed to start FastAPI"
    exit 1
}

# 显示服务状态
show_status() {
    echo ""
    log_step "Service Status Summary:"
    echo "================================"
    
    # Celery Worker 状态
    if [ -f $PID_DIR/celery_worker.pid ] && kill -0 $(cat $PID_DIR/celery_worker.pid) 2>/dev/null; then
        echo -e "Celery Worker: ${GREEN}✓ Running${NC} (PID: $(cat $PID_DIR/celery_worker.pid))"
    else
        echo -e "Celery Worker: ${RED}✗ Not running${NC}"
    fi
    
    # Celery Beat 状态
    if [ -f $PID_DIR/celery_beat.pid ] && kill -0 $(cat $PID_DIR/celery_beat.pid) 2>/dev/null; then
        echo -e "Celery Beat:   ${GREEN}✓ Running${NC} (PID: $(cat $PID_DIR/celery_beat.pid))"
    else
        echo -e "Celery Beat:   ${RED}✗ Not running${NC}"
    fi
    
    # Flower 状态
    if [ -f $PID_DIR/flower.pid ] && kill -0 $(cat $PID_DIR/flower.pid) 2>/dev/null; then
        echo -e "Flower:        ${GREEN}✓ Running${NC} (http://localhost:$FLOWER_PORT)"
    else
        echo -e "Flower:        ${YELLOW}- Not started${NC}"
    fi
    
    # FastAPI 状态
    if [ -f $PID_DIR/fastapi.pid ] && kill -0 $(cat $PID_DIR/fastapi.pid) 2>/dev/null; then
        echo -e "FastAPI:       ${GREEN}✓ Running${NC} (http://localhost:$FASTAPI_PORT)"
    else
        echo -e "FastAPI:       ${RED}✗ Not running${NC}"
    fi
    
    echo "================================"
}

# 显示使用说明
show_usage() {
    echo ""
    log_step "Usage Information:"
    echo "================================"
    echo "API Documentation: http://localhost:$FASTAPI_PORT/docs"
    echo "Flower Monitoring: http://localhost:$FLOWER_PORT"
    echo ""
    echo "Log files location: $LOG_DIR/"
    echo "PID files location: $PID_DIR/"
    echo ""
    echo "To stop all services: ./stop.sh"
    echo "To restart services:  ./restart.sh"
    echo "To view logs:        tail -f $LOG_DIR/<service>.log"
    echo "================================"
}

# 主函数
main() {
    echo -e "${BLUE}"
    echo "================================================"
    echo "    NextPoints Service Startup Script"
    echo "================================================"
    echo -e "${NC}"
    
    # 检查是否以 root 身份运行
    if [ "$EUID" -eq 0 ]; then
        log_warn "Running as root is not recommended"
    fi
    
    # 执行启动步骤
    create_directories
    check_dependencies
    start_celery_worker
    start_celery_beat
    start_flower
    start_fastapi
    
    # 等待所有服务完全启动
    log_step "Waiting for all services to fully initialize..."
    sleep 3
    
    # 显示状态和使用说明
    show_status
    show_usage
    
    echo ""
    log_info "All services started successfully! 🚀"
    echo ""
}

# 错误处理
cleanup_on_error() {
    log_error "Startup failed. Cleaning up..."
    ./stop.sh 2>/dev/null || true
    exit 1
}

trap cleanup_on_error ERR

# 执行主函数
main "$@"

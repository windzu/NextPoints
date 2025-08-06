#!/bin/bash

# NextPoints 服务停止脚本
# 停止所有相关服务并清理进程

set -e

# 配置变量
LOG_DIR="logs"
PID_DIR="pids"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# 停止单个服务
stop_service() {
    local service_name=$1
    local pid_file="$PID_DIR/${service_name}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_step "Stopping $service_name (PID: $pid)..."
            if kill "$pid" 2>/dev/null; then
                # 等待进程结束
                for i in {1..10}; do
                    if ! kill -0 "$pid" 2>/dev/null; then
                        log_info "$service_name stopped successfully"
                        rm -f "$pid_file"
                        return 0
                    fi
                    sleep 1
                done
                
                # 如果还没停止，强制杀死
                log_warn "Force killing $service_name..."
                kill -9 "$pid" 2>/dev/null || true
                rm -f "$pid_file"
                log_info "$service_name force stopped"
            else
                log_warn "Failed to stop $service_name"
                rm -f "$pid_file"
            fi
        else
            log_warn "$service_name PID file exists but process not running"
            rm -f "$pid_file"
        fi
    else
        log_warn "$service_name PID file not found"
    fi
}

# 停止 Redis（如果是我们启动的）
stop_redis() {
    local redis_pid_file="$PID_DIR/redis.pid"
    
    if [ -f "$redis_pid_file" ]; then
        log_step "Stopping Redis server..."
        local redis_pid=$(cat "$redis_pid_file")
        if kill -0 "$redis_pid" 2>/dev/null; then
            redis-cli shutdown 2>/dev/null || kill "$redis_pid" 2>/dev/null || true
            rm -f "$redis_pid_file"
            log_info "Redis stopped successfully"
        else
            rm -f "$redis_pid_file"
            log_warn "Redis PID file exists but process not running"
        fi
    else
        # 尝试通过 redis-cli 关闭
        if redis-cli ping > /dev/null 2>&1; then
            log_step "Stopping Redis server..."
            redis-cli shutdown 2>/dev/null || true
            log_info "Redis stopped successfully"
        fi
    fi
}

# 强制清理相关进程
force_cleanup() {
    log_step "Performing force cleanup..."
    
    # 杀死所有相关进程
    pkill -f "celery.*app.celery_app" 2>/dev/null || true
    pkill -f "uvicorn.*app.main" 2>/dev/null || true
    pkill -f "flower" 2>/dev/null || true
    
    # 清理 PID 文件
    rm -f $PID_DIR/*.pid 2>/dev/null || true
    
    log_info "Force cleanup completed"
}

# 显示停止状态
show_stop_status() {
    echo ""
    log_step "Service Stop Status:"
    echo "================================"
    
    local all_stopped=true
    
    # 检查各服务状态
    services=("redis" "celery_worker" "celery_beat" "flower" "fastapi")
    
    for service in "${services[@]}"; do
        local pid_file="$PID_DIR/${service}.pid"
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            if kill -0 "$pid" 2>/dev/null; then
                echo -e "$service: ${RED}✗ Still running${NC} (PID: $pid)"
                all_stopped=false
            else
                echo -e "$service: ${GREEN}✓ Stopped${NC}"
            fi
        else
            echo -e "$service: ${GREEN}✓ Stopped${NC}"
        fi
    done
    
    echo "================================"
    
    if [ "$all_stopped" = true ]; then
        log_info "All services stopped successfully! 🛑"
    else
        log_warn "Some services are still running. Use --force to force stop."
    fi
}

# 清理日志文件（可选）
cleanup_logs() {
    if [ "$1" = "--clean-logs" ]; then
        log_step "Cleaning log files..."
        rm -f $LOG_DIR/*.log 2>/dev/null || true
        log_info "Log files cleaned"
    fi
}

# 主函数
main() {
    echo -e "${BLUE}"
    echo "================================================"
    echo "    NextPoints Service Stop Script"
    echo "================================================"
    echo -e "${NC}"
    
    # 解析参数
    local force_stop=false
    local clean_logs=false
    
    for arg in "$@"; do
        case $arg in
            --force)
                force_stop=true
                ;;
            --clean-logs)
                clean_logs=true
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --force        Force stop all services"
                echo "  --clean-logs   Remove all log files"
                echo "  --help         Show this help message"
                echo ""
                exit 0
                ;;
        esac
    done
    
    # 创建必要目录
    mkdir -p $PID_DIR
    
    # 按顺序停止服务
    stop_service "fastapi"
    stop_service "flower"
    stop_service "celery_beat"
    stop_service "celery_worker"
    stop_redis
    
    # 如果指定了强制停止
    if [ "$force_stop" = true ]; then
        force_cleanup
    fi
    
    # 清理日志文件
    if [ "$clean_logs" = true ]; then
        cleanup_logs --clean-logs
    fi
    
    # 显示停止状态
    show_stop_status
    
    echo ""
}

# 执行主函数
main "$@"

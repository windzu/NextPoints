#!/bin/bash

# NextPoints 服务重启脚本

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

main() {
    echo -e "${BLUE}"
    echo "================================================"
    echo "    NextPoints Service Restart Script"
    echo "================================================"
    echo -e "${NC}"
    
    log_step "Stopping all services..."
    ./stop_nextpoints.sh --force
    
    echo ""
    log_step "Waiting 3 seconds before restart..."
    sleep 3
    
    log_step "Starting all services..."
    ./start_nextpoints.sh
    
    echo ""
    log_info "Restart completed! 🔄"
}

main "$@"

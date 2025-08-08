# NextPoints 异步导出系统使用指南

## 概述

基于 Celery 的异步导出系统，支持将 NextPoint 格式数据转换为 NuScenes 等标准格式。

## 系统架构

```
FastAPI Application
    ↓
Export Service (管理导出任务)
    ↓
Celery Task Queue (Redis)
    ↓
Celery Workers (执行实际转换)
    ↓
文件存储 (/tmp/exports/)
```

## 安装和启动

### 1. 安装依赖

```bash
# 安装 Celery 相关依赖
pip install -r requirements_celery.txt

# 或单独安装
pip install celery[redis] redis flower
```

### 2. 启动 Redis

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis-server

# 或使用 Docker
docker run -d -p 6379:6379 redis:alpine
```

### 3. 启动 Celery 服务

```bash
# 启动所有 Celery 服务
./start_celery.sh

# 或手动启动
celery -A app.celery_app worker --loglevel=info --concurrency=4
celery -A app.celery_app beat --loglevel=info
celery -A app.celery_app flower --port=5555  # 可选监控界面
```

### 4. 停止服务

```bash
./stop_celery.sh
```

## API 使用示例

### 1. 启动导出任务

```bash
curl -X POST "http://localhost:8000/api/projects/my_project/export/nuscenes" \
  -H "Content-Type: application/json" \
  -d '{
    "export_format": "nuscenes_v1.0",
    "coordinate_system": "ego_vehicle",
    "annotation_filter": {
      "object_types": ["car", "pedestrian", "bicycle"],
      "min_points": 10
    },
    "export_options": {
      "include_images": true,
      "include_pointcloud": true,
      "compress_output": true
    }
  }'
```

响应：

```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "pending",
  "message": "Export task created for project 'my_project'",
  "created_at": "2025-08-06T10:30:00Z",
  "estimated_duration": 300
}
```

### 2. 查询任务状态

```bash
curl "http://localhost:8000/api/projects/export/tasks/abc123-def456-ghi789"
```

响应：

```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "processing",
  "progress": 45.5,
  "current_step": "Processing frame 455/1000",
  "message": "Converting frame 1708676399593999872",
  "created_at": "2025-08-06T10:30:00Z",
  "started_at": "2025-08-06T10:30:05Z"
}
```

### 3. 下载结果

```bash
curl -O "http://localhost:8000/api/projects/export/download/abc123-def456-ghi789"
```

### 4. 取消任务

```bash
curl -X DELETE "http://localhost:8000/api/projects/export/tasks/abc123-def456-ghi789"
```

## 监控和管理

### Flower 监控界面

访问 `http://localhost:5555` 查看：

- 活跃任务
- 任务历史
- Worker 状态
- 队列统计

### 命令行监控

```bash
# 查看活跃任务
celery -A app.celery_app inspect active

# 查看队列状态
celery -A app.celery_app inspect stats

# 查看注册的任务
celery -A app.celery_app inspect registered
```

## 配置选项

### 环境变量

```bash
# Redis 配置
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/0"

# 任务配置
export CELERY_TASK_TIME_LIMIT=3600
export CELERY_WORKER_CONCURRENCY=4
```

### Celery 配置

在 `app/celery_app.py` 中可以调整：

- 任务超时时间
- Worker 并发数
- 队列配置
- 重试策略

## 生产环境部署

### 1. 使用 Supervisor 管理进程

```ini
[program:celery_worker]
command=celery -A app.celery_app worker --loglevel=info --concurrency=4
directory=/path/to/nextpoints
user=nextpoints
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/worker.log

[program:celery_beat]
command=celery -A app.celery_app beat --loglevel=info
directory=/path/to/nextpoints
user=nextpoints
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/beat.log
```

### 2. 使用 Docker Compose

```yaml
version: "3.8"
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"

  celery_worker:
    build: .
    command: celery -A app.celery_app worker --loglevel=info --concurrency=4
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
    volumes:
      - ./exports:/tmp/exports

  celery_beat:
    build: .
    command: celery -A app.celery_app beat --loglevel=info
    depends_on:
      - redis
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
```

## 故障排除

### 常见问题

1. **Redis 连接失败**

   ```
   kombu.exceptions.OperationalError: [Errno 111] Connection refused
   ```

   解决：确保 Redis 服务正在运行

2. **任务长时间 PENDING**

   - 检查 Worker 是否运行
   - 确认队列配置正确

3. **内存不足**
   - 减少 Worker 并发数
   - 增加 swap 空间
   - 实现分批处理

### 日志查看

```bash
# Celery 日志
tail -f logs/celery.log

# 任务详细日志
celery -A app.celery_app events --dump
```

## 扩展功能

### 添加新的导出格式

1. 在 `ExportFormat` 枚举中添加新格式
2. 在 `export_tasks.py` 中实现转换逻辑
3. 更新 API 文档

### 自定义队列

```python
# 在 celery_app.py 中配置
task_routes={
    "app.tasks.export_tasks.export_large_dataset": {"queue": "large_export"},
    "app.tasks.export_tasks.export_small_dataset": {"queue": "small_export"},
}
```

### 任务优先级

```python
# 启动任务时设置优先级
export_to_nuscenes_task.apply_async(
    args=[project_name, export_request, task_id],
    priority=5  # 0-10, 数字越大优先级越高
)
```

"""
Celery 应用配置
"""
from celery import Celery
import os

# 创建 Celery 实例
celery_app = Celery(
    "nextpoints",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0"),
    include=[
        "app.tasks.export_tasks",  # 导出任务模块
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # 时区设置
    timezone="UTC",
    enable_utc=True,
    
    # 任务超时设置
    task_time_limit=3600,  # 1 小时硬超时
    task_soft_time_limit=3300,  # 55 分钟软超时
    
    # 任务重试设置
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    
    # 结果保存时间
    result_expires=86400,  # 24 小时后清理结果
    
    # 任务状态追踪
    task_track_started=True,
    task_ignore_result=False,
)

# 配置周期性任务（可选）
celery_app.conf.beat_schedule = {
    "cleanup-old-exports": {
        "task": "app.tasks.export_tasks.cleanup_old_exports",
        "schedule": 3600.0,  # 每小时执行一次清理
    },
}

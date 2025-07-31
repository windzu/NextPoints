# SUSTechPOINTS 现代化改造项目开发文档

## 1\. 项目愿景与目标

本项目旨在将 `SUSTechPOINTS` 从一个依赖本地文件系统的点云标注工具，升级为一个支持云存储、模型辅助标注和 web 化项目管理的现代化、可扩展标注平台。

**核心目标:**

1. **数据云端化:** 解耦对本地文件系统的依赖，支持从云存储（初期为 AWS S3）直接加载和管理数据。
2. **标注智能化:** 建立与外部机器学习模型（ML Backend）的通信机制，实现预标注功能，提升标注效率。
3. **管理现代化:** 提供一个功能完善的 Web 前端，用于项目的创建、状态追踪（标注进度、质检状态）和管理。

---

## 2\. 系统架构

系统将采用面向服务的分布式架构，由以下四个核心组件构成：

1. **标注前端 (Frontend):** 用户交互界面，负责渲染点云数据和标注工具。
2. **标注后端 (Backend):** 基于 **FastAPI** 的核心服务，负责业务逻辑、API、数据库交互以及与其他服务的通信。
3. **云存储 (Cloud Storage):** **AWS S3**，作为点云原始数据的唯一可信来源 (Source of Truth)。
4. **机器学习后端 (ML Backend):** 一个独立的、符合约定接口的 Web 服务，用于运行点云推理模型。

### 数据流

- **数据加载:** `前端 -> 请求任务 -> 后端 -> 生成S3预签名URL -> 前端 -> 使用URL直接从S3加载数据`
- **模型预测:** `前端 -> 请求预测 -> 后端 -> 生成预签名URL并请求ML后端 -> ML后端下载数据并预测 -> ML后端返回结果 -> 后端保存并返回给前端`

---

## 3\. 技术栈

- **后端框架:** Python, FastAPI
- **数据校验与序列化:** Pydantic
- **数据库 ORM:** SQLModel (或 SQLAlchemy)
- **数据库:** SQLite (用于初期开发), PostgreSQL (推荐用于生产)
- **云存储交互:** Boto3 (AWS SDK for Python)
- **异步服务器:** Uvicorn
- **点云格式:** PCD (`.pcd`)

---

## 4\. 数据库模型 (Database Schema)

我们将使用以下模型来组织数据，这将通过 ORM 映射到数据库表中。

```python
# file: app/models.py

from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship

class Project(SQLModel, table=True):
    """
    项目表，用于管理不同的标注项目。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: Optional[str] = None
    s3_source_path: str # 项目关联的S3前缀路径, e.g., "s3://my-bucket/dataset1/"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # 通过 Relationship 关联到 Task 表
    tasks: List["Task"] = Relationship(back_populates="project")

class Task(SQLModel, table=True):
    """
    任务表，每个任务对应一个需要标注的点云文件。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    s3_key: str = Field(unique=True) # S3中点云文件的完整Key, e.g., "dataset1/raw/0001.pcd"
    status: str = Field(default="unlabeled", index=True) # 可选值: 'unlabeled', 'in_progress', 'completed', 'reviewed'
    annotations: Optional[dict] = Field(default=None) # 存储标注结果的JSON对象

    # Foreign Key 关联到 Project 表
    project_id: Optional[int] = Field(default=None, foreign_key="project.id")
    project: Optional[Project] = Relationship(back_populates="tasks")

```

---

## 5\. API 接口规范 (API Specification)

### 5.1 项目管理 (Project Management)

- **创建项目**

  - `POST /api/projects`
  - **Request Body:**

    ```json
    {
      "name": "Project Alpha",
      "description": "Initial test project.",
      "s3_source_path": "s3://my-bucket/dataset1/"
    }
    ```

  - **Success Response (201):** 返回新创建项目的完整信息。

- **获取项目列表**

  - `GET /api/projects`
  - **Success Response (200):**

    ```json
    [
      {
        "id": 1,
        "name": "Project Alpha",
        "total_task_count": 150,
        "completed_task_count": 75,
        "progress": 0.5
      }
    ]
    ```

- **删除项目**

  - `DELETE /api/projects/{project_id}`
  - **Success Response (204):** No Content.

### 5.2 任务管理 (Task Management)

- **获取项目下的任务列表**

  - `GET /api/projects/{project_id}/tasks`
  - **Success Response (200):** 返回该项目下所有任务的列表。

- **获取单个任务详情 (用于标注)**

  - `GET /api/tasks/{task_id}`
  - **Implementation Note:** 此接口需在后端为 `task.s3_key` 生成一个临时的 **S3 预签名 URL**。
  - **Success Response (200):**

    ```json
    {
      "id": 101,
      "status": "unlabeled",
      "annotations": null,
      "data": {
        "point_cloud_url": "S3_PRESIGNED_URL_HERE"
      }
    }
    ```

- **更新任务 (保存标注)**

  - `PUT /api/tasks/{task_id}`
  - **Request Body:**

    ```json
    {
        "status": "completed",
        "annotations": { ... } // 标注结果的JSON
    }
    ```

  - **Success Response (200):** 返回更新后的任务信息。

### 5.3 机器学习集成 (ML Integration)

- **请求模型预测**
  - `POST /api/tasks/{task_id}/predict`
  - **Implementation Note:** 后端接收到请求后，生成 S3 预签名 URL，然后向 ML Backend 发起请求。
  - **Success Response (200):** 返回由 ML Backend 生成的预标注结果。

---

## 6\. 开发路线图 (Development Roadmap)

### ✅ 阶段一: 后端基础重构与项目管理核心

- [x] **1.1: 初始化 FastAPI 项目:** 建立项目结构、安装依赖 (`fastapi`, `uvicorn`, `sqlmodel`, `boto3`)。
- [ ] **1.2: 设计并实现数据库模型:** 在 `models.py` 中创建 `Project` 和 `Task` 的 SQLModel。
- [ ] **1.3: 实现项目 CRUD API:**
  - [ ] `POST /api/projects`
  - [ ] `GET /api/projects` (初期可不含进度计算)
  - [ ] `DELETE /api/projects/{project_id}`
- [ ] **1.4: 编写 S3 同步脚本:** 创建一个 `scripts/sync_s3.py`，用于扫描 S3 目录，并将文件信息填充到数据库的 `Project` 和 `Task` 表中。

### ⬜ 阶段二: 打通云端数据流

- [ ] **2.1: 实现任务 API:**
  - [ ] `GET /api/projects/{project_id}/tasks`
  - [ ] `GET /api/tasks/{task_id}`
  - [ ] `PUT /api/tasks/{task_id}`
- [ ] **2.2: 实现 S3 预签名 URL 生成逻辑:** 在 `GET /api/tasks/{task_id}` 接口中集成 Boto3 以生成 URL。
- [ ] **2.3: 后端进度计算:** 完善 `GET /api/projects` 接口，使其能够动态计算 `total_task_count` 和 `completed_task_count`。
- [ ] **2.4: 前端改造:** 修改前端的点云加载逻辑，使其调用 `GET /api/tasks/{task_id}` 并使用返回的 `point_cloud_url` 加载数据。

### ⬜ 阶段三: 前端项目管理界面

- [ ] **3.1: 开发项目列表页面:** 创建一个新的前端页面，用于展示所有项目。
- [ ] **3.2: 对接项目列表 API:** 调用 `GET /api/projects` 并将数据显示为卡片或表格，包含名称、进度条等。
- [ ] **3.3: 实现项目创建功能:** 添加“新建项目”按钮和表单，调用 `POST /api/projects` API。
- [ ] **3.4: 实现项目删除功能:** 为每个项目添加删除按钮，调用 `DELETE /api/projects/{project_id}` API。

### ⬜ 阶段四: ML Backend 集成

- [ ] **4.1: 定义 ML Backend 接口协议:** 最终确定 `标注后端 -> ML后端` 的请求和响应 JSON 结构。
- [ ] **4.2: 实现后端预测代理接口:** 开发 `POST /api/tasks/{task_id}/predict`，该接口负责与 ML Backend 通信。
- [ ] **4.3: 前端集成预测功能:** 在标注界面添加“预测”按钮，调用预测接口，并将返回的预标注结果在点云上渲染出来。
- [ ] **4.4: (独立任务) 封装一个 ML Backend 服务:** 将一个点云模型（如 PointNet++, etc.）用 FastAPI 或 Flask 包装，使其符合步骤 4.1 中定义的接口规范。

---

## 7\. 详细实施计划 (Detailed Implementation Plan)

### 7.1 当前架构分析

#### 现有技术栈

- **Web 框架**: CherryPy + Jinja2 模板引擎
- **前端**: Three.js + 原生 JavaScript
- **数据存储**: 本地文件系统 (`./data/{scene}/`)
- **标注格式**: JSON 格式的 3D bounding box
- **算法集成**: 本地 `algos` 模块 (pre_annotate.py)
- **部署**: 单容器 Docker

#### 现有 API 接口分析

当前 CherryPy 提供的主要接口：

- `GET /` - 主页面 (index.html)
- `POST /saveworldlist` - 保存标注数据
- `POST /predict_rotation` - 预测旋转角度
- `GET /auto_annotate` - 自动标注
- `GET /load_annotation` - 加载标注数据
- `GET /datameta` - 获取所有场景元数据
- `GET /scenemeta` - 获取单个场景元数据
- `POST /run_model` - 远程模型推理

#### 数据流现状

```
前端 Three.js → CherryPy API → 本地文件系统
├── 点云数据: ./data/{scene}/lidar/*.pcd
├── 标注数据: ./data/{scene}/label/*.json
└── 元数据: ./data/{scene}/meta.json
```

### 7.2 阶段一：FastAPI 后端重构 (保持接口兼容)

#### 目标

将 CherryPy 接口平滑迁移到 FastAPI，保持前端零改动

#### 新项目结构

```
/workspace/
├── main.py (FastAPI 入口)
├── models.py (SQLModel 数据模型)
├── database.py (数据库配置)
├── routers/
│   ├── __init__.py
│   ├── projects.py (新的项目管理API)
│   ├── tasks.py (新的任务管理API)
│   └── legacy.py (兼容现有CherryPy接口)
├── services/
│   ├── __init__.py
│   ├── s3_service.py (S3操作服务)
│   ├── algos_service.py (算法调用服务)
│   └── scene_service.py (场景数据服务)
├── scripts/
│   └── sync_s3.py (S3同步脚本)
├── requirements.txt
└── legacy/ (保留原有文件作为参考)
    ├── main_cherrypy.py (重命名的原main.py)
    └── scene_reader.py
```

#### 接口兼容策略

**Phase 1.1: 基础架构搭建**

- 创建 FastAPI 应用结构
- 实现数据库模型 (Project, Task)
- 设置路由和中间件

**Phase 1.2: 兼容接口迁移**
保持所有现有端点的完全兼容：

| 原 CherryPy 接口         | FastAPI 等价接口         | 状态 | 备注            |
| ------------------------ | ------------------------ | ---- | --------------- |
| `GET /`                  | `GET /`                  | 保持 | Jinja2 模板渲染 |
| `POST /saveworldlist`    | `POST /saveworldlist`    | 兼容 | 保存标注逻辑    |
| `POST /predict_rotation` | `POST /predict_rotation` | 兼容 | 调用 algos 模块 |
| `GET /auto_annotate`     | `GET /auto_annotate`     | 兼容 | 自动标注功能    |
| `GET /load_annotation`   | `GET /load_annotation`   | 兼容 | 加载本地标注    |
| `GET /datameta`          | `GET /datameta`          | 兼容 | 场景元数据      |
| `GET /scenemeta`         | `GET /scenemeta`         | 兼容 | 单场景元数据    |
| `POST /run_model`        | `POST /run_model`        | 兼容 | 远程推理        |

**Phase 1.3: 新 RESTful API 添加**
并行添加新的标准化 API：

- `POST /api/projects` - 创建项目
- `GET /api/projects` - 项目列表
- `DELETE /api/projects/{id}` - 删除项目
- `GET /api/projects/{id}/tasks` - 项目任务列表
- `GET /api/tasks/{id}` - 任务详情 (支持 S3)
- `PUT /api/tasks/{id}` - 更新任务

#### 技术实现要点

**依赖管理**

```python
# requirements.txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlmodel==0.0.11
boto3==1.34.0
jinja2==3.1.2  # 保持模板兼容
python-multipart==0.0.6
pydantic==2.5.0
```

**数据库集成**

- 初期使用 SQLite，保持开发简单
- 设计支持 PostgreSQL 的迁移路径
- 保持与现有文件系统的双重兼容

**算法模块集成**

- 保留 `algos/` 目录结构
- 将算法调用封装为服务层
- 保持现有的 `predict_rotation`, `auto_annotate` 功能

### 7.3 阶段二：S3 集成 (渐进式替换)

#### 数据迁移策略

**Phase 2.1: S3 服务层实现**

- 实现 S3 客户端配置
- 预签名 URL 生成逻辑
- 文件上传/下载服务

**Phase 2.2: 双数据源支持**

```python
# 数据加载优先级
def load_point_cloud(scene, frame):
    # 1. 优先从 S3 加载
    if s3_available:
        return load_from_s3(scene, frame)
    # 2. 降级到本地文件
    else:
        return load_from_local(scene, frame)
```

**Phase 2.3: 数据同步工具**

```bash
# S3 同步脚本
python scripts/sync_s3.py \
  --source ./data/ \
  --bucket my-bucket \
  --prefix dataset1/ \
  --create-project "Migrated Dataset"
```

### 7.4 阶段三：前端改造 (最小化修改)

#### 改造范围

**Phase 3.1: 数据加载逻辑改造**

- 修改 Three.js 点云加载：从本地路径 → API + S3 URL
- 保持现有的渲染和交互逻辑
- 添加加载状态和错误处理

**Phase 3.2: 项目管理界面**

- 新增项目列表页面 (`projects.html`)
- 保持与现有页面的视觉一致性
- 使用原生 JavaScript，避免引入新框架

**Phase 3.3: 路由增强**

```javascript
// 新的前端路由逻辑
const routes = {
  "/": "projects.html", // 项目列表页
  "/annotate": "index.html", // 现有标注页面
  "/view": "view.html", // 现有查看页面
};
```

### 7.5 阶段四：ML Backend 集成 (保持现有集成)

#### 集成策略

- 保留现有的 `POST /run_model` 接口
- 增强为支持 S3 数据源
- 添加新的预测接口 `POST /api/tasks/{id}/predict`

#### 实现要点

```python
@router.post("/api/tasks/{task_id}/predict")
async def predict_task(task_id: int):
    # 1. 获取任务信息
    task = get_task(task_id)

    # 2. 生成 S3 预签名 URL
    presigned_url = generate_presigned_url(task.s3_key)

    # 3. 调用 ML Backend
    prediction = call_remote_inference(presigned_url)

    # 4. 返回预标注结果
    return prediction
```

### 7.6 部署和测试策略

#### Docker 配置更新

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# 支持两种启动模式
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### 测试策略

1. **单元测试**: 核心 API 接口
2. **集成测试**: CherryPy → FastAPI 兼容性
3. **端到端测试**: 前端 → 后端 → S3 完整流程
4. **性能测试**: 大文件 S3 预签名 URL 性能

### 7.7 风险控制和回滚计划

#### 风险控制

- **渐进式迁移**: 每个阶段都保持向后兼容
- **双路由支持**: 新旧接口并存
- **数据备份**: 本地数据作为 S3 的备份
- **功能开关**: 环境变量控制新功能的启用

#### 回滚计划

```bash
# 紧急回滚到 CherryPy
docker run -v /data:/app/data \
  -e LEGACY_MODE=true \
  -p 8080:8080 \
  sustech-points:legacy
```

### 7.8 开发时间估算

| 阶段 | 任务             | 预估时间 | 关键里程碑         |
| ---- | ---------------- | -------- | ------------------ |
| 1.1  | FastAPI 基础架构 | 2-3 天   | 项目启动，基本路由 |
| 1.2  | 兼容接口迁移     | 3-4 天   | 前端零改动运行     |
| 1.3  | 新 API 开发      | 2-3 天   | 项目管理功能       |
| 2.1  | S3 服务集成      | 2-3 天   | 预签名 URL 生成    |
| 2.2  | 数据双源支持     | 1-2 天   | 无缝数据迁移       |
| 3.1  | 前端数据流改造   | 2-3 天   | S3 点云加载        |
| 3.2  | 项目管理界面     | 3-4 天   | 完整项目管理       |
| 4    | ML 增强集成      | 1-2 天   | AI 辅助标注        |

**总预估**: 16-24 天 (约 3-4 周)

### 7.9 成功标准

#### 阶段一成功标准

- [ ] FastAPI 应用正常启动
- [ ] 所有原有 CherryPy 接口 100% 兼容
- [ ] 前端无需任何修改即可正常使用
- [ ] 新的项目管理 API 可正常调用

#### 阶段二成功标准

- [ ] S3 预签名 URL 正常生成
- [ ] 点云文件从 S3 正常加载
- [ ] 本地文件作为备份可正常使用
- [ ] 数据同步脚本正常工作

#### 阶段三成功标准

- [ ] 项目管理界面功能完整
- [ ] 前端可无缝切换本地/S3 数据源
- [ ] 用户体验保持一致

#### 最终成功标准

- [ ] 完整的云端化点云标注平台
- [ ] 项目/任务两级管理体系
- [ ] AI 辅助标注功能
- [ ] 可扩展的架构设计

---

## 8\. 下一步行动 (Next Actions)

基于详细实施计划，建议按以下顺序开始开发：

### 立即开始 (Phase 1.1)

1. **备份现有代码**: 将 `main.py` 重命名为 `legacy/main_cherrypy.py`
2. **创建新项目结构**: 按照 7.2 节的目录结构创建文件
3. **安装新依赖**: 创建 `requirements.txt` 并安装 FastAPI 相关包
4. **实现基础 FastAPI 应用**: 创建最小可用版本

### 第一周目标

- [ ] 完成 FastAPI 基础架构搭建
- [ ] 实现数据库模型和基本配置
- [ ] 创建路由结构框架
- [ ] 确保开发环境正常运行

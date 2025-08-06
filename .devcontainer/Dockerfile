# .devcontainer/Dockerfile

# 推荐使用官方的 devcontainer 基础镜像，它已经帮你创建了非 root 用户 (vscode) 和常用工具
# FROM mcr.microsoft.com/devcontainers/python:3.9-bullseye
FROM python:3.8-slim

# 系统级别的依赖
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends git curl \
    gcc libgl1 libglib2.0-0 python3-dev build-essential redis-server

# Python 依赖
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Dockerfile 的职责到此为止。
# 不需要设置 WORKDIR，devcontainer 会自动处理。
# 不需要 COPY 代码。
# 不需要 RUN pip install
# 不需要 EXPOSE 端口，devcontainer 会通过 forwardPorts 处理。
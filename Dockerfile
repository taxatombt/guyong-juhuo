# Juhuo Docker 配置

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /root/.juhuo/data

# 环境变量
ENV COPAW_WORKING_DIR=/root/.copaw
ENV JUHuo_DATA_DIR=/root/.juhuo

# 暴露端口
EXPOSE 18768

# 默认命令：Web Console
CMD ["python", "web_console.py"]

# 备用命令
# CMD ["python", "-m", "juhuo", "shell"]

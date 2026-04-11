# 聚活 (guyong-juhuo) Dockerfile
# 用法:
#   docker build -t taxatombt/guyong-juhuo .
#   docker run -d -p 9876:9876 -v $(pwd)/data:/app/data --name juhuo taxatombt/guyong-juhuo:latest

FROM python:3.11-slim

# 工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt ./

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个项目
COPY . .

# 暴露端口
EXPOSE 9876

#  volumes 用于持久化数据
VOLUME ["/app/data", "/app/chat_history", "/app/evolution_suggestions", "/app/skill_db"]

# 启动命令
CMD ["python", "web_console.py"]

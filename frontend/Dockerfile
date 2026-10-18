
FROM node:18-alpine

WORKDIR /app

# 先复制 package.json 和 package-lock.json，利用 Docker 缓存
COPY package*.json ./

# 安装依赖
RUN npm install

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 5173

# 启动开发服务器
CMD ["npm", "run", "dev"]


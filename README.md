# 个人图书管理系统

基于Vue3 + Flask的个人图书管理系统，支持ISBN扫码录入、图书信息爬取、AI智能分类推荐、电子书管理等功能。

## 功能特性

- ✅ 用户注册/登录
- ✅ ISBN扫码/手动输入
- ✅ 图书信息自动爬取（豆瓣、京东、当当）
- ✅ 图书管理（增删改查、搜索、分类筛选）
- ✅ 电子书上传与管理
- ✅ AI自动分类与标签生成
- ✅ 智能推荐与问答

## 技术栈

### 后端
- Flask 3.0.0
- Flask-SQLAlchemy
- SQLite/MySQL
- BeautifulSoup4 (网页解析)
- Requests (HTTP请求)

### 前端
- Vue 3.3.4
- Vue Router 4.2.5
- Element Plus 2.4.4
- Axios 1.6.2
- Vite 5.0.5

## 项目结构

```
├── backend/              # Flask后端
│   ├── app.py           # 主应用文件
│   ├── config.py        # 配置文件
│   ├── models.py        # 数据库模型
│   ├── routes/          # 路由模块
│   │   ├── auth.py      # 用户认证
│   │   ├── books.py     # 图书管理
│   │   ├── ebooks.py    # 电子书管理
│   │   └── ai.py        # AI分析推荐
│   └── utils/           # 工具模块
│       ├── isbn_validator.py  # ISBN验证
│       ├── book_scraper.py    # 图书信息爬取
│       └── ai_service.py      # AI服务
├── frontend/            # Vue3前端
│   ├── src/
│   │   ├── views/       # 页面组件
│   │   ├── api/         # API接口
│   │   └── router/      # 路由配置
│   └── package.json
├── database/            # 数据库文件
├── uploads/             # 电子书上传目录
└── README.md
```

## 快速开始

### 1. 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python init_db.py

# 启动服务
python app.py
```

后端服务将在 http://localhost:5000 启动

### 2. 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 http://localhost:3000 启动

## 数据库设计

### user 表
- id: 用户ID
- username: 用户名
- password: 密码（加密）
- email: 邮箱
- created_at: 创建时间

### book 表
- id: 图书ID
- user_id: 用户ID（外键）
- isbn: ISBN号
- title: 书名
- author: 作者
- publisher: 出版社
- publish_date: 出版日期
- description: 简介
- cover_url: 封面URL
- category: 分类

### ebook 表
- id: 电子书ID
- user_id: 用户ID（外键）
- book_id: 关联图书ID（可空）
- file_path: 文件路径
- file_name: 文件名
- file_size: 文件大小
- file_type: 文件类型

### tag 表
- id: 标签ID
- tag_name: 标签名称

### book_tag 表
- id: 关联ID
- book_id: 图书ID
- tag_id: 标签ID

## API接口

### 用户认证
- POST `/api/auth/register` - 用户注册
- POST `/api/auth/login` - 用户登录
- POST `/api/auth/logout` - 用户登出
- GET `/api/auth/me` - 获取当前用户信息

### 图书管理
- GET `/api/books` - 获取图书列表（支持分页、搜索、分类筛选）
- GET `/api/books/:id` - 获取图书详情
- POST `/api/books/add` - 添加图书（通过ISBN）
- PUT `/api/books/:id` - 更新图书信息
- DELETE `/api/books/:id` - 删除图书
- GET `/api/books/categories` - 获取所有分类

### 电子书管理
- GET `/api/ebooks` - 获取电子书列表
- POST `/api/ebooks/upload` - 上传电子书
- GET `/api/ebooks/:id` - 下载电子书
- DELETE `/api/ebooks/:id` - 删除电子书
- POST `/api/ebooks/:id/link` - 关联电子书到图书

### AI功能
- POST `/api/ai/analyze/:id` - 分析图书并生成标签
- POST `/api/ai/recommend` - 图书推荐
- POST `/api/ai/qa` - 智能问答

## 使用说明

1. **注册/登录**：首次使用需要注册账号
2. **添加图书**：通过ISBN扫码或手动输入ISBN添加图书
3. **图书管理**：查看、编辑、删除图书，支持搜索和分类筛选
4. **电子书管理**：上传PDF、EPUB等格式的电子书
5. **AI分析**：对图书进行AI分析，自动生成分类和标签
6. **智能推荐**：基于关键词获取图书推荐
7. **智能问答**：与AI助手对话，获取图书推荐

## 注意事项

- 首次运行需要初始化数据库（运行 `python backend/init_db.py`）
- 确保uploads目录有写入权限
- 爬虫功能依赖网络连接，可能需要代理访问部分网站
- AI功能当前为简化实现，可后续集成真实的AI接口（如OpenAI、百度文心一言等）

## 开发计划

- [ ] 实现ISBN扫码功能（前端摄像头调用）
- [ ] 集成真实的AI接口（OpenAI/文心一言等）
- [ ] 优化爬虫稳定性
- [ ] 添加移动端适配
- [ ] 实现图书阅读进度跟踪
- [ ] 添加数据导出功能

## License

MIT License

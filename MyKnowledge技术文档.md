# MyKnowledge 技术文档

本文档描述 **MyKnowledge 个人图书/知识管理系统** 仓库中实际采用的技术栈与实现要点，与代码及依赖保持一致。

---

## 1. 项目概述

系统分为 **Vue 3 前端** 与 **Flask 后端**，通过 REST API（`/api/*`）交互。开发时前端使用 Vite 独立启动并代理 API；生产或局域网访问时，可由 Flask 托管 `frontend/dist` 静态资源，实现单入口部署。

---

## 2. 技术栈总览

| 层级 | 技术 | 版本（以仓库文件为准） | 用途 |
|------|------|------------------------|------|
| 前端框架 | Vue | ^3.3.4 | 组件与页面 |
| 前端路由 | vue-router | ^4.2.5 | SPA 路由与登录守卫 |
| 构建工具 | Vite | ^5.0.5 | 开发与打包 |
| Vue 插件 | @vitejs/plugin-vue | ^4.5.0 | SFC 编译 |
| UI | Element Plus | ^2.4.4 | 组件库 |
| 图标 | @element-plus/icons-vue | （随 Element Plus 安装） | 图标 |
| HTTP | axios | ^1.6.2 | 调用后端 API |
| 图表 | echarts | ^6.0.0 | 仪表盘等数据可视化 |
| 扫码 | vue3-barcode-qrcode-reader | ^1.0.5（底层 @zxing） | ISBN 等条码/二维码扫描 |
| 二维码生成 | qrcode | ^1.5.4 | 与图书/展示相关的前端能力 |
| 后端框架 | Flask | 3.0.0 | Web 应用与 API |
| ORM | Flask-SQLAlchemy | 3.1.1 | 数据访问 |
| 跨域 | Flask-CORS | 4.0.0 | 浏览器跨域与携带 Cookie |
| HTTP 工具库 | Werkzeug | 3.0.1 | 上传、安全文件名等 |
| 数据库驱动 | PyMySQL | 1.1.0 | 连接 MySQL |
| 数据库 | MySQL | 由部署环境决定 | 持久化存储 |
| HTTP 客户端 | requests | 2.31.0 | 外部 API、爬虫、AnythingLLM |
| HTML 解析 | beautifulsoup4 | 4.12.2 | 图书信息抓取解析 |
| 环境变量 | python-dotenv | ≥1.0.0 | 加载 `.env` |
| AI SDK | openai | ≥1.0.0 | OpenAI 兼容 HTTP API（如 DeepSeek、Moonshot） |
| 密码学 | cryptography | 41.0.7 | 开发用 HTTPS 自签证书生成 |
| 中文分词 | jieba | （见 `requirements.txt`） | RAG/分词与助手侧文本处理 |

---

## 3. 前端技术实现

### 3.1 工程与脚本

- 入口构建：**Vite** + **@vitejs/plugin-vue**，单页应用。
- `package.json` 中 `predev` 在执行 `vite` 前运行 `python ../backend/generate_cert.py`，用于生成/更新开发用 TLS 证书。
- `npm run build` 输出到 `frontend/dist`，供 Flask 静态托管或独立 Nginx 等部署。

### 3.2 开发服务器与网络

- `vite.config.js`：`server.port = 3000`，`host: true` 便于局域网调试。
- **HTTPS**：读取 `backend/key.pem`、`backend/cert.pem`，与扫码、安全上下文等场景兼容。
- **代理**：`/api` → `http://localhost:5000`，与 Flask 默认端口一致。

### 3.3 与后端的通信

- `src/api/index.js` 使用 **axios** 实例：
  - `withCredentials: true`，与后端 **Flask Session（Cookie）** 配合。
  - **baseURL**：本机为相对路径 `/api`（走 Vite 代理）；非 `localhost`/`127.0.0.1` 时使用 `http://{当前主机}:5000/api`（便于手机扫码访问同一局域网后端）。
  - 请求拦截器写入 `Authorization: Bearer ${token}`；后端受保护接口主要依赖 **Session 中的 `user_id`**，前端 `localStorage` 中的 `token` 当前为登录成功后的占位标记（如 `logged_in`），用于 **路由守卫**。

### 3.4 路由与页面

- `src/router/index.js`：**createWebHistory** 模式；`/login` 外需存在 `localStorage.token` 才放行。
- 主要页面：登录/注册、布局壳、仪表盘、图书列表/详情/添加、电子书管理/预览、AI 推荐与问答等，均基于 **Vue 3**（组合式或选项式混用）与 **Element Plus**。

### 3.5 可视化与硬件能力

- **ECharts**：仪表盘分类占比等图表（与 `/api/dashboard` 数据配合）。
- **vue3-barcode-qrcode-reader**：摄像头扫码录入 ISBN 等。
- **qrcode**：二维码相关前端能力。

---

## 4. 后端技术实现

### 4.1 应用结构

- 入口：`backend/app.py` 创建 `Flask` 实例，加载 `config.Config`，初始化 **Flask-SQLAlchemy** 的 `db`，注册 **CORS**，并注册蓝图：

| 蓝图 | URL 前缀 | 职责摘要 |
|------|-----------|----------|
| `auth_bp` | `/api/auth` | 注册、登录、登出、当前用户；Session |
| `books_bp` | `/api/books` | 图书 CRUD、元数据、书架位置等 |
| `ebooks_bp` | `/api/ebooks` | 电子书上传、下载、内联预览 |
| `ai_bp` | `/api/ai` | 图书分析、推荐、问答、对话历史等 |
| `isbn_bp` | `/api/isbn` | ISBN 校验、缓存统计与清理 |
| `dashboard_bp` | `/api/dashboard` | 仪表盘汇总、书单推荐等 |

- 静态站点：`FRONTEND_DIST` 指向 `frontend/dist`，`/assets/*` 与 SPA fallback 将非 API 请求回退到 `index.html`，由 Vue Router 处理。

### 4.2 配置与环境变量

- `backend/config.py` 通过 **python-dotenv** 加载项目根目录 `.env`。
- 主要配置项包括：MySQL 连接、`SECRET_KEY`、上传目录与大小限制、**OpenAI 兼容 API**（`AI_API_KEY`、`AI_API_BASE_URL`、`AI_MODEL`）、**AnythingLLM**（`ANYTHINGLLM_API_KEY`、`ANYTHINGLLM_BASE_URL`、`ANYTHINGLLM_WORKSPACE_SLUG`）、图书数据源顺序 `BOOK_SOURCES`、爬虫调试与超时等。

### 4.3 认证与安全

- 密码：**Werkzeug** `generate_password_hash` / `check_password_hash`。
- 登录态：**Flask Session** 存 `user_id`、`username`；`routes.auth.login_required` 从 Session 读取 `user_id`。
- CORS：`supports_credentials=True`，与前端 `withCredentials` 一致。
- Session Cookie：`SESSION_COOKIE_SAMESITE`、`SESSION_COOKIE_HTTPONLY` 在 `Config` 中定义。

### 4.4 图书与 ISBN

- **ISBN**：`utils/isbn_validator` 校验与规范化；`routes/isbn` 提供校验与缓存管理接口。
- **元数据获取**：`utils/book_scraper` 使用 **requests** + **BeautifulSoup** 按配置的数据源顺序抓取；可选 `utils/robots_checker` 遵守 robots 规则。
- **内存缓存**：`utils/cache` 对 ISBN 与部分 API 结果做 TTL 缓存，减轻重复请求与爬取压力。

### 4.5 电子书

- 允许扩展名：`pdf`、`epub`、`mobi`、`txt`、`doc`、`docx`（见 `routes/ebooks.py`）。
- 上传路径：项目根下 `uploads/{user_id}/`，由 `Config.UPLOAD_FOLDER` 管理，`MAX_CONTENT_LENGTH` 限制请求体大小。
- **Word 预览**：可通过系统安装的 **LibreOffice**（`soffice`）无头模式将 `doc`/`docx` 转为 PDF 后内联展示；未安装时仅能下载或使用其他格式预览。
- 响应头：使用 RFC5987 形式的 `filename*` 处理中文文件名，避免编码问题。

### 4.6 仪表盘

- `routes/dashboard.py`：基于 **SQLAlchemy** 聚合用户图书分类数量；返回占比与「经典书单」等模板数据，供前端 **ECharts** 与列表展示。

### 4.7 AI、RAG 与外部检索

- **图书标签/分类分析**：`utils/ai_service.py` 以 **关键词规则** 为主（不依赖外部大模型完成该步），结果写回 `Book` 与 `Tag`/`BookTag`；分析后可触发 **RAG 索引更新**（`enhanced_recommend.update_rag_index`）。
- **推荐与问答增强**：`utils/rag_engine.py` 实现基于 **jieba 分词** 与 **TF-IDF** 的检索、字段加权、停用词等；与 `utils/enhanced_recommend.py` 组合，并配合 **API 缓存**。
- **图书助手**：`utils/assistant_service.py` 使用 **openai** 官方 SDK 的 `OpenAI` 客户端，指向 `Config` 中的兼容接口，结合本地书目检索生成回答；意图与分词处使用 **jieba**（失败时回退正则分词）。
- **AnythingLLM**：`utils/anythingllm_client.py` 通过 **requests** 调用工作区 API，支持向量检索；使用 **urllib3.util.retry.Retry** 与 **HTTPAdapter** 做重试。模型表 `AnythingLLMDoc` 记录图书与远端文档映射。
- **对话历史**：`ChatMessage` 模型持久化用户与 AI 消息及推荐结果 JSON。

### 4.8 开发与 TLS

- `generate_cert.py` 使用 **cryptography** 生成 RSA 证书与私钥，供 Vite HTTPS 或本地调试使用（非生产 CA 签发）。

---

## 5. 数据模型（ORM 概要）

使用 **Flask-SQLAlchemy** 定义，主要实体包括：

- `User`：用户；密码哈希；与图书、电子书、书架、会话数据关联。
- `Book`：ISBN、题名、作者、出版社、简介、分类、封面等；与标签、电子书、位置、AnythingLLM 文档映射关联。
- `Ebook`：用户上传文件路径与元数据。
- `Tag` / `BookTag`：标签及多对多关联。
- `Bookshelf` / `BookLocation`：物理书架与图书摆放位置。
- `ChatMessage`：AI 对话与推荐快照。
- `AnythingLLMDoc`：同步到 AnythingLLM 的文档路径记录。

数据库为 **MySQL**，连接 URI 形态为 `mysql+pymysql://...?charset=utf8mb4`，并配置连接池 `pool_pre_ping`、`pool_recycle`。

---

## 6. 依赖文件位置

- Python：`backend/requirements.txt`
- 前端：`frontend/package.json` 与 `frontend/package-lock.json`

安装示例（在项目根目录）：

```bash
cd backend && pip install -r requirements.txt
cd ../frontend && npm install
```

---

## 7. 运行与部署要点

1. 准备 **MySQL** 数据库，环境变量或 `config.py` 默认值与 `init_mysql_db.py` 等初始化脚本配合使用。
2. 配置根目录 `.env`（数据库、密钥、AI 与 AnythingLLM 等），**勿将真实密钥提交版本库**。
3. 开发：后端 `python app.py`（默认 5000）；前端 `npm run dev`（3000，HTTPS，代理 `/api`）。
4. 生产构建：前端 `npm run build` 后，由 Flask 提供 `dist` 或由反向代理分别托管静态与 API。
5. 若使用 Word 在线预览，服务器需安装 **LibreOffice** 并可在 PATH 中调用 `soffice`。
6. **AnythingLLM** 为独立服务，需单独部署并使 `ANYTHINGLLM_BASE_URL` 可达。

---

## 8. 文档维护说明

本文件随仓库实现更新；若新增模块或依赖，请同步修改 **第 2 节总表**、**第 4 节实现说明** 与 **第 6 节依赖路径**。

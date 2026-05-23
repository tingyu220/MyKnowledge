"""
配置文件
"""
import os
from pathlib import Path

# 加载 .env 文件（若存在）
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
except ImportError:
    pass

# 获取项目根目录（MyKnowledge目录）
# __file__ 是 backend/config.py，向上两级到 MyKnowledge
BACKEND_DIR = Path(__file__).resolve().parent  # backend目录
BASE_DIR = BACKEND_DIR.parent  # MyKnowledge目录（项目根目录）

class Config:
    # MySQL数据库配置
    DB_HOST = os.environ.get('DB_HOST') or 'localhost'
    DB_PORT = os.environ.get('DB_PORT') or '3306'
    DB_USER = os.environ.get('DB_USER') or 'root'
    DB_PASSWORD = os.environ.get('DB_PASSWORD') or 'Ty07172003.'
    DB_NAME = os.environ.get('DB_NAME') or 'myknowledge'
    
    # 数据库连接字符串
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # 自动检测连接是否有效
        'pool_recycle': 300,    # 连接回收时间（秒）
    }
    
    # 密钥配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    # Session 配置：开发环境下代理请求需正确携带 cookie
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    
    # 文件上传配置
    upload_dir = BASE_DIR / 'uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)  # 确保目录存在
    UPLOAD_FOLDER = str(upload_dir)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB
    
    # AI 接口配置（支持 OpenAI 兼容接口，如 Moonshot、DeepSeek 等）
    # 通过环境变量 AI_API_KEY 设置 API Key，生产环境请勿写在代码中
    # AI_API_BASE_URL 示例：
    # - DeepSeek: https://api.deepseek.com
    # - Moonshot (Kimi): https://api.moonshot.cn/v1
    # - OpenAI: https://api.openai.com/v1
    AI_API_KEY = os.environ.get('AI_API_KEY') or ''
    AI_API_BASE_URL = os.environ.get('AI_API_BASE_URL') or 'https://api.deepseek.com'

    # AI 模型名称（根据使用的服务商选择）
    # DeepSeek: deepseek-chat, deepseek-coder
    # Moonshot: moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k
    AI_MODEL = os.environ.get('AI_MODEL') or 'deepseek-chat'

    # AnythingLLM 向量数据库配置
    # 用于 RAG 检索增强（向量搜索）
    # 环境变量：ANYTHINGLLM_API_KEY, ANYTHINGLLM_BASE_URL, ANYTHINGLLM_WORKSPACE_SLUG
    ANYTHINGLLM_API_KEY = os.environ.get('ANYTHINGLLM_API_KEY') or ''
    ANYTHINGLLM_BASE_URL = os.environ.get('ANYTHINGLLM_BASE_URL') or 'http://localhost:3001'
    ANYTHINGLLM_WORKSPACE_SLUG = os.environ.get('ANYTHINGLLM_WORKSPACE_SLUG') or 'mykownledge'

    # 图书信息数据源（按顺序尝试，国内优先）
    # 可选：douban_api, openlibrary, googlebooks, douban, jd, dangdang
    # 默认顺序（国内优先）：豆瓣API → 京东 → 当当 → Open Library → Google Books → 豆瓣爬虫
    # 仅用 API 示例：BOOK_SOURCES = douban_api,openlibrary,googlebooks
    _src = os.environ.get('BOOK_SOURCES', '').strip()
    BOOK_SOURCES = [s.strip() for s in _src.split(',') if s.strip()] if _src else None

    # 爬虫调试：为 True 时打印各数据源失败原因
    SCRAPER_DEBUG = os.environ.get('SCRAPER_DEBUG', '').lower() in ('1', 'true', 'yes')
    
    # 爬虫总超时时间（秒），默认 20 秒
    SCRAPER_TIMEOUT = int(os.environ.get('SCRAPER_TIMEOUT', '20'))


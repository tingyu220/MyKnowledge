# -*- coding: utf-8 -*-
"""
Flask 主应用文件
个人图书管理系统后端
"""
import sys
import os
from flask import Flask, request, send_from_directory, jsonify
from flask_cors import CORS
from config import Config
from models import db

# 获取前端dist目录的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIST = os.path.join(BASE_DIR, '..', 'frontend', 'dist')
print(f"前端目录: {FRONTEND_DIST}")
print(f"目录存在: {os.path.exists(FRONTEND_DIST)}")

app = Flask(__name__)
app.config.from_object(Config)

# 应用数据库引擎选项
if hasattr(Config, 'SQLALCHEMY_ENGINE_OPTIONS'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = Config.SQLALCHEMY_ENGINE_OPTIONS

# 初始化数据库
db.init_app(app)

# 启用CORS
CORS(app, supports_credentials=True)

# 注册蓝图
from routes.auth import auth_bp
from routes.books import books_bp
from routes.ebooks import ebooks_bp
from routes.ai import ai_bp
from routes.isbn import isbn_bp
from routes.dashboard import dashboard_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(books_bp, url_prefix='/api/books')
app.register_blueprint(ebooks_bp, url_prefix='/api/ebooks')
app.register_blueprint(ai_bp, url_prefix='/api/ai')
app.register_blueprint(isbn_bp, url_prefix='/api/isbn')
app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')

# 打印所有注册的路由
print("\n已注册的路由:")
for rule in app.url_map.iter_rules():
    print(f"  {rule.rule} -> {rule.endpoint}")

@app.route('/')
def index():
    return jsonify({'message': '个人图书管理系统 API', 'version': '1.0.0'})

# 静态文件路由（assets目录）
@app.route('/assets/<path:filename>')
def serve_assets(filename):
    file_path = os.path.join(FRONTEND_DIST, 'assets', filename)
    if os.path.exists(file_path):
        return send_from_directory(os.path.join(FRONTEND_DIST, 'assets'), filename)
    return jsonify({'error': f'Asset not found: {filename}', 'path': file_path}), 404

# 前端SPA fallback（所有非API路由）
@app.route('/<path:path>')
def serve_spa(path):
    # 先检查是否是静态文件
    file_path = os.path.join(FRONTEND_DIST, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIST, path)
    # 返回index.html让Vue Router处理路由
    return send_from_directory(FRONTEND_DIST, 'index.html')

@app.route('/books/add')
@app.route('/login')
@app.route('/books')
@app.route('/dashboard')
def spa_routes():
    return send_from_directory(FRONTEND_DIST, 'index.html')

if __name__ == '__main__':
    try:
        with app.app_context():
            try:
                db.create_all()
                print("[OK] 数据库表检查/创建完成")
            except Exception as e:
                print(f"[WARNING] 数据库表创建警告: {str(e)}")
                print("  如果数据库不存在，请先运行: python init_mysql_db.py")

        # SSL证书路径
        cert_path = os.path.join(BASE_DIR, 'cert.pem')
        key_path = os.path.join(BASE_DIR, 'key.pem')

        print("\n" + "=" * 50)
        print("Flask服务器启动中...")
        print("=" * 50)
        print("后端地址: http://localhost:5000")
        print("API地址: http://localhost:5000/")
        print("前端地址: http://localhost:3000")
        print("手机扫码用: http://你的电脑IP:5000")
        print("按 Ctrl+C 停止服务器\n")

        app.run(
            debug=True,
            host='0.0.0.0',
            port=5000
        )
    except Exception as e:
        print(f"\n[ERROR] 启动失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

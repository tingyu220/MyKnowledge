"""
后端服务器启动脚本（带错误处理）
"""
import sys
import traceback

def check_imports():
    """检查所有必要的导入"""
    print("=" * 50)
    print("检查依赖导入...")
    print("=" * 50)
    
    try:
        from flask import Flask
        print("✓ Flask")
    except ImportError as e:
        print(f"✗ Flask 导入失败: {e}")
        return False
    
    try:
        from flask_cors import CORS
        print("✓ Flask-CORS")
    except ImportError as e:
        print(f"✗ Flask-CORS 导入失败: {e}")
        return False
    
    try:
        from flask_sqlalchemy import SQLAlchemy
        print("✓ Flask-SQLAlchemy")
    except ImportError as e:
        print(f"✗ Flask-SQLAlchemy 导入失败: {e}")
        return False
    
    try:
        import pymysql
        print("✓ PyMySQL")
    except ImportError as e:
        print(f"✗ PyMySQL 导入失败: {e}")
        return False
    
    try:
        from config import Config
        print("✓ Config")
    except ImportError as e:
        print(f"✗ Config 导入失败: {e}")
        traceback.print_exc()
        return False
    
    try:
        from models import db
        print("✓ Models")
    except ImportError as e:
        print(f"✗ Models 导入失败: {e}")
        traceback.print_exc()
        return False
    
    return True

def check_database_connection():
    """检查数据库连接"""
    print("\n" + "=" * 50)
    print("检查数据库连接...")
    print("=" * 50)
    
    try:
        from config import Config
        import pymysql
        
        print(f"尝试连接: {Config.DB_HOST}:{Config.DB_PORT}")
        print(f"数据库: {Config.DB_NAME}")
        print(f"用户: {Config.DB_USER}")
        
        connection = pymysql.connect(
            host=Config.DB_HOST,
            port=int(Config.DB_PORT),
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            charset='utf8mb4',
            connect_timeout=5
        )
        
        with connection.cursor() as cursor:
            cursor.execute(f"SHOW DATABASES LIKE '{Config.DB_NAME}'")
            result = cursor.fetchone()
            if not result:
                print(f"⚠ 数据库 '{Config.DB_NAME}' 不存在，将尝试创建...")
            else:
                print(f"✓ 数据库 '{Config.DB_NAME}' 存在")
        
        connection.close()
        print("✓ 数据库连接成功")
        return True
        
    except pymysql.Error as e:
        print(f"✗ 数据库连接失败: {e}")
        print("\n请检查：")
        print("  1. MySQL服务是否已启动")
        print("  2. 数据库配置是否正确 (backend/config.py)")
        print("  3. 用户权限是否足够")
        return False
    except Exception as e:
        print(f"✗ 数据库连接检查失败: {e}")
        traceback.print_exc()
        return False

def start_app():
    """启动Flask应用"""
    print("\n" + "=" * 50)
    print("启动Flask应用...")
    print("=" * 50)
    
    try:
        from app import app
        
        print("✓ Flask应用初始化成功")
        print(f"✓ 服务器将运行在: http://0.0.0.0:5000")
        print(f"✓ 本地访问: http://localhost:5000")
        print("\n按 Ctrl+C 停止服务器\n")
        
        app.run(debug=True, host='0.0.0.0', port=5000)
        
    except Exception as e:
        print(f"\n✗ 启动失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("个人图书管理系统 - 后端启动检查")
    print("=" * 50)
    
    # 检查导入
    if not check_imports():
        print("\n✗ 依赖检查失败，请先安装依赖:")
        print("  pip install -r requirements.txt")
        return 1
    
    # 检查数据库连接（但不强制要求，因为db.create_all可能会创建数据库）
    check_database_connection()
    
    # 启动应用
    try:
        start_app()
    except KeyboardInterrupt:
        print("\n\n服务器已停止")
        return 0
    except Exception as e:
        print(f"\n✗ 启动过程中出错: {e}")
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())

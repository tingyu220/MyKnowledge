"""
项目检查和启动脚本
"""
import sys
import os
import subprocess
from pathlib import Path

# 添加backend目录到路径
backend_dir = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_dir))

def check_backend_dependencies():
    """检查后端依赖"""
    print("=" * 50)
    print("检查后端依赖...")
    print("=" * 50)
    
    required_packages = [
        'flask', 'flask_sqlalchemy', 'flask_cors', 
        'werkzeug', 'requests', 'bs4', 'pymysql', 'cryptography'
    ]
    
    missing = []
    for package in required_packages:
        try:
            if package == 'bs4':
                __import__('bs4')
            elif package == 'flask_sqlalchemy':
                __import__('flask_sqlalchemy')
            elif package == 'flask_cors':
                __import__('flask_cors')
            else:
                __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} 未安装")
            missing.append(package)
    
    if missing:
        print(f"\n缺少依赖: {', '.join(missing)}")
        print("请运行: pip install -r backend/requirements.txt")
        return False
    
    print("\n✓ 所有后端依赖已安装")
    return True

def check_database_connection():
    """检查数据库连接"""
    print("\n" + "=" * 50)
    print("检查数据库连接...")
    print("=" * 50)
    
    try:
        from config import Config
        import pymysql
        
        print(f"数据库: {Config.DB_NAME}")
        print(f"主机: {Config.DB_HOST}:{Config.DB_PORT}")
        print(f"用户: {Config.DB_USER}")
        
        # 尝试连接
        connection = pymysql.connect(
            host=Config.DB_HOST,
            port=int(Config.DB_PORT),
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            cursor.execute(f"SHOW DATABASES LIKE '{Config.DB_NAME}'")
            result = cursor.fetchone()
            if result:
                print(f"✓ 数据库 '{Config.DB_NAME}' 存在")
            else:
                print(f"⚠ 数据库 '{Config.DB_NAME}' 不存在，将在启动时创建")
        
        connection.close()
        print("✓ 数据库连接成功")
        return True
        
    except Exception as e:
        print(f"✗ 数据库连接失败: {str(e)}")
        print("\n请检查：")
        print("  1. MySQL服务是否已启动")
        print("  2. 数据库配置是否正确 (backend/config.py)")
        print("  3. 用户权限是否足够")
        return False

def check_frontend_dependencies():
    """检查前端依赖"""
    print("\n" + "=" * 50)
    print("检查前端依赖...")
    print("=" * 50)
    
    frontend_dir = Path(__file__).parent / 'frontend'
    node_modules = frontend_dir / 'node_modules'
    
    if node_modules.exists():
        print("✓ node_modules 目录存在")
        return True
    else:
        print("⚠ node_modules 目录不存在")
        print("请运行: cd frontend && npm install")
        return False

def main():
    """主函数"""
    print("\n" + "=" * 50)
    print("个人图书管理系统 - 项目检查")
    print("=" * 50)
    
    # 检查后端依赖
    backend_ok = check_backend_dependencies()
    
    # 检查前端依赖
    frontend_ok = check_frontend_dependencies()
    
    # 检查数据库连接
    db_ok = check_database_connection()
    
    print("\n" + "=" * 50)
    print("检查结果汇总")
    print("=" * 50)
    print(f"后端依赖: {'✓ 通过' if backend_ok else '✗ 失败'}")
    print(f"前端依赖: {'✓ 通过' if frontend_ok else '✗ 失败'}")
    print(f"数据库连接: {'✓ 通过' if db_ok else '✗ 失败'}")
    
    if backend_ok and frontend_ok and db_ok:
        print("\n✓ 所有检查通过！项目可以启动。")
        print("\n启动方式：")
        print("  1. 后端: cd backend && python app.py")
        print("  2. 前端: cd frontend && npm run dev")
        print("  3. 或使用: start.bat")
        return 0
    else:
        print("\n⚠ 部分检查未通过，请先解决上述问题。")
        return 1

if __name__ == '__main__':
    sys.exit(main())

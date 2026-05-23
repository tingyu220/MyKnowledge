"""
启动前后端服务
"""
import subprocess
import sys
import time
from pathlib import Path

def start_backend():
    """启动后端服务"""
    print("=" * 50)
    print("启动后端服务...")
    print("=" * 50)
    
    backend_dir = Path(__file__).parent / 'backend'
    
    # 先初始化数据库
    print("初始化数据库...")
    try:
        result = subprocess.run(
            [sys.executable, 'init_mysql_db.py'],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            print("✓ 数据库初始化成功")
        else:
            print(f"⚠ 数据库初始化警告: {result.stderr}")
    except Exception as e:
        print(f"⚠ 数据库初始化跳过: {str(e)}")
    
    # 启动Flask服务
    print("\n启动Flask服务器 (http://localhost:5000)...")
    print("按 Ctrl+C 停止服务\n")
    
    try:
        subprocess.run(
            [sys.executable, 'app.py'],
            cwd=str(backend_dir)
        )
    except KeyboardInterrupt:
        print("\n后端服务已停止")

def start_frontend():
    """启动前端服务"""
    print("=" * 50)
    print("启动前端服务...")
    print("=" * 50)
    
    frontend_dir = Path(__file__).parent / 'frontend'
    
    print("启动Vite开发服务器 (http://localhost:3000)...")
    print("按 Ctrl+C 停止服务\n")
    
    try:
        # 检查是否有npm
        subprocess.run(['npm', '--version'], check=True, capture_output=True)
        
        subprocess.run(
            ['npm', 'run', 'dev'],
            cwd=str(frontend_dir)
        )
    except FileNotFoundError:
        print("✗ 未找到 npm，请先安装 Node.js")
    except KeyboardInterrupt:
        print("\n前端服务已停止")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        service = sys.argv[1]
        if service == 'backend':
            start_backend()
        elif service == 'frontend':
            start_frontend()
        else:
            print("用法: python start_services.py [backend|frontend]")
    else:
        print("请指定要启动的服务:")
        print("  python start_services.py backend   # 启动后端")
        print("  python start_services.py frontend  # 启动前端")
        print("\n或使用 start.bat 同时启动前后端")

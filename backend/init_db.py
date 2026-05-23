"""
数据库初始化脚本（通用版，支持MySQL和SQLite）
"""
from app import app, db
from config import Config

def init_database():
    """初始化数据库表"""
    try:
        with app.app_context():
            db.create_all()
            print("✓ 数据库初始化完成！")
            
            # 根据数据库类型显示不同信息
            if 'mysql' in Config.SQLALCHEMY_DATABASE_URI.lower():
                print(f"  数据库类型: MySQL")
                print(f"  数据库名称: {Config.DB_NAME}")
                print(f"  主机: {Config.DB_HOST}:{Config.DB_PORT}")
            else:
                print(f"  数据库类型: SQLite")
                print(f"  数据库文件: {Config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')}")
            
            print(f"  上传目录: {Config.UPLOAD_FOLDER}")
            print("\n  已创建的表：")
            print("    - user (用户表)")
            print("    - book (图书表)")
            print("    - ebook (电子书表)")
            print("    - tag (标签表)")
            print("    - book_tag (图书标签关联表)")
            print("    - bookshelf (书架表)")
            print("    - book_location (图书位置表)")
    except Exception as e:
        print(f"✗ 数据库初始化失败: {str(e)}")
        if 'mysql' in Config.SQLALCHEMY_DATABASE_URI.lower():
            print("\n提示：如果是MySQL数据库，请先运行 python init_mysql_db.py 创建数据库")

if __name__ == '__main__':
    init_database()


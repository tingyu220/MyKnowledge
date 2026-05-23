# -*- coding: utf-8 -*-
"""
MySQL数据库初始化脚本
用于创建数据库（如果不存在）和初始化表结构
"""
import pymysql
from app import app, db
from config import Config
from fix_user_email_nullable import fix_email_column
from fix_book_updated_at import fix_book_updated_at
from fix_book_category_length import fix_book_category_length
from fix_book_publish_date import fix_book_publish_date
from fix_book_description import fix_book_description
from fix_ebook_uploaded_at import fix_ebook_uploaded_at
from fix_bookshelf_tables import fix_bookshelf_tables
from fix_chat_message import fix_chat_message_table

def create_database_if_not_exists():
    """如果数据库不存在则创建"""
    try:
        # 连接到MySQL服务器（不指定数据库）
        connection = pymysql.connect(
            host=Config.DB_HOST,
            port=int(Config.DB_PORT),
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 检查数据库是否存在
            cursor.execute(f"SHOW DATABASES LIKE '{Config.DB_NAME}'")
            result = cursor.fetchone()
            
            if not result:
                # 创建数据库
                cursor.execute(f"CREATE DATABASE `{Config.DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                print(f"OK: 数据库 '{Config.DB_NAME}' 创建成功")
            else:
                print(f"OK: 数据库 '{Config.DB_NAME}' 已存在")
        
        connection.close()
        return True
    except Exception as e:
        print(f"ERROR: 创建数据库失败: {str(e)}")
        return False

def init_database():
    """初始化数据库表"""
    # 首先确保数据库存在
    if not create_database_if_not_exists():
        print("无法创建数据库，请检查MySQL连接配置")
        return
    
    # 创建表
    try:
        with app.app_context():
            db.create_all()
            print("\nOK: 数据库表创建成功！")
            print(f"  数据库: {Config.DB_NAME}")
            print(f"  主机: {Config.DB_HOST}:{Config.DB_PORT}")
            print("\n  已创建的表：")
            print("    - user (用户表)")
            print("    - book (图书表)")
            print("    - ebook (电子书表)")
            print("    - tag (标签表)")
            print("    - book_tag (图书标签关联表)")
            print("    - bookshelf (书架表)")
            print("    - book_location (图书位置表)")
            print("    - chat_message (AI对话历史表)")
            # 修复 user.email 可空（兼容旧表或建表差异）
            try:
                fix_email_column()
            except Exception as e:
                print(f"  (user.email 修复跳过: {e})")
            # 修复 book.updated_at 缺失（兼容旧表）
            try:
                fix_book_updated_at()
            except Exception as e:
                print(f"  (book.updated_at 修复跳过: {e})")
            # 修复 book.category 长度过短（兼容 Open Library 等长分类）
            try:
                fix_book_category_length()
            except Exception as e:
                print(f"  (book.category 修复跳过: {e})")
            # 修复 book.publish_date 类型（确保为 VARCHAR 而非 DATE）
            try:
                fix_book_publish_date()
            except Exception as e:
                print(f"  (book.publish_date 修复跳过: {e})")
            # 修复 book.description 类型（确保为 TEXT，支持 2000+ 字）
            try:
                fix_book_description()
            except Exception as e:
                print(f"  (book.description 修复跳过: {e})")
            # 修复 ebook.uploaded_at 缺失（兼容旧表）
            try:
                fix_ebook_uploaded_at()
            except Exception as e:
                print(f"  (ebook.uploaded_at 修复跳过: {e})")
            # 创建/修复 reading_session（已移除）
            try:
                fix_bookshelf_tables()
            except Exception as e:
                print(f"  (bookshelf/book_location 修复跳过: {e})")
            # 创建/修复 chat_message 表
            try:
                fix_chat_message_table()
            except Exception as e:
                print(f"  (chat_message 修复跳过: {e})")
    except Exception as e:
        print(f"\nERROR: 创建表失败: {str(e)}")
        print("\n请检查：")
        print("  1. MySQL服务是否已启动")
        print("  2. 数据库连接配置是否正确")
        print("  3. 用户权限是否足够")

if __name__ == '__main__':
    print("=" * 50)
    print("MySQL数据库初始化")
    print("=" * 50)
    print(f"数据库: {Config.DB_NAME}")
    print(f"主机: {Config.DB_HOST}:{Config.DB_PORT}")
    print(f"用户: {Config.DB_USER}")
    print("=" * 50)
    init_database()

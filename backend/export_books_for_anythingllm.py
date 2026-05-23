# -*- coding: utf-8 -*-
"""
将MySQL中的图书数据导出为TXT文件
每本书一个文件，供AnythingLLM训练使用
"""

import os
import glob
from app import app, db
from models import Book, BookLocation, Bookshelf


def _build_book_content(book):
    """
    构建图书的TXT内容（供AnythingLLM使用）

    参数：
        book: Book对象

    返回：
        str: 格式化后的文本内容
    """
    lines = []
    lines.append(f"书名：{book.title}")
    lines.append(f"作者：{book.author or '未知'}")
    lines.append(f"ISBN：{book.isbn or '未知'}")
    lines.append(f"出版社：{book.publisher or '未知'}")
    lines.append(f"出版年份：{book.publish_date or '未知'}")
    lines.append(f"分类：{book.category or '未分类'}")

    # 位置信息（通过关联查询）
    location_text = "未设置"
    if book.location and book.location.bookshelf:
        shelf = book.location.bookshelf
        location_parts = []
        if shelf.room:
            location_parts.append(shelf.room)
        if shelf.name:
            location_parts.append(shelf.name)
        if book.location.layer:
            location_parts.append(f"第{book.location.layer}层")
        if book.location.position:
            location_parts.append(book.location.position)

        location_text = " → ".join(location_parts)

        if book.location.full_location_code:
            location_text += f"\n完整位置码：{book.location.full_location_code}"

    lines.append(f"书架位置：{location_text}")
    lines.append(f"简介：{book.description or '暂无简介'}")

    return "\n".join(lines)


def export_single_book(book_id, output_dir='bookdata'):
    """
    导出单本图书为TXT文件并同步到 AnythingLLM

    参数：
        book_id: 图书ID
        output_dir: 输出目录（相对路径或绝对路径）

    返回：
        bool: 是否成功
    """
    # 确保输出目录存在
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(os.path.dirname(__file__), output_dir)

    os.makedirs(output_dir, exist_ok=True)

    try:
        with app.app_context():
            book = Book.query.get(book_id)
            if not book:
                print(f"[警告] 图书ID {book_id} 不存在，跳过导出")
                return False

            # 生成文件名：使用ID（固定不变）
            filename = f"{book.id:04d}.txt"
            filepath = os.path.join(output_dir, filename)

            # 如果旧文件存在且文件名不同（之前用书名命名），先删除所有匹配的旧文件
            old_pattern = os.path.join(output_dir, f"{book.id:04d}_*.txt")
            for old_file in glob.glob(old_pattern):
                try:
                    os.remove(old_file)
                    print(f"删除旧TXT文件：{os.path.basename(old_file)}")
                except Exception as e:
                    print(f"[警告] 删除旧文件失败 {old_file}: {e}")

            # 构建内容
            content = _build_book_content(book)

            # 写入文件（UTF-8编码）
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"✅ TXT导出成功：{filename}")

            # 同步到 AnythingLLM（非阻塞，失败不影响）
            try:
                from utils.anythingllm_client import get_anythingllm_client
                client = get_anythingllm_client()
                sync_success = client.sync_book_document(book_id, filepath)
                if sync_success:
                    print(f"✅ AnythingLLM 同步成功")
                else:
                    print(f"[警告] AnythingLLM 同步失败，但TXT已导出")
            except Exception as e:
                print(f"[警告] AnythingLLM 同步异常: {e}")

            return True

    except Exception as e:
        print(f"[错误] 导出失败 (book_id={book_id}): {e}")
        return False


def export_books_to_txt(output_dir='bookdata'):
    """
    导出所有图书为TXT文件

    参数：
        output_dir: 输出目录（相对路径或绝对路径）
    """
    # 确保输出目录存在
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(os.path.dirname(__file__), output_dir)

    os.makedirs(output_dir, exist_ok=True)

    with app.app_context():
        # 查询所有图书（按ID排序）
        books = Book.query.order_by(Book.id).all()

        exported_count = 0
        missing_location = 0

        for book in books:
            # 构建文本内容
            content = _build_book_content(book)

            # 生成文件名：使用ID（固定格式）
            filename = f"{book.id:04d}.txt"
            filepath = os.path.join(output_dir, filename)

            # 写入文件（UTF-8编码）
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            exported_count += 1
            print(f"已导出：{filename}")

        print(f"\n[成功] 导出完成！")
        print(f"[书本数] 总共导出：{exported_count} 本书")
        print(f"[注意] 未设置位置：{missing_location} 本")
        print(f"[目录] 输出目录：{output_dir}")


if __name__ == '__main__':
    export_books_to_txt()

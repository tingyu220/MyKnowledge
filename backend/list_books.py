# -*- coding: utf-8 -*-
"""
查看当前数据库中的图书信息
"""

from app import app, db
from models import Book, BookLocation, Bookshelf

def list_books():
    with app.app_context():
        books = Book.query.order_by(Book.id).all()
        print(f"📚 数据库中共有 {len(books)} 本书\n")
        print("=" * 80)
        for book in books:
            print(f"ID: {book.id:04d}")
            print(f"  书名: {book.title}")
            print(f"  作者: {book.author}")
            print(f"  分类: {book.category}")
            print(f"  位置: ", end="")
            if book.location and book.location.bookshelf:
                shelf = book.location.bookshelf
                print(f"{shelf.room} → {shelf.name} → 第{book.location.layer}层 → {book.location.position}")
            else:
                print("未设置")
            print("-" * 80)

if __name__ == '__main__':
    list_books()

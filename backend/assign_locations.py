# -*- coding: utf-8 -*-
"""
为现有图书添加书架位置信息（不添加新书）
"""

from app import app, db
from models import Book, Bookshelf, BookLocation

def assign_locations_to_existing_books():
    """
    为数据库中已存在的图书分配书架位置
    """
    with app.app_context():
        # 查找或创建默认书架
        shelf = Bookshelf.query.filter_by(code='A001').first()
        if not shelf:
            shelf = Bookshelf(
                user_id=1,
                name='文学书架',
                code='A001',
                room='书房',
                layer_count=5,
                sort_order=1,
                note='默认文学书架'
            )
            db.session.add(shelf)
            db.session.flush()
            print("创建默认书架：书房-文学书架")
        else:
            print(f"使用现有书架：{shelf.room}-{shelf.name}")
        
        # 获取所有没有位置的图书
        books_without_location = []
        all_books = Book.query.all()
        for book in all_books:
            if not book.location:
                books_without_location.append(book)
        
        print(f"\n找到 {len(books_without_location)} 本没有位置的图书")
        
        # 为没有位置的图书自动分配位置
        layer = 1
        position_map = ['左侧第1本', '右侧第1本', '左侧第2本', '右侧第2本', '左侧第3本', '右侧第3本']
        
        for i, book in enumerate(books_without_location):
            pos_idx = i % len(position_map)
            
            loc = BookLocation(
                book_id=book.id,
                bookshelf_id=shelf.id,
                layer=layer,
                position=position_map[pos_idx],
                full_location_code=f'{shelf.code}-{layer:02d}-{pos_idx+1}'
            )
            db.session.add(loc)
            print(f"分配位置：《{book.title}》 → {shelf.room}/{shelf.name} 第{layer}层 {position_map[pos_idx]}")
            
            # 每3本换一层
            if (i + 1) % 3 == 0:
                layer += 1
        
        # 提交
        db.session.commit()
        print(f"\n[完成] 已为 {len(books_without_location)} 本书分配位置")
        print(f"[书架] {shelf.room} - {shelf.name} (代码: {shelf.code})")

if __name__ == '__main__':
    assign_locations_to_existing_books()

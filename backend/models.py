# -*- coding: utf-8 -*-
"""
数据库模型定义
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import SmallInteger
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    """用户表"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=True, unique=True)  # 允许为空，MySQL中多个NULL不算重复
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    books = db.relationship('Book', backref='user', lazy=True, cascade='all, delete-orphan')
    ebooks = db.relationship('Ebook', backref='user', lazy=True, cascade='all, delete-orphan')
    bookshelves = db.relationship('Bookshelf', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Book(db.Model):
    """图书表"""
    __tablename__ = 'book'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    isbn = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200))
    publisher = db.Column(db.String(200))
    publish_date = db.Column(db.String(50))
    description = db.Column(db.Text)
    cover_url = db.Column(db.String(500))
    category = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
# 关联关系
    tags = db.relationship('BookTag', backref='book', lazy=True, cascade='all, delete-orphan')
    ebooks = db.relationship('Ebook', backref='book', lazy=True)
    location = db.relationship(
        'BookLocation',
        back_populates='book',
        uselist=False,
        cascade='all, delete-orphan',
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'isbn': self.isbn,
            'title': self.title,
            'author': self.author,
            'publisher': self.publisher,
            'publish_date': self.publish_date,
            'description': self.description,
            'cover_url': self.cover_url,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'tags': [tag.tag.tag_name for tag in self.tags if tag.tag]
        }

class Ebook(db.Model):
    """电子书表"""
    __tablename__ = 'ebook'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=True)
    file_path = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(200), nullable=False)
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'book_id': self.book_id,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }


class Tag(db.Model):
    """标签表"""
    __tablename__ = 'tag'
    
    id = db.Column(db.Integer, primary_key=True)
    tag_name = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 关联关系
    books = db.relationship('BookTag', backref='tag', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'tag_name': self.tag_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class BookTag(db.Model):
    """图书标签关联表"""
    __tablename__ = 'book_tag'
    
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('book_id', 'tag_id', name='_book_tag_uc'),)


class Bookshelf(db.Model):
    """用户书架（物理位置：房间/编号/层等元数据）"""
    __tablename__ = 'bookshelf'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), nullable=False)
    room = db.Column(db.String(100))
    layer_count = db.Column(SmallInteger)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    locations = db.relationship('BookLocation', back_populates='bookshelf', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (db.UniqueConstraint('user_id', 'code', name='uk_bookshelf_user_code'),)


class BookLocation(db.Model):
    """图书在书架上的位置（一书一条）"""
    __tablename__ = 'book_location'

    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False, unique=True)
    bookshelf_id = db.Column(db.Integer, db.ForeignKey('bookshelf.id'), nullable=False)
    layer = db.Column(SmallInteger, nullable=False)
    position = db.Column(db.String(100))
    full_location_code = db.Column(db.String(200))
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    book = db.relationship('Book', back_populates='location')
    bookshelf = db.relationship('Bookshelf', back_populates='locations')


class ChatMessage(db.Model):
    """AI对话历史记录"""
    __tablename__ = 'chat_message'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    message_type = db.Column(db.String(10), nullable=False)  # 'user' 或 'ai'
    content = db.Column(db.Text, nullable=False)
    recommendations = db.Column(db.Text)  # JSON格式存储推荐结果
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        import json
        recs = []
        if self.recommendations:
            try:
                recs = json.loads(self.recommendations)
            except:
                recs = []
        return {
            'id': self.id,
            'type': self.message_type,
            'content': self.content,
            'recommendations': recs,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class AnythingLLMDoc(db.Model):
    """AnythingLLM 文档映射表"""
    __tablename__ = 'anythingllm_doc'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), unique=True, nullable=False)
    location = db.Column(db.String(500), nullable=False, comment='AnythingLLM 内部文档路径')
    filename = db.Column(db.String(100), nullable=False, comment='文件名')
    uploaded_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now(), comment='上传时间')

    # 关联关系
    book = db.relationship('Book', backref='anythingllm_doc', lazy=True, uselist=False)

    def to_dict(self):
        return {
            'id': self.id,
            'book_id': self.book_id,
            'location': self.location,
            'filename': self.filename,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }

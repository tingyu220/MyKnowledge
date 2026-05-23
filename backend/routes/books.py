# -*- coding: utf-8 -*-
"""
图书管理路由
"""
import logging

import requests
from flask import Blueprint, request, jsonify, session, Response
from models import db, Book, Tag, BookTag, BookLocation, Bookshelf
from routes.auth import login_required

logger = logging.getLogger(__name__)
# 封面代理请求的 User-Agent，避免部分站点拦截
COVER_PROXY_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
from utils.isbn_validator import validate_isbn, normalize_isbn
from utils.book_scraper import scrape_book_info
from utils.ai_service import analyze_book
import re

books_bp = Blueprint('books', __name__)

# 与 models.Book 字段长度一致，入库前截断以防 "Data too long"
_BOOK_FIELD_MAX = {
    'title': 200, 'author': 200, 'publisher': 200,
    'publish_date': 50, 'cover_url': 500, 'category': 500,
}


def _truncate(s, max_len):
    if not s or max_len <= 0:
        return s or ''
    return (s.strip() or '')[:max_len]


def _auto_assign_location(book):
    """
    为新添加的图书自动分配书架位置
    如果分类为计算机，放到计算机书架；否则放到文学书架
    """
    try:
        category = (book.category or '').lower()
        user_id = book.user_id

        # 根据分类选择书架
        if '计算机' in category or '编程' in category or 'Python' in category:
            shelf = Bookshelf.query.filter_by(user_id=user_id, code='A002').first()
            if not shelf:
                shelf = Bookshelf(
                    user_id=user_id,
                    name='计算机书架',
                    code='A002',
                    room='书房',
                    layer_count=5,
                    sort_order=2,
                    note='计算机技术书架'
                )
                db.session.add(shelf)
                db.session.flush()
        else:
            shelf = Bookshelf.query.filter_by(user_id=user_id, code='A001').first()
            if not shelf:
                shelf = Bookshelf(
                    user_id=user_id,
                    name='文学书架',
                    code='A001',
                    room='书房',
                    layer_count=5,
                    sort_order=1,
                    note='文学类书架'
                )
                db.session.add(shelf)
                db.session.flush()

        # 计算位置（找当前层数最多的位置）
        existing_locs = BookLocation.query.filter_by(bookshelf_id=shelf.id).all()
        layer = 1
        if existing_locs:
            max_layer = max(loc.layer for loc in existing_locs)
            count_in_layer = sum(1 for loc in existing_locs if loc.layer == max_layer)
            if count_in_layer >= 3:
                layer = max_layer + 1
            else:
                layer = max_layer

        pos_idx = len([loc for loc in existing_locs if loc.layer == layer])

        positions = ['左侧第1本', '右侧第1本', '左侧第2本', '右侧第2本', '左侧第3本', '右侧第3本']
        position = positions[pos_idx % len(positions)]

        location = BookLocation(
            book_id=book.id,
            bookshelf_id=shelf.id,
            layer=layer,
            position=position,
            full_location_code=f'{shelf.code}-{layer:02d}-{pos_idx+1}'
        )
        db.session.add(location)
        db.session.commit()
        print(f"[LOCATION] Auto-assigned: {book.title[:20]} -> {shelf.name} Layer {layer} {position}")
        return True
    except Exception as e:
        print(f"[LOCATION] Auto-assign failed: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return False


def _normalize_publish_date(date_str):
    """
    规范化出版日期格式
    支持：'2002' -> '2002'（保持原样，因为模型是 String）
    如果数据库是 DATE 类型，需要转换为 '2002-01-01'，但当前模型是 String(50)
    """
    if not date_str:
        return ''
    date_str = str(date_str).strip()
    # 如果只有年份（4位数字），保持原样（String 类型可以存储）
    # 如果数据库是 DATE 类型，这里可以转换为 'YYYY-01-01'，但当前模型是 String
    return date_str


def _generate_and_save_tags(book):
    """
    为图书生成并保存标签（基于 AI 分析）
    如果分析失败，不影响图书添加（静默失败）
    """
    try:
        analysis_result = analyze_book(book.title, book.description or '')
        if not analysis_result:
            return

        # 保存标签到临时列表，避免在循环中修改 session
        tags_to_add = []
        
        # 更新分类（如果 AI 分析提供了更好的分类）
        ai_category = analysis_result.get('category')
        if ai_category and not book.category:
            book.category = _truncate(ai_category, _BOOK_FIELD_MAX.get('category', 0))

        # 生成标签列表
        tags = analysis_result.get('tags', [])
        for tag_name in tags:
            if not tag_name or not isinstance(tag_name, str):
                continue
            tag_name = tag_name.strip()[:50]
            if not tag_name:
                continue
            tags_to_add.append(tag_name)

        # 查找或创建标签，并关联
        for tag_name in tags_to_add:
            tag = Tag.query.filter_by(tag_name=tag_name).first()
            if not tag:
                tag = Tag(tag_name=tag_name)
                db.session.add(tag)
                db.session.flush()

            existing_link = BookTag.query.filter_by(book_id=book.id, tag_id=tag.id).first()
            if not existing_link:
                book_tag = BookTag(book_id=book.id, tag_id=tag.id)
                db.session.add(book_tag)

        db.session.commit()
        print(f"[TAG] 标签生成成功，共 {len(tags_to_add)} 个标签")
    except Exception as e:
        import traceback
        print(f"[TAG] AI 标签生成失败 (book_id={book.id}): {str(e)[:100]}")
        try:
            db.session.rollback()
        except:
            pass

@books_bp.route('', methods=['GET'])
@login_required
def get_books():
    """获取图书列表"""
    user_id = session.get('user_id')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')
    
    query = Book.query.filter_by(user_id=user_id)
    
    # 搜索过滤
    if search:
        query = query.filter(
            db.or_(
                Book.title.like(f'%{search}%'),
                Book.author.like(f'%{search}%'),
                Book.isbn.like(f'%{search}%')
            )
        )
    
    # 分类过滤
    if category:
        query = query.filter_by(category=category)
    
    # 分页
    pagination = query.order_by(Book.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    books = [book.to_dict() for book in pagination.items]
    
    return jsonify({
        'books': books,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200

@books_bp.route('/<int:book_id>', methods=['GET'])
@login_required
def get_book(book_id):
    """获取图书详情"""
    user_id = session.get('user_id')
    book = Book.query.filter_by(id=book_id, user_id=user_id).first()
    
    if not book:
        return jsonify({'error': '图书不存在'}), 404
    
    return jsonify({'book': book.to_dict()}), 200


@books_bp.route('/<int:book_id>/cover', methods=['GET'])
@login_required
def get_book_cover(book_id):
    """
    代理获取图书封面图片。
    后端请求外部 URL 并返回图片内容，避免前端直接加载外部图片时的
    CORS、Referer 拦截、混合内容等问题。
    """
    user_id = session.get('user_id')
    book = Book.query.filter_by(id=book_id, user_id=user_id).first()
    if not book:
        return jsonify({'error': '图书不存在'}), 404

    cover_url = (book.cover_url or '').strip()
    if not cover_url:
        return jsonify({'error': '无封面'}), 404

    try:
        if cover_url.startswith('http://'):
            cover_url = 'https://' + cover_url[5:]
    except Exception:
        pass

    # 构建模拟浏览器的请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://book.douban.com/',
    }

    try:
        resp = requests.get(
            cover_url,
            headers=headers,
            timeout=20,
            stream=True,
        )
        
        # 处理 418 错误（被反爬拦截）
        if resp.status_code == 418:
            # 尝试移除 Referer 重试
            retry_headers = headers.copy()
            del retry_headers['Referer']
            resp = requests.get(
                cover_url,
                headers=retry_headers,
                timeout=20,
                stream=True,
            )
        
        resp.raise_for_status()
        content_type = (resp.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if 'text/html' in content_type or ('image/' not in content_type and content_type):
            logger.warning('封面代理返回非图片内容 book_id=%s content_type=%s', book_id, content_type)
            return jsonify({'error': '封面加载失败'}), 502
        if 'image/' not in content_type:
            content_type = 'image/jpeg'
        return Response(resp.content, mimetype=content_type)
    except requests.RequestException as e:
        logger.warning('封面代理请求失败 book_id=%s url=%s: %s', book_id, cover_url, e)
        return jsonify({'error': '封面加载失败'}), 502


@books_bp.route('/add', methods=['POST'])
@login_required
def add_book():
    """
    通过 ISBN 添加图书。
    流程：接收 ISBN -> 校验格式 -> 标准化 -> 查库是否已有 -> 无则爬取 -> 解析 -> 入库。
    支持手动模式：前端传 manual=true 时，接收手动输入的图书信息。
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': '用户未登录'}), 401
        
        data = request.get_json(silent=True) or {}
        isbn_raw = (data.get('isbn') or '').strip()
        
        if not isbn_raw:
            return jsonify({'error': 'ISBN不能为空'}), 400
        
        # 手动输入模式：允许不校验 ISBN 格式（用户可能手动输入）
        is_manual = data.get('manual', False)
        
        if not is_manual:
            if not validate_isbn(isbn_raw):
                return jsonify({'error': 'ISBN格式不正确，请使用 ISBN-10 或 ISBN-13'}), 400
            
            isbn = normalize_isbn(isbn_raw)
            if not isbn:
                return jsonify({'error': 'ISBN标准化失败'}), 400
        else:
            isbn = isbn_raw
        
        # 检查当前用户是否已存在该 ISBN
        existing_book = Book.query.filter_by(user_id=user_id, isbn=isbn).first()
        if existing_book:
            return jsonify({
                'message': '图书已存在',
                'book': existing_book.to_dict()
            }), 200
        
        # 手动模式：直接使用传入的图书信息
        if is_manual:
            title = (data.get('title') or '').strip()
            if not title:
                return jsonify({'error': '图书标题不能为空'}), 400

            book_info = {
                'title': title,
                'author': data.get('author', ''),
                'publisher': data.get('publisher', ''),
                'publish_date': data.get('publish_date', ''),
                'description': data.get('description', ''),
                'cover_url': data.get('cover_url', ''),
                'category': data.get('category', '')
            }
        else:
            # 爬取图书信息
            try:
                book_info = scrape_book_info(isbn)
                if not book_info:
                    # API 无法获取时，返回特殊状态码，提示用户手动输入
                    return jsonify({
                        'error': '未能找到图书信息，请尝试手动输入',
                        'isbn': isbn,
                        'requires_manual': True
                    }), 200
                
                title = (book_info.get('title') or '').strip()
                if not title:
                    return jsonify({
                        'error': '未能获取图书标题信息',
                        'isbn': isbn,
                        'requires_manual': True
                    }), 200
            except Exception as e:
                import traceback
                print(f"爬取图书信息异常: {traceback.format_exc()}")
                return jsonify({
                    'error': '获取图书信息失败，请尝试手动输入',
                    'isbn': isbn,
                    'requires_manual': True
                }), 200
        
        # 入库前按字段最大长度截断，避免 "Data too long for column"
        def _t(k, v):
            return _truncate(v, _BOOK_FIELD_MAX.get(k, 0))
        
        # 简介特殊处理：截断到 2000 字以内
        description_raw = (book_info.get('description') or '').strip()
        if len(description_raw) > 2000:
            description = description_raw[:2000].rsplit(' ', 1)[0] + '...'  # 在单词边界截断
        else:
            description = description_raw
        
        book = Book(
            user_id=user_id,
            isbn=isbn,
            title=_t('title', title),
            author=_t('author', book_info.get('author')),
            publisher=_t('publisher', book_info.get('publisher')),
            publish_date=_normalize_publish_date(book_info.get('publish_date')),
            description=description,
            cover_url=_t('cover_url', book_info.get('cover_url')),
            category=_t('category', book_info.get('category'))
        )
        
        try:
            print(f"[ADD_BOOK] 开始添加图书: user_id={user_id}, isbn={isbn}, manual={is_manual}")
            db.session.add(book)
            print(f"[ADD_BOOK] Book 已加入 session, id={book.id if book.id else '未分配'}")
            db.session.commit()
            print(f"[ADD_BOOK] 主事务 commit 成功, book_id={book.id}")

            # 自动分配书架位置
            print(f"[ADD_BOOK] 开始分配书架位置...")
            _auto_assign_location(book)

            # 自动生成标签（基于 AI 分析）- 独立事务，失败不影响主数据
            print(f"[ADD_BOOK] 开始生成标签...")
            _generate_and_save_tags(book)
            print(f"[ADD_BOOK] 标签生成完成")

            # 自动导出为 AnythingLLM TXT 文档（非阻塞）
            try:
                from export_books_for_anythingllm import export_single_book
                export_single_book(book.id)
                print(f"[ADD_BOOK] TXT导出完成")
            except Exception as e:
                print(f"[警告] TXT导出失败（不影响添加）: {e}")

            return jsonify({
                'message': '添加成功',
                'book': book.to_dict()
            }), 201
        except Exception as e:
            db.session.rollback()
            import traceback
            print(f"[ADD_BOOK] 数据库操作异常: {traceback.format_exc()}")
            return jsonify({'error': f'添加失败: {str(e)}'}), 500
    except Exception as e:
        import traceback
        print(f"添加图书异常: {traceback.format_exc()}")
        return jsonify({'error': f'处理请求失败: {str(e)}'}), 500

@books_bp.route('/<int:book_id>', methods=['PUT'])
@login_required
def update_book(book_id):
    """更新图书信息（手动编辑）"""
    user_id = session.get('user_id')
    book = Book.query.filter_by(id=book_id, user_id=user_id).first()
    
    if not book:
        return jsonify({'error': '图书不存在'}), 404
    
    data = request.get_json(silent=True) or {}
    
    # 更新字段（带长度限制和清理）
    if 'title' in data:
        book.title = _truncate(data['title'], _BOOK_FIELD_MAX.get('title', 0))
    if 'author' in data:
        book.author = _truncate(data['author'], _BOOK_FIELD_MAX.get('author', 0))
    if 'publisher' in data:
        book.publisher = _truncate(data['publisher'], _BOOK_FIELD_MAX.get('publisher', 0))
    if 'publish_date' in data:
        book.publish_date = _normalize_publish_date(data['publish_date'])
    if 'description' in data:
        desc = (data['description'] or '').strip()
        if len(desc) > 2000:
            desc = desc[:2000].rsplit(' ', 1)[0] + '...'
        book.description = desc
    if 'category' in data:
        book.category = _truncate(data['category'], _BOOK_FIELD_MAX.get('category', 0))
    if 'cover_url' in data:
        book.cover_url = _truncate(data['cover_url'], _BOOK_FIELD_MAX.get('cover_url', 0))

    # 标签管理：用户可调整系统生成的标签
    if 'tags' in data:
        tags_input = data['tags']
        if isinstance(tags_input, list):
            tag_names = [str(t).strip()[:50] for t in tags_input if t]
            tag_names = list(dict.fromkeys(tag_names))[:10]  # 去重，最多 10 个
            # 删除原有关联
            BookTag.query.filter_by(book_id=book_id).delete()
            for name in tag_names:
                if not name:
                    continue
                tag = Tag.query.filter_by(tag_name=name).first()
                if not tag:
                    tag = Tag(tag_name=name)
                    db.session.add(tag)
                    db.session.flush()
                db.session.add(BookTag(book_id=book_id, tag_id=tag.id))
    
    try:
        db.session.commit()

        # 自动导出为 AnythingLLM TXT 文档（非阻塞）
        try:
            from export_books_for_anythingllm import export_single_book
            export_single_book(book.id)
            print(f"[UPDATE_BOOK] TXT导出完成")
        except Exception as e:
            print(f"[警告] TXT导出失败: {e}")

        return jsonify({
            'message': '更新成功',
            'book': book.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"更新图书异常: {traceback.format_exc()}")
        return jsonify({'error': f'更新失败: {str(e)}'}), 500


@books_bp.route('/<int:book_id>/refresh', methods=['POST'])
@login_required
def refresh_book(book_id):
    """
    重新爬取并更新图书信息（基于 ISBN）
    用于更新简介、封面等可能变化的信息
    """
    user_id = session.get('user_id')
    book = Book.query.filter_by(id=book_id, user_id=user_id).first()
    
    if not book:
        return jsonify({'error': '图书不存在'}), 404
    
    if not book.isbn:
        return jsonify({'error': '图书缺少 ISBN，无法重新爬取'}), 400
    
    try:
        # 重新爬取图书信息
        book_info = scrape_book_info(book.isbn)
        if not book_info:
            return jsonify({'error': '未能获取图书信息，请检查 ISBN 是否正确或稍后重试'}), 400
        
        # 验证标题
        title = (book_info.get('title') or '').strip()
        if not title:
            return jsonify({'error': '未能获取图书标题信息'}), 400
        
        # 入库前按字段最大长度截断
        def _t(k, v):
            return _truncate(v, _BOOK_FIELD_MAX.get(k, 0))
        
        # 简介特殊处理：截断到 2000 字以内
        description_raw = (book_info.get('description') or '').strip()
        if len(description_raw) > 2000:
            description = description_raw[:2000].rsplit(' ', 1)[0] + '...'
        else:
            description = description_raw
        
        # 更新字段（保留原有数据，只更新爬取到的信息）
        # 如果爬取到的信息更完整，则更新
        if title:
            book.title = _t('title', title)
        if book_info.get('author'):
            book.author = _t('author', book_info.get('author'))
        if book_info.get('publisher'):
            book.publisher = _t('publisher', book_info.get('publisher'))
        if book_info.get('publish_date'):
            book.publish_date = _normalize_publish_date(book_info.get('publish_date'))
        if description:
            book.description = description
        if book_info.get('cover_url'):
            book.cover_url = _t('cover_url', book_info.get('cover_url'))
        if book_info.get('category'):
            book.category = _t('category', book_info.get('category'))
        
        db.session.commit()

        # 自动导出为 AnythingLLM TXT 文档（非阻塞）
        try:
            from export_books_for_anythingllm import export_single_book
            export_single_book(book.id)
            print(f"[REFRESH_BOOK] TXT导出完成")
        except Exception as e:
            print(f"[警告] TXT导出失败: {e}")

        # 重新生成标签（基于更新后的信息）
        _generate_and_save_tags(book)

        return jsonify({
            'message': '更新成功',
            'book': book.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"重新爬取图书信息异常: {traceback.format_exc()}")
        return jsonify({'error': f'更新失败: {str(e)}'}), 500

@books_bp.route('/<int:book_id>', methods=['DELETE'])
@login_required
def delete_book(book_id):
    """删除图书（同时清理本地TXT和AnythingLLM文档）"""
    user_id = session.get('user_id')
    book = Book.query.filter_by(id=book_id, user_id=user_id).first()

    if not book:
        return jsonify({'error': '图书不存在'}), 404

    try:
        # ========== 1. 删除本地 TXT 文件 ==========
        try:
            import os
            # bookdata 在 backend/bookdata/
            backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            output_dir = os.path.join(backend_dir, 'bookdata')
            filename = f"{book.id:04d}.txt"
            filepath = os.path.join(output_dir, filename)

            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"[DELETE_BOOK] 删除TXT文件：{filename}")
            else:
                print(f"[DELETE_BOOK] TXT文件不存在：{filename}（可能从未导出）")
        except Exception as e:
            print(f"[警告] 删除TXT文件失败: {e}（继续删除流程）")

        # ========== 2. 删除 AnythingLLM 文档 ==========
        anythingllm_deleted = False
        try:
            from models import AnythingLLMDoc
            from utils.anythingllm_client import get_anythingllm_client

            doc = AnythingLLMDoc.query.filter_by(book_id=book_id).first()
            if doc:
                client = get_anythingllm_client()
                success = client.delete_document(doc.location)
                if success:
                    print(f"[DELETE_BOOK] 删除AnythingLLM文档：{doc.location}")
                    anythingllm_deleted = True
                else:
                    print(f"[警告] 删除AnythingLLM文档失败：{doc.location}")

                # 删除映射记录
                db.session.delete(doc)
            else:
                print(f"[DELETE_BOOK] 未找到AnythingLLM映射记录（可能从未同步）")
        except Exception as e:
            print(f"[警告] 删除AnythingLLM文档异常: {e}（继续删除流程）")

        # ========== 3. 删除数据库图书记录 ==========
        db.session.delete(book)
        db.session.commit()

        print(f"[DELETE_BOOK] 图书删除成功：ID={book_id}, 书名={book.title}")
        return jsonify({'message': '删除成功'}), 200

    except Exception as e:
        db.session.rollback()
        import traceback
        print(f"删除图书异常: {traceback.format_exc()}")
        return jsonify({'error': f'删除失败: {str(e)}'}), 500

@books_bp.route('/tags', methods=['GET'])
@login_required
def get_tags():
    """获取系统中已有的标签列表（用于标签选择/自动补全）"""
    tags = Tag.query.order_by(Tag.tag_name).all()
    return jsonify({'tags': [t.tag_name for t in tags]}), 200


@books_bp.route('/categories', methods=['GET'])
@login_required
def get_categories():
    """获取所有分类"""
    user_id = session.get('user_id')
    categories = db.session.query(Book.category).filter_by(user_id=user_id).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return jsonify({'categories': categories}), 200


# -*- coding: utf-8 -*-
"""
AI分析模块路由
"""
from flask import Blueprint, request, jsonify, session
from models import db, Book, Tag, BookTag, ChatMessage
from routes.auth import login_required
from utils.ai_service import analyze_book
from utils.assistant_service import get_assistant_service
from utils.enhanced_recommend import enhanced_recommend_response, enhanced_qa, update_rag_index
from utils.cache import get_isbn_cache, get_api_cache

ai_bp = Blueprint('ai', __name__)
assistant_service = get_assistant_service()


@ai_bp.route('/analyze/<int:book_id>', methods=['POST'])
@login_required
def analyze_book_tags(book_id):
    """分析图书并生成标签"""
    user_id = session.get('user_id')
    book = Book.query.filter_by(id=book_id, user_id=user_id).first()

    if not book:
        return jsonify({'error': '图书不存在'}), 404

    try:
        # 调用分析（基于规则）
        analysis_result = analyze_book(book.title, book.description or '')

        if not analysis_result:
            return jsonify({'error': '分析失败'}), 500

        # 保存分类
        if analysis_result.get('category'):
            book.category = analysis_result['category']

        # 保存标签
        tags = analysis_result.get('tags', [])
        for tag_name in tags:
            # 查找或创建标签
            tag = Tag.query.filter_by(tag_name=tag_name).first()
            if not tag:
                tag = Tag(tag_name=tag_name)
                db.session.add(tag)
                db.session.flush()

            # 检查是否已关联
            existing_link = BookTag.query.filter_by(book_id=book_id, tag_id=tag.id).first()
            if not existing_link:
                book_tag = BookTag(book_id=book_id, tag_id=tag.id)
                db.session.add(book_tag)

        db.session.commit()

        # 更新RAG索引（后台操作）
        try:
            user_books = Book.query.filter_by(user_id=user_id).all()
            update_rag_index(user_books)
        except Exception as e:
            print(f"RAG索引更新失败: {e}")

        return jsonify({
            'message': '分析完成',
            'result': analysis_result,
            'book': book.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'分析失败: {str(e)}'}), 500


@ai_bp.route('/recommend', methods=['POST'])
@login_required
def recommend():
    """图书推荐（使用RAG增强）"""
    user_id = session.get('user_id')
    data = request.get_json()

    query = data.get('query', '')
    limit = data.get('limit', 5)

    if not query:
        return jsonify({'error': '查询内容不能为空'}), 400

    try:
        # 获取用户的所有图书
        user_books = Book.query.filter_by(user_id=user_id).all()

        if not user_books:
            return jsonify({
                'message': '您还没有添加图书',
                'recommendations': []
            }), 200

        # 使用增强推荐（RAG + 缓存）
        result = enhanced_recommend_response(query, user_books, limit)

        return jsonify({
            'query': query,
            'answer': result.get('answer', ''),
            'recommendations': result.get('recommendations', []),
            'match_level': result.get('match_level', 'none'),
        }), 200
    except Exception as e:
        return jsonify({'error': f'推荐失败: {str(e)}'}), 500


@ai_bp.route('/qa', methods=['POST'])
@login_required
def qa():
    """问答交互（使用RAG增强）"""
    user_id = session.get('user_id')
    data = request.get_json()

    question = data.get('question', '')

    if not question:
        return jsonify({'error': '问题不能为空'}), 400

    try:
        # 获取用户的所有图书
        user_books = Book.query.filter_by(user_id=user_id).all()

        if not user_books:
            return jsonify({
                'message': '您还没有添加图书',
                'recommendations': []
            }), 200

        # 使用增强问答（RAG + 缓存）
        result = enhanced_qa(question, user_books)

        return jsonify({
            'question': question,
            'answer': result.get('answer', ''),
            'recommendations': result.get('recommendations', []),
        }), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'问答失败: {str(e)}'}), 500


@ai_bp.route('/assistant/chat', methods=['POST'])
@login_required
def assistant_chat():
    """统一 AI 图书助手入口"""
    user_id = session.get('user_id')
    data = request.get_json() or {}

    message = (data.get('message') or '').strip()
    recent_messages = data.get('recent_messages') or []
    awaiting_mood = bool(data.get('awaiting_mood'))

    if not message:
        return jsonify({'error': '消息不能为空'}), 400

    try:
        user_books = Book.query.filter_by(user_id=user_id).all()
        result = assistant_service.process_message(
            message=message,
            user_books=user_books,
            recent_messages=recent_messages,
            awaiting_mood=awaiting_mood,
        )
        return jsonify(result), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'助手处理失败: {str(e)}'}), 500


@ai_bp.route('/cache/stats', methods=['GET'])
@login_required
def cache_stats():
    """获取缓存统计（调试用）"""
    try:
        api_cache = get_api_cache()
        stats = api_cache.get_stats()
        return jsonify({
            'cache_size': stats.get('size', 0),
            'hit_rate': f"{stats.get('hit_rate', 0)}%",
            'hits': stats.get('hits', 0),
            'misses': stats.get('misses', 0),
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取统计失败: {str(e)}'}), 500


@ai_bp.route('/cache/clear', methods=['POST'])
@login_required
def clear_cache():
    """清空推荐缓存"""
    try:
        api_cache = get_api_cache()
        api_cache.cache.clear()
        return jsonify({'message': '缓存已清空'}), 200
    except Exception as e:
        return jsonify({'error': f'清空缓存失败: {str(e)}'}), 500


@ai_bp.route('/chat/history', methods=['GET'])
@login_required
def get_chat_history():
    """获取对话历史"""
    user_id = session.get('user_id')
    limit = request.args.get('limit', 50, type=int)

    try:
        messages = ChatMessage.query.filter_by(user_id=user_id)\
            .order_by(ChatMessage.created_at.desc())\
            .limit(limit)\
            .all()
        return jsonify({
            'messages': [m.to_dict() for m in reversed(messages)]
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取历史失败: {str(e)}'}), 500


@ai_bp.route('/chat/messages', methods=['POST'])
@login_required
def save_chat_message():
    """保存对话消息"""
    user_id = session.get('user_id')
    data = request.get_json()

    message_type = data.get('type')  # 'user' 或 'ai'
    content = data.get('content', '')
    recommendations = data.get('recommendations', [])

    if not message_type or not content:
        return jsonify({'error': '消息类型和内容不能为空'}), 400

    if message_type not in ('user', 'ai'):
        return jsonify({'error': '消息类型无效'}), 400

    try:
        import json
        msg = ChatMessage(
            user_id=user_id,
            message_type=message_type,
            content=content,
            recommendations=json.dumps(recommendations, ensure_ascii=False)
        )
        db.session.add(msg)
        db.session.commit()

        return jsonify({
            'message': '消息已保存',
            'data': msg.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'保存失败: {str(e)}'}), 500


@ai_bp.route('/chat/history', methods=['DELETE'])
@login_required
def clear_chat_history():
    """清空对话历史"""
    user_id = session.get('user_id')

    try:
        ChatMessage.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({'message': '对话历史已清空'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'清空失败: {str(e)}'}), 500

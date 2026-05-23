# -*- coding: utf-8 -*-
"""
ISBN 模块路由
- 接收 ISBN（扫码/手动输入）
- 校验格式，返回标准化结果
- ISBN缓存管理
"""
from flask import Blueprint, request, jsonify
from routes.auth import login_required
from utils.isbn_validator import validate_isbn, normalize_isbn
from utils.cache import get_isbn_cache, clear_all_caches

isbn_bp = Blueprint('isbn', __name__)


@isbn_bp.route('/validate', methods=['POST', 'GET'])
@login_required
def validate():
    """
    校验 ISBN 格式。
    POST: JSON { "isbn": "978-7-115-xxxxx" }
    GET:  ?isbn=9787115xxxxx
    返回: { "valid": bool, "normalized": str | null }
    """
    isbn_raw = None
    if request.method == 'POST':
        data = request.get_json() or {}
        isbn_raw = (data.get('isbn') or '').strip()
    else:
        isbn_raw = (request.args.get('isbn') or '').strip()

    if not isbn_raw:
        return jsonify({'error': 'ISBN 不能为空', 'valid': False, 'normalized': None}), 400

    normalized = normalize_isbn(isbn_raw)
    valid = validate_isbn(isbn_raw)

    return jsonify({
        'valid': valid,
        'normalized': normalized if valid else None,
    }), 200


@isbn_bp.route('/cache/stats', methods=['GET'])
@login_required
def cache_stats():
    """获取ISBN缓存统计"""
    try:
        isbn_cache = get_isbn_cache()
        stats = isbn_cache.get_stats()
        return jsonify({
            'size': stats.get('size', 0),
            'max_size': stats.get('max_size', 0),
            'hit_rate': f"{stats.get('hit_rate', 0)}%",
            'hits': stats.get('hits', 0),
            'misses': stats.get('misses', 0),
            'evictions': stats.get('evictions', 0),
        }), 200
    except Exception as e:
        return jsonify({'error': f'获取统计失败: {str(e)}'}), 500


@isbn_bp.route('/cache/clear', methods=['POST'])
@login_required
def clear_cache():
    """清空所有缓存"""
    try:
        stats = clear_all_caches()
        return jsonify({
            'message': '缓存已清空',
            'cleared_isbn_cache': stats.get('isbn_cache', {}),
            'cleared_api_cache': stats.get('api_cache', {}),
        }), 200
    except Exception as e:
        return jsonify({'error': f'清空缓存失败: {str(e)}'}), 500


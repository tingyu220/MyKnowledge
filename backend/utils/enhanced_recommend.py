# -*- coding: utf-8 -*-
"""
本地图书推荐和问答服务

只使用用户书库数据进行检索，不依赖外部联网服务。
"""
import logging
import os
import re
from typing import Any, Dict, List, Tuple

from utils.cache import get_api_cache
from utils.rag_engine import rebuild_rag_index

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 5
WEAK_FALLBACK_MESSAGE = '未查询到匹配书籍，下列是一些相关性较弱书籍：'
STRONG_MATCH_MESSAGE = '根据您的书库，以下书籍与您的需求最匹配：'

QUERY_STOPWORDS = {
    '我', '想', '想要', '看看', '阅读', '读', '一些', '有关', '相关', '方面', '类型', '推荐',
    '书', '书籍', '本书', '几本', '最近', '有没有', '适合', '可以', '帮我', '请问', '一下',
    '的', '了', '和', '与', '以及', '比较', '哪些', '什么'
}


def _safe_text(value: Any) -> str:
    return str(value or '').strip()


def _tokenize(text: str) -> List[str]:
    text = _safe_text(text)
    if not text:
        return []

    try:
        from jieba import cut
        raw_tokens = list(cut(text, cut_all=False))
    except Exception:
        raw_tokens = re.findall(r'[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}|\d{4,}', text)

    tokens = []
    for token in raw_tokens:
        token = _safe_text(token).lower()
        if len(token) < 2 or token in QUERY_STOPWORDS:
            continue
        tokens.append(token)

    seen = set()
    unique_tokens = []
    for token in tokens:
        if token not in seen:
            seen.add(token)
            unique_tokens.append(token)
    return unique_tokens


def _extract_book_tags(book: Any) -> List[str]:
    if hasattr(book, 'to_dict'):
        try:
            tags = book.to_dict().get('tags', [])
            return [_safe_text(tag) for tag in tags if _safe_text(tag)]
        except Exception:
            pass

    tags = []
    for rel in getattr(book, 'tags', []) or []:
        tag_name = ''
        if hasattr(rel, 'tag') and getattr(rel.tag, 'tag_name', None):
            tag_name = rel.tag.tag_name
        elif hasattr(rel, 'tag_name'):
            tag_name = rel.tag_name
        if _safe_text(tag_name):
            tags.append(_safe_text(tag_name))
    return tags


def _book_to_dict(book: Any) -> Dict[str, Any]:
    if hasattr(book, 'to_dict'):
        data = book.to_dict()
    else:
        data = {
            'id': getattr(book, 'id', None),
            'isbn': getattr(book, 'isbn', ''),
            'title': getattr(book, 'title', ''),
            'author': getattr(book, 'author', ''),
            'publisher': getattr(book, 'publisher', ''),
            'publish_date': getattr(book, 'publish_date', ''),
            'description': getattr(book, 'description', ''),
            'cover_url': getattr(book, 'cover_url', ''),
            'category': getattr(book, 'category', ''),
            'created_at': getattr(book, 'created_at', None),
            'updated_at': getattr(book, 'updated_at', None),
            'tags': _extract_book_tags(book),
            'location': '',
            'location_code': '',
        }

    data.setdefault('tags', _extract_book_tags(book))
    location, location_code = _resolve_book_location(book, data)
    data['location'] = location
    data['location_code'] = location_code
    return data


def _resolve_book_location(book: Any, book_data: Dict[str, Any]) -> Tuple[str, str]:
    direct_location = _safe_text(book_data.get('location'))
    direct_code = _safe_text(book_data.get('location_code'))
    if direct_location or direct_code:
        return direct_location, direct_code

    location_rel = getattr(book, 'location', None)
    if location_rel is not None:
        bookshelf = getattr(location_rel, 'bookshelf', None)
        parts = []
        room = _safe_text(getattr(bookshelf, 'room', ''))
        shelf_name = _safe_text(getattr(bookshelf, 'name', ''))
        layer = getattr(location_rel, 'layer', None)
        position = _safe_text(getattr(location_rel, 'position', ''))
        if room:
            parts.append(room)
        if shelf_name:
            parts.append(shelf_name)
        if layer:
            parts.append(f'第{layer}层')
        if position:
            parts.append(position)
        if parts:
            return ' → '.join(parts), _safe_text(getattr(location_rel, 'full_location_code', ''))

    book_id = book_data.get('id') or getattr(book, 'id', None)
    if not book_id:
        return '', ''
    return _read_location_from_bookdata(book_id)


def _read_location_from_bookdata(book_id: Any) -> Tuple[str, str]:
    try:
        filename = f'{int(book_id):04d}.txt'
    except Exception:
        return '', ''

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(backend_dir, 'bookdata', filename)
    if not os.path.exists(file_path):
        return '', ''

    location = ''
    location_code = ''
    try:
        with open(file_path, 'r', encoding='utf-8') as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if line.startswith('书架位置：'):
                    location = line.split('：', 1)[1].strip()
                elif line.startswith('完整位置码：'):
                    location_code = line.split('：', 1)[1].strip()
                if location and location_code:
                    break
    except Exception:
        return '', ''

    return location, location_code


class EnhancedRecommendService:
    """只基于本地图书库的推荐和问答服务。"""

    def __init__(self):
        self.api_cache = get_api_cache()
        self._index_version = 0

    def update_index(self, books: List[Any]) -> None:
        rebuild_rag_index(books)
        self._index_version += 1
        logger.info("RAG索引已更新，共 %s 本书，版本 %s", len(books), self._index_version)

    def recommend_response(self, query: str, user_books: List[Any], limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
        query = _safe_text(query)
        if not user_books:
            return {
                'answer': '您还没有添加任何图书。请先添加一些图书，我才能为您提供推荐。',
                'recommendations': [],
                'match_level': 'none',
            }

        if not query:
            return {
                'answer': '请输入想看的主题、分类或标签，我会从您的书库中挑选最匹配的书。',
                'recommendations': self._recent_recommendations(user_books, limit),
                'match_level': 'recent',
            }

        cache_key = query.lower()
        cached = self.api_cache.get('recommend_v2', query=cache_key, count=limit)
        if cached:
            return cached

        result = self._build_result(query, user_books, limit)
        self.api_cache.set('recommend_v2', result, query=cache_key, count=limit)
        return result

    def recommend_books(self, query: str, user_books: List[Any], limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
        return self.recommend_response(query, user_books, limit).get('recommendations', [])

    def answer_question(self, question: str, user_books: List[Any]) -> Dict[str, Any]:
        question = _safe_text(question)
        if not user_books:
            return {
                'answer': '您还没有添加任何图书。请先添加一些图书，我才能为您提供推荐和回答。',
                'recommendations': [],
                'match_level': 'none',
            }

        cache_key = question.lower()
        cached = self.api_cache.get('qa_v2', question=cache_key)
        if cached:
            return cached

        result = self._build_result(question, user_books, DEFAULT_LIMIT)
        self.api_cache.set('qa_v2', result, question=cache_key)
        return result

    def _build_result(self, query: str, user_books: List[Any], limit: int) -> Dict[str, Any]:
        query_tokens = _tokenize(query)
        scored_books = [self._score_book(book, query, query_tokens) for book in user_books]

        strong_matches = [item for item in scored_books if item['strong_score'] > 0]
        weak_matches = [item for item in scored_books if item['strong_score'] == 0 and item['fallback_score'] > 0]

        strong_matches.sort(key=self._sort_key, reverse=True)
        weak_matches.sort(key=self._sort_key, reverse=True)

        if strong_matches:
            selected = strong_matches[:limit]
            answer = self._build_answer(STRONG_MATCH_MESSAGE, selected)
            match_level = 'strong'
        elif weak_matches:
            selected = weak_matches[:limit]
            answer = self._build_answer(WEAK_FALLBACK_MESSAGE, selected)
            match_level = 'weak'
        else:
            selected = self._recent_scored_books(user_books, limit)
            answer = self._build_answer(WEAK_FALLBACK_MESSAGE, selected)
            match_level = 'weak'

        recommendations = [self._to_recommendation(item) for item in selected]
        return {
            'answer': answer,
            'recommendations': recommendations,
            'match_level': match_level,
        }

    def _score_book(self, book: Any, query: str, query_tokens: List[str]) -> Dict[str, Any]:
        book_data = _book_to_dict(book)
        category = _safe_text(book_data.get('category')).lower()
        tags = [_safe_text(tag).lower() for tag in book_data.get('tags', []) if _safe_text(tag)]
        title = _safe_text(book_data.get('title')).lower()
        author = _safe_text(book_data.get('author')).lower()
        description = _safe_text(book_data.get('description')).lower()

        category_tag_fields = [category] + tags
        category_tag_matches = self._field_matches(query, query_tokens, category_tag_fields)
        title_author_matches = self._field_matches(query, query_tokens, [title, author])
        description_matches = self._field_matches(query, query_tokens, [description])

        desc_bonus = min(len(description), 600) / 300 if description else 0
        strong_score = category_tag_matches * 12 + (desc_bonus if category_tag_matches > 0 else 0)
        fallback_score = title_author_matches * 6 + description_matches * 3 + desc_bonus
        final_score = strong_score if strong_score > 0 else fallback_score

        reason = self._build_reason(category_tag_matches, title_author_matches, description_matches, description)

        return {
            'book': book,
            'book_data': book_data,
            'strong_score': strong_score,
            'fallback_score': fallback_score,
            'score': final_score,
            'reason': reason,
            'desc_len': len(description),
            'created_at': book_data.get('created_at') or '',
        }

    def _field_matches(self, query: str, query_tokens: List[str], fields: List[str]) -> int:
        cleaned_fields = [field for field in fields if field]
        if not cleaned_fields:
            return 0

        matches = 0
        query_lower = query.lower()
        for field in cleaned_fields:
            if query_lower and field and field in query_lower:
                matches += 2
            for token in query_tokens:
                if token in field:
                    matches += 1
        return matches

    def _build_reason(
        self,
        category_tag_matches: int,
        title_author_matches: int,
        description_matches: int,
        description: str,
    ) -> str:
        if category_tag_matches > 0:
            base = '这本书的分类和标签与您的需求高度吻合'
        elif title_author_matches > 0:
            base = '这本书与您的需求在书名或作者信息上存在直接关联'
        elif description_matches > 0:
            base = '这本书虽然没有直接命中分类标签，但简介内容与您的需求有明显关联'
        else:
            base = '当前没有更强匹配，我先把最近入库且相对接近的书提供给您参考'

        if description and len(description) >= 40 and (category_tag_matches > 0 or title_author_matches > 0):
            return f'{base}，同时这本书的简介信息较完整，便于进一步判断是否适合您'
        return base

    def _sort_key(self, item: Dict[str, Any]) -> Tuple[float, int, str]:
        return (item['score'], item['desc_len'], _safe_text(item['created_at']))

    def _to_recommendation(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'book': item['book_data'],
            'score': round(item['score'], 2),
            'reason': item['reason'],
        }

    def _build_answer(self, intro: str, scored_books: List[Dict[str, Any]]) -> str:
        lines = [intro]
        for index, item in enumerate(scored_books[:DEFAULT_LIMIT], 1):
            book = item['book_data']
            lines.append(f'{index}. 《{book.get("title") or "未知书名"}》')
            if book.get('author'):
                lines.append(f'   作者：{book["author"]}')
            if book.get('category'):
                lines.append(f'   分类：{book["category"]}')
            if book.get('tags'):
                lines.append(f'   标签：{"、".join(book["tags"][:4])}')
            if book.get('location'):
                lines.append(f'   所在位置：{book["location"]}')
            if book.get('location_code'):
                lines.append(f'   位置码：{book["location_code"]}')
            lines.append(f'   推荐理由：{item["reason"]}')
        return '\n'.join(lines)

    def _recent_scored_books(self, user_books: List[Any], limit: int) -> List[Dict[str, Any]]:
        recent_books = sorted(
            user_books,
            key=lambda book: _safe_text(_book_to_dict(book).get('created_at')),
            reverse=True,
        )[:limit]
        return [self._score_book(book, '', []) for book in recent_books]

    def _recent_recommendations(self, user_books: List[Any], limit: int) -> List[Dict[str, Any]]:
        return [self._to_recommendation(item) for item in self._recent_scored_books(user_books, limit)]

    def get_cache_stats(self) -> Dict[str, Any]:
        return self.api_cache.get_stats()


_recommend_service = EnhancedRecommendService()


def get_recommend_service() -> EnhancedRecommendService:
    return _recommend_service


def update_rag_index(books: List[Any]) -> None:
    _recommend_service.update_index(books)


def enhanced_recommend_response(query: str, user_books: List[Any], limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    return _recommend_service.recommend_response(query, user_books, limit)


def enhanced_recommend(query: str, user_books: List[Any], limit: int = DEFAULT_LIMIT) -> List[Dict[str, Any]]:
    return _recommend_service.recommend_books(query, user_books, limit)


def enhanced_qa(question: str, user_books: List[Any]) -> Dict[str, Any]:
    return _recommend_service.answer_question(question, user_books)

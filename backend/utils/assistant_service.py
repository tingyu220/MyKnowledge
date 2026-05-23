# -*- coding: utf-8 -*-
"""
统一 AI 图书助手服务

职责：
1. 使用 DeepSeek 识别用户意图
2. 只从本地图书库中检索事实
3. 基于检索结果生成简洁回答
"""
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)

DEFAULT_RECOMMEND_COUNT = 2
DEFAULT_QUERY_LIMIT = 5
DEFAULT_RECENT_LIMIT = 8

GENERIC_RECOMMEND_PATTERNS = (
    '有什么好书', '看点什么', '推荐点书', '推荐书', '想看点东西', '想看点书',
    '想看书', '看点书', '找点书', '挑点书', '你看着办', '都行', '随便'
)

RECENT_QUERY_PATTERNS = (
    '最近有什么书', '最近有什么书籍', '最近有哪些书', '最近新增了什么书',
    '最近添加了什么书', '最近添加了哪些书', '最近入库了什么书', '最近入库有哪些书'
)


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

    stopwords = {
        '我', '想', '想看', '推荐', '什么', '哪些', '有没有', '最近', '顺便', '一本到', '两本',
        '本书', '书', '书籍', '给我', '帮我', '一下', '看看', '更', '还是', '然后', '先', '再',
        '都行', '随便', '你看着办'
    }
    tokens = []
    for token in raw_tokens:
        token = _safe_text(token).lower()
        if len(token) < 2 or token in stopwords:
            continue
        tokens.append(token)
    return list(dict.fromkeys(tokens))


def _extract_book_tags(book: Any) -> List[str]:
    try:
        data = book.to_dict() if hasattr(book, 'to_dict') else {}
        tags = data.get('tags', [])
        return [_safe_text(tag) for tag in tags if _safe_text(tag)]
    except Exception:
        return []


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
        with open(file_path, 'r', encoding='utf-8') as handle:
            for raw_line in handle:
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
        }

    data.setdefault('tags', _extract_book_tags(book))
    if not data.get('location') and not data.get('location_code'):
        loc_rel = getattr(book, 'location', None)
        if loc_rel is not None:
            shelf = getattr(loc_rel, 'bookshelf', None)
            parts = []
            room = _safe_text(getattr(shelf, 'room', ''))
            shelf_name = _safe_text(getattr(shelf, 'name', ''))
            layer = getattr(loc_rel, 'layer', None)
            position = _safe_text(getattr(loc_rel, 'position', ''))
            if room:
                parts.append(room)
            if shelf_name:
                parts.append(shelf_name)
            if layer:
                parts.append(f'第{layer}层')
            if position:
                parts.append(position)
            if parts:
                data['location'] = ' → '.join(parts)
                data['location_code'] = _safe_text(getattr(loc_rel, 'full_location_code', ''))

    if not data.get('location') and not data.get('location_code'):
        data['location'], data['location_code'] = _read_location_from_bookdata(data.get('id'))
    return data


class DeepSeekAIAdapter:
    def __init__(self):
        self.enabled = bool(Config.AI_API_KEY)
        self.client = None
        if self.enabled:
            self.client = OpenAI(
                api_key=Config.AI_API_KEY,
                base_url=Config.AI_API_BASE_URL,
            )

    def interpret_intent(self, message: str, recent_messages: Optional[List[Dict[str, Any]]] = None, awaiting_mood: bool = False) -> Dict[str, Any]:
        if not self.enabled or not self.client:
            raise RuntimeError('AI adapter is not configured')

        recent_messages = recent_messages or []
        system_prompt = (
            '你是图书助手的意图识别器。'
            '请根据用户输入和最近对话，输出严格 JSON。'
            'mode 只能是 query、recommend、query_and_recommend。'
            '如果用户在表达模糊推荐需求，且信息不足，请将 needs_clarification 设为 true。'
            'search.author/title/categories/tags 只能提取用户明确提到或强相关的对象。'
            'mood_keywords 用 1-3 个简短词概括用户当前阅读心境。'
            'recommendation_count 是 0-2 的整数。'
            'basis 只能是 title、author、category_tag、mixed、mood。'
        )
        user_payload = {
            'message': message,
            'awaiting_mood': awaiting_mood,
            'recent_messages': recent_messages[-4:],
        }
        response = self.client.chat.completions.create(
            model=Config.AI_MODEL,
            temperature=0.1,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': json.dumps(user_payload, ensure_ascii=False)},
            ],
        )
        content = _safe_text(response.choices[0].message.content)
        return _extract_json_object(content)

    def compose_answer(self, payload: Dict[str, Any]) -> str:
        if not self.enabled or not self.client:
            raise RuntimeError('AI adapter is not configured')

        system_prompt = (
            '你是个人图书管理系统中的 AI 图书助手。'
            '回答必须简洁，只能依据提供的书库结果，不得编造不存在的书。'
            '如果有命中依据，请用很短的话点明，例如“按作者命中”“按分类/标签命中”。'
            '查询结果需要带所在位置；如果还有推荐，放在后面，不要长篇解释。'
        )
        response = self.client.chat.completions.create(
            model=Config.AI_MODEL,
            temperature=0.2,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
            ],
        )
        return _safe_text(response.choices[0].message.content)


def _extract_json_object(content: str) -> Dict[str, Any]:
    try:
        return json.loads(content)
    except Exception:
        match = re.search(r'\{.*\}', content, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}


class BookAssistantService:
    def __init__(self, ai_adapter: Optional[Any] = None):
        self.ai_adapter = ai_adapter or DeepSeekAIAdapter()

    def process_message(
        self,
        message: str,
        user_books: List[Any],
        recent_messages: Optional[List[Dict[str, Any]]] = None,
        awaiting_mood: bool = False,
    ) -> Dict[str, Any]:
        if not user_books:
            return {
                'mode': 'empty',
                'needs_clarification': False,
                'answer': '您的书库还是空的，先添加几本书，我再帮您查找或推荐。',
                'books': [],
                'recommendations': [],
                'display_books': [],
            }

        if self._is_recent_books_query(message):
            recent_books = self._get_recent_books(user_books, DEFAULT_RECENT_LIMIT)
            return {
                'mode': 'recent',
                'needs_clarification': False,
                'answer': self._build_recent_books_answer(recent_books),
                'books': recent_books,
                'recommendations': [],
                'display_books': recent_books,
                'intent_basis': 'recent',
            }

        intent = self._interpret_intent(message, recent_messages, awaiting_mood)
        intent = self._align_intent_with_library(message, user_books, intent)
        if self._should_force_clarification(message, intent):
            intent['mode'] = 'recommend'
            intent['needs_clarification'] = True
            intent['basis'] = 'mood'
            intent['search'] = {'author': '', 'title': '', 'categories': [], 'tags': []}

        if intent.get('needs_clarification') and not self._is_default_recommend_reply(message):
            prompt = self._build_clarification_prompt()
            return {
                'mode': 'recommend',
                'needs_clarification': True,
                'answer': prompt,
                'books': [],
                'recommendations': [],
                'display_books': [],
                'intent_basis': 'mood',
            }

        mode = intent.get('mode', 'query')
        if mode == 'query':
            matched_books = self._query_books(intent, message, user_books)
            answer = self._compose_or_fallback(
                mode=mode,
                basis=intent.get('basis', 'mixed'),
                matched_books=matched_books,
                recommendations=[],
                user_message=message,
            )
            return {
                'mode': mode,
                'needs_clarification': False,
                'answer': answer,
                'books': matched_books,
                'recommendations': [],
                'display_books': matched_books,
                'intent_basis': intent.get('basis', 'mixed'),
            }

        if mode == 'query_and_recommend':
            matched_books = self._query_books(intent, message, user_books)
            recommendations = self._recommend_from_matches(matched_books, user_books, intent)
            answer = self._compose_or_fallback(
                mode=mode,
                basis=intent.get('basis', 'mixed'),
                matched_books=matched_books,
                recommendations=recommendations,
                user_message=message,
            )
            return {
                'mode': mode,
                'needs_clarification': False,
                'answer': answer,
                'books': matched_books,
                'recommendations': recommendations,
                'display_books': self._merge_books(matched_books, recommendations),
                'intent_basis': intent.get('basis', 'mixed'),
            }

        recommendations = self._recommend_books(intent, message, user_books)
        answer = self._compose_or_fallback(
            mode='recommend',
            basis=intent.get('basis', 'mood'),
            matched_books=[],
            recommendations=recommendations,
            user_message=message,
        )
        return {
            'mode': 'recommend',
            'needs_clarification': False,
            'answer': answer,
            'books': [],
            'recommendations': recommendations,
            'display_books': recommendations,
            'intent_basis': intent.get('basis', 'mood'),
        }

    def _interpret_intent(self, message: str, recent_messages: Optional[List[Dict[str, Any]]], awaiting_mood: bool) -> Dict[str, Any]:
        try:
            intent = self.ai_adapter.interpret_intent(message, recent_messages=recent_messages, awaiting_mood=awaiting_mood) or {}
        except Exception as exc:
            logger.warning('AI 意图识别失败，回退规则判断: %s', exc)
            intent = {}

        if intent:
            intent.setdefault('search', {'author': '', 'title': '', 'categories': [], 'tags': []})
            intent.setdefault('mood_keywords', [])
            intent.setdefault('recommendation_count', DEFAULT_RECOMMEND_COUNT)
            intent.setdefault('basis', 'mixed')
            return intent

        return self._heuristic_intent(message, awaiting_mood)

    def _heuristic_intent(self, message: str, awaiting_mood: bool) -> Dict[str, Any]:
        wants_recommend = any(key in message for key in ('推荐', '适合', '先看', '顺便推荐'))
        tokens = _tokenize(message)
        generic = any(pattern in message for pattern in GENERIC_RECOMMEND_PATTERNS)
        if awaiting_mood:
            return {
                'mode': 'recommend',
                'needs_clarification': False,
                'search': {'author': '', 'title': '', 'categories': [], 'tags': []},
                'mood_keywords': tokens[:3],
                'recommendation_count': DEFAULT_RECOMMEND_COUNT,
                'basis': 'mood',
            }

        if generic or (wants_recommend and len(tokens) <= 2):
            return {
                'mode': 'recommend',
                'needs_clarification': True,
                'search': {'author': '', 'title': '', 'categories': [], 'tags': []},
                'mood_keywords': [],
                'recommendation_count': DEFAULT_RECOMMEND_COUNT,
                'basis': 'mood',
            }

        mode = 'query_and_recommend' if wants_recommend else 'query'
        return {
            'mode': mode,
            'needs_clarification': False,
            'search': {'author': '', 'title': '', 'categories': tokens[:2], 'tags': tokens[:2]},
            'mood_keywords': [],
            'recommendation_count': DEFAULT_RECOMMEND_COUNT if wants_recommend else 0,
            'basis': 'mixed',
        }

    def _align_intent_with_library(self, message: str, user_books: List[Any], intent: Dict[str, Any]) -> Dict[str, Any]:
        search = intent.get('search', {}) or {}
        has_explicit_search = any([
            _safe_text(search.get('author')),
            _safe_text(search.get('title')),
            search.get('categories'),
            search.get('tags'),
        ])

        detected = self._detect_library_entities(message, user_books)
        if not detected:
            return intent

        wants_recommend = any(key in message for key in ('推荐', '适合', '先看', '顺便推荐'))
        if has_explicit_search:
            merged = {
                'author': _safe_text(search.get('author')) or detected.get('author', ''),
                'title': _safe_text(search.get('title')) or detected.get('title', ''),
                'categories': list(dict.fromkeys((search.get('categories') or []) + detected.get('categories', []))),
                'tags': list(dict.fromkeys((search.get('tags') or []) + detected.get('tags', []))),
            }
            intent['search'] = merged
            if intent.get('basis') in ('mood', 'mixed'):
                intent['basis'] = detected.get('basis', 'mixed')
            if intent.get('mode') == 'recommend' and not wants_recommend:
                intent['mode'] = 'query'
                intent['needs_clarification'] = False
            return intent

        intent['search'] = detected
        intent['basis'] = detected.get('basis', 'mixed')
        intent['mode'] = 'query_and_recommend' if wants_recommend else 'query'
        intent['needs_clarification'] = False
        if not wants_recommend:
            intent['recommendation_count'] = 0
        return intent

    def _detect_library_entities(self, message: str, user_books: List[Any]) -> Dict[str, Any]:
        message_text = _safe_text(message).lower()
        if not message_text:
            return {}

        authors = []
        titles = []
        categories = []
        tags = []
        for raw_book in user_books:
            book = _book_to_dict(raw_book)
            author = _safe_text(book.get('author'))
            title = _safe_text(book.get('title'))
            category = _safe_text(book.get('category'))
            for tag in book.get('tags', []):
                tag_text = _safe_text(tag)
                if tag_text and tag_text.lower() in message_text and tag_text not in tags:
                    tags.append(tag_text)
            if author and author.lower() in message_text and author not in authors:
                authors.append(author)
            if title and title.lower() in message_text and title not in titles:
                titles.append(title)
            if category and category.lower() in message_text and category not in categories:
                categories.append(category)

        if not any([authors, titles, categories, tags]):
            return {}

        basis = 'mixed'
        if authors and not any([titles, categories, tags]):
            basis = 'author'
        elif titles and not any([authors, categories, tags]):
            basis = 'title'
        elif (categories or tags) and not any([authors, titles]):
            basis = 'category_tag'

        return {
            'author': authors[0] if authors else '',
            'title': titles[0] if titles else '',
            'categories': categories[:3],
            'tags': tags[:4],
            'basis': basis,
        }

    def _query_books(self, intent: Dict[str, Any], message: str, user_books: List[Any]) -> List[Dict[str, Any]]:
        search = intent.get('search', {})
        author = _safe_text(search.get('author')).lower()
        title = _safe_text(search.get('title')).lower()
        categories = [_safe_text(item).lower() for item in search.get('categories', []) if _safe_text(item)]
        tags = [_safe_text(item).lower() for item in search.get('tags', []) if _safe_text(item)]
        query_tokens = _tokenize(message)

        scored = []
        for raw_book in user_books:
            book = _book_to_dict(raw_book)
            score = 0
            title_text = _safe_text(book.get('title')).lower()
            author_text = _safe_text(book.get('author')).lower()
            category_text = _safe_text(book.get('category')).lower()
            tag_texts = [_safe_text(tag).lower() for tag in book.get('tags', [])]
            description_text = _safe_text(book.get('description')).lower()

            if title and title in title_text:
                score += 100
            if author and author in author_text:
                score += 90
            if categories and any(item in category_text for item in categories):
                score += 70
            if tags and any(any(tag in tag_text for tag_text in tag_texts) for tag in tags):
                score += 70
            if not any([title, author, categories, tags]):
                for token in query_tokens:
                    if token in title_text:
                        score += 30
                    if token in author_text:
                        score += 25
                    if token in category_text:
                        score += 20
                    if any(token in tag_text for tag_text in tag_texts):
                        score += 20
                    if token in description_text:
                        score += 10

            if score > 0:
                scored.append((score, len(description_text), _safe_text(book.get('created_at')), book))

        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [item[3] for item in scored[:DEFAULT_QUERY_LIMIT]]

    def _recommend_from_matches(self, matched_books: List[Dict[str, Any]], user_books: List[Any], intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not matched_books:
            return self._recommend_books(intent, '', user_books)

        count = max(1, min(int(intent.get('recommendation_count', DEFAULT_RECOMMEND_COUNT)), 2))
        matched_ids = {book['id'] for book in matched_books}
        primary = matched_books[:count]
        if len(primary) >= count:
            return primary

        author_set = {_safe_text(book.get('author')).lower() for book in matched_books if _safe_text(book.get('author'))}
        category_set = {_safe_text(book.get('category')).lower() for book in matched_books if _safe_text(book.get('category'))}
        tag_set = {_safe_text(tag).lower() for book in matched_books for tag in book.get('tags', []) if _safe_text(tag)}

        supplements = []
        for raw_book in user_books:
            book = _book_to_dict(raw_book)
            if book['id'] in matched_ids or any(book['id'] == item['id'] for item in supplements):
                continue
            author_text = _safe_text(book.get('author')).lower()
            category_text = _safe_text(book.get('category')).lower()
            tag_texts = [_safe_text(tag).lower() for tag in book.get('tags', [])]
            if author_set and author_text in author_set:
                supplements.append(book)
            elif category_set and category_text in category_set:
                supplements.append(book)
            elif tag_set and any(tag in tag_texts for tag in tag_set):
                supplements.append(book)
            if len(primary) + len(supplements) >= count:
                break

        return (primary + supplements)[:count]

    def _recommend_books(self, intent: Dict[str, Any], message: str, user_books: List[Any]) -> List[Dict[str, Any]]:
        count = max(1, min(int(intent.get('recommendation_count', DEFAULT_RECOMMEND_COUNT)), 2))
        search = intent.get('search', {})
        categories = [_safe_text(item).lower() for item in search.get('categories', []) if _safe_text(item)]
        tags = [_safe_text(item).lower() for item in search.get('tags', []) if _safe_text(item)]
        mood_keywords = [_safe_text(item).lower() for item in intent.get('mood_keywords', []) if _safe_text(item)]
        query_tokens = categories + tags + mood_keywords + _tokenize(message)

        if self._is_default_recommend_reply(message) and not query_tokens:
            recent = sorted(
                (_book_to_dict(book) for book in user_books),
                key=lambda item: _safe_text(item.get('created_at')),
                reverse=True,
            )
            return recent[:count]

        scored = []
        for raw_book in user_books:
            book = _book_to_dict(raw_book)
            category_text = _safe_text(book.get('category')).lower()
            tag_texts = [_safe_text(tag).lower() for tag in book.get('tags', [])]
            description_text = _safe_text(book.get('description')).lower()
            title_text = _safe_text(book.get('title')).lower()
            score = 0

            for token in query_tokens:
                if token in category_text:
                    score += 40
                if any(token in tag for tag in tag_texts):
                    score += 35
                if token in description_text:
                    score += 20
                if token in title_text:
                    score += 15

            if score > 0:
                scored.append((score, len(description_text), _safe_text(book.get('created_at')), book))

        if not scored:
            recent = sorted(
                (_book_to_dict(book) for book in user_books),
                key=lambda item: (_safe_text(item.get('created_at')), len(_safe_text(item.get('description')))),
                reverse=True,
            )
            return recent[:count]

        scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        return [item[3] for item in scored[:count]]

    def _compose_or_fallback(
        self,
        mode: str,
        basis: str,
        matched_books: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        user_message: str,
    ) -> str:
        payload = {
            'mode': mode,
            'basis': basis,
            'user_message': user_message,
            'matched_books': matched_books,
            'recommendations': recommendations,
        }
        try:
            answer = self.ai_adapter.compose_answer(payload)
            if answer:
                return answer
        except Exception as exc:
            logger.warning('AI 组织回答失败，回退模板输出: %s', exc)

        return self._fallback_answer(mode, basis, matched_books, recommendations)

    def _get_recent_books(self, user_books: List[Any], limit: int) -> List[Dict[str, Any]]:
        recent = sorted(
            (_book_to_dict(book) for book in user_books),
            key=lambda item: _safe_text(item.get('created_at')),
            reverse=True,
        )
        return recent[:limit]

    def _build_recent_books_answer(self, books: List[Dict[str, Any]]) -> str:
        if not books:
            return '最近入库查询完成，但您的书库里暂时没有可展示的图书。'
        lines = ['这是您最近入库的书：']
        for index, book in enumerate(books, 1):
            lines.append(f'{index}. 《{book["title"]}》')
            if book.get('author'):
                lines.append(f'   作者：{book["author"]}')
            if book.get('location'):
                lines.append(f'   所在位置：{book["location"]}')
        return '\n'.join(lines)

    def _fallback_answer(self, mode: str, basis: str, matched_books: List[Dict[str, Any]], recommendations: List[Dict[str, Any]]) -> str:
        basis_map = {
            'author': '按作者命中',
            'title': '按书名命中',
            'category_tag': '按分类/标签命中',
            'mixed': '按书名、作者和分类标签综合命中',
            'mood': '按当前阅读偏好推荐',
        }
        intro = basis_map.get(basis, '按书库信息命中')
        lines = [intro]

        if matched_books:
            lines.append('查到这些书：')
            for index, book in enumerate(matched_books, 1):
                lines.append(f'{index}. 《{book["title"]}》')
                if book.get('author'):
                    lines.append(f'   作者：{book["author"]}')
                if book.get('location'):
                    lines.append(f'   所在位置：{book["location"]}')
                if book.get('location_code'):
                    lines.append(f'   位置码：{book["location_code"]}')

        if recommendations:
            if mode == 'query_and_recommend':
                lines.append('另外可先看：')
            elif mode == 'recommend':
                lines.append('可以先看：')
            for index, book in enumerate(recommendations, 1):
                lines.append(f'{index}. 《{book["title"]}》')
                if book.get('author'):
                    lines.append(f'   作者：{book["author"]}')
                if book.get('category'):
                    lines.append(f'   分类：{book["category"]}')
        if not matched_books and not recommendations:
            lines.append('这次没有在您的书库里找到合适结果。')
        return '\n'.join(lines)

    def _build_clarification_prompt(self) -> str:
        return '我可以先按你的阅读状态来帮你挑书。你最近更想看轻松一点的，还是更想看能让人静下来思考的？'

    def _is_recent_books_query(self, message: str) -> bool:
        return any(pattern in message for pattern in RECENT_QUERY_PATTERNS)

    def _should_force_clarification(self, message: str, intent: Dict[str, Any]) -> bool:
        search = intent.get('search', {}) or {}
        has_search = any([
            _safe_text(search.get('author')),
            _safe_text(search.get('title')),
            search.get('categories'),
            search.get('tags'),
        ])
        if has_search or self._is_default_recommend_reply(message):
            return False
        return any(pattern in message for pattern in GENERIC_RECOMMEND_PATTERNS)

    def _is_default_recommend_reply(self, message: str) -> bool:
        return any(pattern in message for pattern in ('都行', '随便', '你看着办'))

    def _merge_books(self, matched_books: List[Dict[str, Any]], recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged = []
        seen = set()
        for book in matched_books + recommendations:
            book_id = book.get('id')
            if book_id in seen:
                continue
            seen.add(book_id)
            merged.append(book)
        return merged


_assistant_service = BookAssistantService()


def get_assistant_service() -> BookAssistantService:
    return _assistant_service

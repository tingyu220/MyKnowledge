import unittest
from dataclasses import dataclass, field

from utils.assistant_service import BookAssistantService


@dataclass
class StubBook:
    id: int
    title: str
    author: str = ''
    category: str = ''
    description: str = ''
    tags: list = field(default_factory=list)
    created_at: str = ''
    cover_url: str = ''
    location: str = ''
    location_code: str = ''

    def to_dict(self):
        return {
            'id': self.id,
            'isbn': '',
            'title': self.title,
            'author': self.author,
            'publisher': '',
            'publish_date': '',
            'description': self.description,
            'cover_url': self.cover_url,
            'category': self.category,
            'created_at': self.created_at,
            'updated_at': self.created_at,
            'tags': list(self.tags),
            'location': self.location,
            'location_code': self.location_code,
        }


class FakeAIAdapter:
    def __init__(self, intent):
        self.intent = intent
        self.compose_payloads = []

    def interpret_intent(self, message, recent_messages=None, awaiting_mood=False):
        return self.intent

    def compose_answer(self, payload):
        self.compose_payloads.append(payload)
        return ''


class BookAssistantServiceTests(unittest.TestCase):
    def setUp(self):
        self.books = [
            StubBook(
                id=1,
                title='活着',
                author='余华',
                category='文学',
                description='一部关于命运与生命韧性的小说，简介较完整。',
                tags=['小说', '经典'],
                created_at='2026-04-20T10:00:00',
                location='书房 → 文学书架 → 第1层 → 左侧第1本',
                location_code='A001-01-1',
            ),
            StubBook(
                id=2,
                title='许三观卖血记',
                author='余华',
                category='文学',
                description='围绕普通人的生活展开，风格鲜明。',
                tags=['小说'],
                created_at='2026-04-19T10:00:00',
                location='书房 → 文学书架 → 第1层 → 右侧第1本',
                location_code='A001-01-2',
            ),
            StubBook(
                id=3,
                title='心理学与生活',
                author='理查德',
                category='心理学',
                description='系统介绍心理学基础概念与日常应用。',
                tags=['心理学', '入门'],
                created_at='2026-04-18T10:00:00',
                location='书房 → 文学书架 → 第2层 → 左侧第1本',
                location_code='A001-02-1',
            ),
        ]

    def test_query_mode_returns_only_matched_books_and_locations(self):
        adapter = FakeAIAdapter({
            'mode': 'query',
            'needs_clarification': False,
            'search': {'author': '余华', 'title': '', 'categories': [], 'tags': []},
            'mood_keywords': [],
            'recommendation_count': 0,
            'basis': 'author',
        })
        service = BookAssistantService(ai_adapter=adapter)

        result = service.process_message('余华有什么书', self.books)

        self.assertFalse(result['needs_clarification'])
        self.assertEqual(result['mode'], 'query')
        self.assertEqual(len(result['books']), 2)
        self.assertEqual(len(result['recommendations']), 0)
        self.assertIn('按作者命中', result['answer'])
        self.assertIn('所在位置：书房 → 文学书架 → 第1层 → 左侧第1本', result['answer'])

    def test_library_entity_detection_recovers_author_only_query(self):
        adapter = FakeAIAdapter({
            'mode': 'recommend',
            'needs_clarification': True,
            'search': {'author': '', 'title': '', 'categories': [], 'tags': []},
            'mood_keywords': [],
            'recommendation_count': 2,
            'basis': 'mood',
        })
        service = BookAssistantService(ai_adapter=adapter)

        result = service.process_message('余华的书籍', self.books)

        self.assertEqual(result['mode'], 'query')
        self.assertEqual(len(result['books']), 2)
        self.assertEqual(result['intent_basis'], 'author')

    def test_query_and_recommend_prefers_same_author(self):
        adapter = FakeAIAdapter({
            'mode': 'query_and_recommend',
            'needs_clarification': False,
            'search': {'author': '余华', 'title': '', 'categories': [], 'tags': []},
            'mood_keywords': [],
            'recommendation_count': 2,
            'basis': 'author',
        })
        service = BookAssistantService(ai_adapter=adapter)

        result = service.process_message('余华有什么书，顺便推荐一本到两本', self.books)

        self.assertEqual(result['mode'], 'query_and_recommend')
        self.assertEqual(len(result['books']), 2)
        self.assertGreaterEqual(len(result['recommendations']), 1)
        self.assertEqual(result['recommendations'][0]['author'], '余华')

    def test_ambiguous_recommend_asks_for_mood(self):
        adapter = FakeAIAdapter({
            'mode': 'recommend',
            'needs_clarification': True,
            'search': {'author': '', 'title': '', 'categories': [], 'tags': []},
            'mood_keywords': [],
            'recommendation_count': 2,
            'basis': 'mood',
        })
        service = BookAssistantService(ai_adapter=adapter)

        result = service.process_message('最近有什么好书', self.books)

        self.assertTrue(result['needs_clarification'])
        self.assertIn('最近更想看', result['answer'])
        self.assertEqual(result['books'], [])

    def test_short_vague_recommendation_sentence_also_asks_for_mood(self):
        adapter = FakeAIAdapter({
            'mode': 'query',
            'needs_clarification': False,
            'search': {'author': '', 'title': '', 'categories': [], 'tags': []},
            'mood_keywords': [],
            'recommendation_count': 0,
            'basis': 'mixed',
        })
        service = BookAssistantService(ai_adapter=adapter)

        result = service.process_message('我想看点书', self.books)

        self.assertTrue(result['needs_clarification'])
        self.assertEqual(result['mode'], 'recommend')
        self.assertIn('最近更想看', result['answer'])

    def test_recommend_mode_uses_mood_keywords_for_bookshelf_recommendation(self):
        adapter = FakeAIAdapter({
            'mode': 'recommend',
            'needs_clarification': False,
            'search': {'author': '', 'title': '', 'categories': ['心理学'], 'tags': ['入门']},
            'mood_keywords': ['平静', '治愈'],
            'recommendation_count': 2,
            'basis': 'mood',
        })
        service = BookAssistantService(ai_adapter=adapter)

        result = service.process_message('想看点能让自己平静下来的书', self.books, awaiting_mood=True)

        self.assertEqual(result['mode'], 'recommend')
        self.assertFalse(result['needs_clarification'])
        self.assertGreaterEqual(len(result['recommendations']), 1)
        self.assertEqual(result['recommendations'][0]['title'], '心理学与生活')

    def test_recent_books_query_returns_recent_library_books(self):
        adapter = FakeAIAdapter({
            'mode': 'query',
            'needs_clarification': False,
            'search': {'author': '', 'title': '', 'categories': [], 'tags': []},
            'mood_keywords': [],
            'recommendation_count': 0,
            'basis': 'mixed',
        })
        service = BookAssistantService(ai_adapter=adapter)

        result = service.process_message('最近有什么书籍', self.books)

        self.assertEqual(result['mode'], 'recent')
        self.assertFalse(result['needs_clarification'])
        self.assertGreaterEqual(len(result['books']), 3)
        self.assertIn('最近入库', result['answer'])


if __name__ == '__main__':
    unittest.main()

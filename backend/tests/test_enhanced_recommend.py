import unittest
from dataclasses import dataclass, field

from utils.enhanced_recommend import EnhancedRecommendService, WEAK_FALLBACK_MESSAGE


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


class EnhancedRecommendServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = EnhancedRecommendService()
        self.service.api_cache.invalidate()

    def test_prefers_category_and_tags_before_weaker_text_matches(self):
        books = [
            StubBook(
                id=1,
                title='心理学与生活',
                author='理查德',
                category='心理学',
                tags=['入门', '心理成长'],
                description='一本系统介绍心理学基础概念的经典入门书，内容完整，覆盖认知、情绪与行为。',
                created_at='2026-04-20T10:00:00',
            ),
            StubBook(
                id=2,
                title='读懂关系',
                author='作者甲',
                category='文学',
                tags=['随笔'],
                description='简介里提到一些心理现象，但整体并不是心理学分类图书。',
                created_at='2026-04-21T10:00:00',
            ),
        ]

        result = self.service.recommend_response('我想读心理学相关的书', books, limit=2)

        self.assertEqual(result['match_level'], 'strong')
        self.assertEqual(result['recommendations'][0]['book']['id'], 1)
        self.assertIn('分类和标签与您的需求高度吻合', result['recommendations'][0]['reason'])

    def test_prefers_more_complete_description_within_strong_matches(self):
        books = [
            StubBook(
                id=1,
                title='Python 学习手册',
                author='作者甲',
                category='计算机',
                tags=['编程', '入门'],
                description='简短简介。',
                created_at='2026-04-20T10:00:00',
            ),
            StubBook(
                id=2,
                title='Python 核心实践',
                author='作者乙',
                category='计算机',
                tags=['编程', '入门'],
                description='这是一本面向初学者的 Python 入门与实战书籍，完整讲解语法、项目结构、调试技巧与常见开发流程，内容明显更完整。',
                created_at='2026-04-19T10:00:00',
            ),
        ]

        result = self.service.recommend_response('推荐一些编程入门书籍', books, limit=2)

        self.assertEqual(result['recommendations'][0]['book']['id'], 2)
        self.assertIn('简介信息较完整', result['recommendations'][0]['reason'])

    def test_returns_weaker_matches_when_no_strong_match_exists(self):
        books = [
            StubBook(
                id=1,
                title='设计模式实践',
                author='作者甲',
                category='计算机',
                tags=['架构'],
                description='介绍常见设计模式和工程实践。',
                created_at='2026-04-20T10:00:00',
            ),
            StubBook(
                id=2,
                title='数据库原理',
                author='作者乙',
                category='计算机',
                tags=['数据库'],
                description='数据库基础理论与 SQL 应用。',
                created_at='2026-04-19T10:00:00',
            ),
        ]

        result = self.service.recommend_response('我想看悬疑推理小说', books, limit=2)

        self.assertEqual(result['match_level'], 'weak')
        self.assertTrue(result['answer'].startswith(WEAK_FALLBACK_MESSAGE))
        self.assertEqual(len(result['recommendations']), 2)

    def test_answer_includes_book_location_when_available(self):
        books = [
            StubBook(
                id=1,
                title='安妮日记',
                author='安妮·弗朗克',
                category='文学',
                tags=['日记', '文学'],
                description='关于战争中的成长与记录。',
                created_at='2026-04-20T10:00:00',
                location='书房 → 文学书架 → 第1层 → 左侧第1本',
                location_code='A001-01-1',
            ),
        ]

        result = self.service.answer_question('我想看文学类的书', books)

        self.assertIn('所在位置：书房 → 文学书架 → 第1层 → 左侧第1本', result['answer'])
        self.assertIn('位置码：A001-01-1', result['answer'])


if __name__ == '__main__':
    unittest.main()

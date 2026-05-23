# -*- coding: utf-8 -*-
"""
AI 服务模块
提供图书分析、推荐、问答功能
（已改为纯本地算法，不依赖外部 API）
"""
import json
import logging
import re
import random
from collections import Counter
from typing import List, Dict, Any

try:
    from config import Config
except Exception:
    Config = None

logger = logging.getLogger(__name__)

# 分类关键词映射（用于本地分类分析）
CATEGORY_KEYWORDS = {
    '计算机': ['编程', '算法', '软件', '系统', '网络', '数据库', 'python', 'java', 'javascript', 'c++', '代码', '程序', '开发', '运维', '架构', '计算机', 'it', '网站', 'web', '前端', '后端', '全栈'],
    '文学': ['小说', '散文', '诗歌', '文学', '故事', '名著', '作家', '文集', '诺贝尔文学', '鲁迅', '莫言', '古典文学', '现代文学'],
    '历史': ['历史', '古代', '朝代', '战争', '人物', '近代', '古代史', '文化', '文明', '史书', '史料', '传记', '回忆录'],
    '心理学': ['心理', '情绪', '认知', '行为', '人格', '思维', '心理学', '心灵', '成长', '情商', '情商', '心理分析', '人际交往', '沟通'],
    '经济': ['经济', '金融', '投资', '商业', '市场', '管理', '创业', '财务', '会计', '宏观', '微观', '经济学', '理财', '股票'],
    '科学': ['科学', '物理', '化学', '生物', '数学', '天文', '地理', '自然', '科普', '科学家', '定理', '定律', '实验'],
    '哲学': ['哲学', '思想', '理论', '逻辑', '伦理', '道德', '人生', '思考', '哲学家', '哲学史', '存在主义', '唯心主义'],
    '艺术': ['艺术', '绘画', '音乐', '设计', '美学', '电影', '摄影', '建筑', '美术', '艺术家', '艺术史', '画廊', '美术馆'],
}

# 标签关键词映射
TAG_KEYWORDS = {
    '入门': ['入门', '基础', '初学者', '入门教程', '新手', '启蒙', '初级', '从零开始', '零基础'],
    '进阶': ['进阶', '高级', '深入', '精通', '专家', '提升', '中级', '进阶教程', '提高'],
    '经典': ['经典', '名���', '必读', '经典著作', '传世', '经典作品', '不朽', '代表作'],
    '实用': ['实用', '实战', '应用', '实践', '操作', '实例', '实操', '技巧', '工具'],
    '理论': ['理论', '原理', '概念', '思想', '体系', '基础理论', '理论性', '学术'],
    '畅销': ['畅销', '热门', '流行', '热销', '推荐', '畅销书', '热门书', '好评'],
}


def _ai_enabled() -> bool:
    """检查AI服务是否可用（已禁用）"""
    return False


def analyze_book(title: str, description: str) -> dict:
    """
    分析图书并生成分类和标签（基于规则）
    """
    return _rule_based_analyze(title, description)


def _rule_based_analyze(title: str, description: str) -> dict:
    """基于关键词规则的分析"""
    if not title and not description:
        return {'category': '其他', 'tags': []}

    text = f"{title} {description}".lower()

    # 分类匹配
    category = '其他'
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            category = cat
            break

    # 标签匹配
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            tags.append(tag)

    # 如果没匹配到标签，使用分类作为默认标签
    if not tags:
        tags.append(category)

    return {'category': category, 'tags': tags[:5]}


def recommend_books(query: str, user_books: List[Any], limit: int = 5) -> List[Dict[str, Any]]:
    """
    基于内容的本地图书推荐
    根据查询与书籍的文本相似度进行推荐

    参数:
        query: 用户查询（如"我想读心理学相关的书"）
        user_books: 用户的图书列表（SQLAlchemy Book对象）
        limit: 返回推荐数量

    返回:
        List[Dict]: 推荐列表，每项包含 book、score、reason
    """
    if not user_books or not query:
        return []

    query_lower = query.lower().strip()
    recommendations = []

    for book in user_books:
        score = 0
        reason_parts = []

        # 标题匹配（权重最高）
        if book.title and query_lower in (book.title or '').lower():
            score += 10
            reason_parts.append('标题匹配')

        # 作者匹配
        if book.author and query_lower in (book.author or '').lower():
            score += 5
            reason_parts.append('作者相关')

        # 分类匹配
        if book.category and query_lower in (book.category or '').lower():
            score += 8
            reason_parts.append('分类相关')

        # 简介内容匹配
        if book.description and query_lower in (book.description or '').lower():
            score += 3
            reason_parts.append('内容相关')

        # 标签匹配
        if hasattr(book, 'tags') and book.tags:
            for tag in book.tags:
                if query_lower in str(tag).lower():
                    score += 4
                    reason_parts.append('标签相关')
                    break

        if score > 0:
            recommendations.append({
                'book': book.to_dict(),
                'score': score,
                'reason': '、'.join(reason_parts) if reason_parts else '相关推荐',
            })

    # 按分数排序
    recommendations.sort(key=lambda x: x['score'], reverse=True)

    # 如果没有找到匹配，返回一些随机推荐（基于已有书籍）
    if not recommendations and user_books:
        shuffled = random.sample(user_books, min(limit, len(user_books)))
        for book in shuffled:
            recommendations.append({
                'book': book.to_dict(),
                'score': 1,
                'reason': '为您推荐',
            })

    return recommendations[:limit]


def answer_question(question: str, user_books: List[Any]) -> Dict[str, Any]:
    """
    基于规则的问答功能
    分析用户问题并返回回答和推荐

    参数:
        question: 用户问题
        user_books: 用户的图书列表

    返回:
        Dict: 包含 answer 和 recommendations
    """
    if not user_books:
        return {
            'answer': '您还没有添加任何图书。请先添加一些图书，我才能为您提供推荐。',
            'recommendations': [],
        }

    question_lower = question.lower()

    # 提取关键词
    keywords = []
    for kw in ['心理学', '编程', '历史', '文学', '经济', '科学', '哲学', '艺术', '计算机', '小说', '数学', '物理', '化学', '生物', '管理', '投资', '金融']:
        if kw in question_lower:
            keywords.append(kw)

    # 生成推荐
    if keywords:
        query = ' '.join(keywords)
        recommendations = recommend_books(query, user_books, limit=3)
    else:
        # 如果没有明确关键词，随机推荐几本
        recommendations = recommend_books('', user_books, limit=3)

    if not recommendations:
        return {
            'answer': '抱歉，根据您的问题，我没有找到相关的图书推荐。您可以尝试添加更多图书，或者使用更具体的关键词。',
            'recommendations': [],
        }

    # 生成回答
    answer_lines = []
    if keywords:
        answer_lines.append(f'根据您关于「{"、".join(keywords)}」的问题，我为您推荐以下图书：\n\n')
    else:
        answer_lines.append(f'根据您的问题「{question}」，我为您推荐以下图书：\n\n')

    for i, rec in enumerate(recommendations, 1):
        book = rec['book']
        answer_lines.append(f"{i}. 《{book['title']}》")
        if book.get('author'):
            answer_lines.append(f"   作者：{book['author']}")
        if book.get('category'):
            answer_lines.append(f"   分类：{book['category']}")
        answer_lines.append(f"   推荐理由：{rec['reason']}\n")

    answer_lines.append('\n您可以点击"查看详情"了解更多信息，或继续提问。')

    return {
        'answer': '\n'.join(answer_lines),
        'recommendations': recommendations,
    }

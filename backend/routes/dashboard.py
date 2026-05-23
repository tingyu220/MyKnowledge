# -*- coding: utf-8 -*-
"""
仪表盘汇总接口
"""
from flask import Blueprint, jsonify, session

from models import db, Book

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/summary', methods=['GET'])
def summary():
    """
    返回仪表盘数据：
    - categories: 分类占比（按 book.category）
    - total_books: 总藏书数
    """
    user_id = session.get('user_id')

    # 分类占比（按书籍数量）
    rows = (
        db.session.query(Book.category, db.func.count(Book.id))
        .filter(Book.user_id == user_id)
        .group_by(Book.category)
        .all()
    )
    total_books = sum(int(r[1]) for r in rows) or 0
    categories = []
    for cat, cnt in rows:
        name = (cat or '').strip() or '未分类'
        categories.append({'category': name, 'count': int(cnt)})
    categories.sort(key=lambda x: x['count'], reverse=True)
    # Top6 + 其他
    if len(categories) > 6:
        top = categories[:6]
        other_count = sum(c['count'] for c in categories[6:])
        top.append({'category': '其他', 'count': other_count})
        categories = top
    # percent
    for c in categories:
        c['percent'] = round((c['count'] / total_books * 100) if total_books else 0, 2)

    return jsonify({
        'categories': categories,
        'total_books': total_books,
    }), 200


@dashboard_bp.route('/recommendations', methods=['GET'])
def get_recommendations():
    """
    返回经典书单推荐
    基于用户已添加的图书，按分类推荐经典的书籍
    """
    user_id = session.get('user_id')

    # 获取用户的所有图书
    user_books = Book.query.filter_by(user_id=user_id).all()

    # 经典书单模板（按分类）
    classic_books_by_category = {
        '文学': [
            {'title': '《活着》', 'note': '余华｜文学经典，适合重读'},
            {'title': '《百年孤独》', 'note': '马尔克斯｜魔幻现实主义代表作'},
            {'title': '《红楼梦》', 'note': '曹雪芹｜中国古典文学巅峰'},
            {'title': '《1984》', 'note': '乔治·奥威尔｜反乌托邦经典'},
        ],
        '计算机': [
            {'title': '《深入理解计算机系统》', 'note': 'CS 基础经典（可按章节慢读）'},
            {'title': '《算法导论》', 'note': '算法经典教材'},
            {'title': '《代码大全》', 'note': '软件构建实用指南'},
            {'title': '《设计模式》', 'note': 'GoF 经典设计模式'},
        ],
        '历史': [
            {'title': '《人类简史》', 'note': '尤瓦尔·赫拉利｜宏观视角的通识读物'},
            {'title': '《万历十五年》', 'note': '黄仁宇｜历史微观叙事'},
            {'title': '《史记》', 'note': '司马迁｜史家之绝唱'},
        ],
        '心理学': [
            {'title': '《思考，快与慢》', 'note': '丹尼尔·卡尼曼｜行为经济学经典'},
            {'title': '《影响力》', 'note': '罗伯特·西奥迪尼｜心理学应用'},
            {'title': '《自卑与超越》', 'note': '阿德勒｜个体心理学'},
        ],
        '经济': [
            {'title': '《经济学原理》', 'note': '曼昆｜经济学入门经典'},
            {'title': '《国富论》', 'note': '亚当·斯密｜现代经济学奠基之作'},
            {'title': '《原则》', 'note': '瑞·达利欧｜方法论与复盘'},
        ],
        '科学': [
            {'title': '《时间简史》', 'note': '霍金｜宇宙科学科普'},
            {'title': '《物种起源》', 'note': '达尔文｜进化论经典'},
            {'title': '《上帝掷骰子吗》', 'note': '曹天元｜量子物理史话'},
        ],
        '哲学': [
            {'title': '《苏菲的世界》', 'note': '乔斯坦·贾德｜哲学入门小说'},
            {'title': '《西方哲学史》', 'note': '罗素｜哲学史经典'},
            {'title': '《中国哲学简史》', 'note': '冯友兰｜中国哲学概述'},
        ],
        '艺术': [
            {'title': '《艺术的故事》', 'note': '贡布里希｜艺术史经典'},
            {'title': '《美学散步》', 'note': '宗白华｜中国美学随笔'},
            {'title': '《摄影构图学》', 'note': '摄影艺术基础'},
        ],
    }

    # 分析用户已有的分类
    user_categories = set()
    for book in user_books:
        if book.category:
            user_categories.add(book.category)

    # 智能推荐：优先推荐用户已有分类的经典书单
    recommended_books = []

    # 第一优先级：用户已有分类的经典书籍
    for cat in user_categories:
        if cat in classic_books_by_category:
            for book_info in classic_books_by_category[cat]:
                recommended_books.append(book_info)

    # 第二优先级：补充一些通用经典（如果推荐不足）
    if len(recommended_books) < 5:
        fallback_books = [
            {'title': '《活着》', 'note': '余华｜文学经典，适合重读'},
            {'title': '《人类简史》', 'note': '尤瓦尔·赫拉利｜宏观视角的通识读物'},
            {'title': '《原则》', 'note': '瑞·达利欧｜方法论与复盘'},
            {'title': '《思考，快与慢》', 'note': '丹尼尔·卡尼曼｜行为经济学经典'},
            {'title': '《艺术的故事》', 'note': '贡布里希｜艺术史经典'},
        ]
        for book_info in fallback_books:
            if book_info not in recommended_books:
                recommended_books.append(book_info)
            if len(recommended_books) >= 5:
                break

    # 去重并限制返回数量
    seen_titles = set()
    unique_recommendations = []
    for book_info in recommended_books:
        if book_info['title'] not in seen_titles:
            seen_titles.add(book_info['title'])
            unique_recommendations.append(book_info)
        if len(unique_recommendations) >= 6:
            break

    return jsonify({
        'recommendations': unique_recommendations
    }), 200


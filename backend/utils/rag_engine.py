# -*- coding: utf-8 -*-
"""
RAG（检索增强生成）引擎模块

功能：
1. 文本向量化和相似度计算
2. 基于TF-IDF的内容检索
3. 智能问答上下文构建
4. 生成推荐理由

优化改进：
- 使用 jieba 分词（按词语而非单字）
- 扩展停用词库
- 统一查询和文档分词逻辑
- 字段加权相似度计算
- 多级匹配策略（精确→模糊→语义）
"""
import re
import math
import logging
from collections import Counter, defaultdict
from typing import List, Dict, Any, Tuple, Optional
from jieba import cut

logger = logging.getLogger(__name__)

# 扩展的中文停用词表
STOPWORDS = {
            # 常见虚词
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很',
            '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '之', '与',
            '及', '为', '以', '等', '而', '于', '或', '但', '因', '所', '如', '若', '则', '至', '乃', '且',
            # 代词
            '我们', '你们', '他们', '它们', '她们', '其', '彼', '此', '某', '各', '每', '谁', '何', '几',
            # 介词连词
            '在', '从', '到', '向', '对', '为', '以', '由', '因', '所以', '但是', '虽然', '如果', '那么',
            # 助词语气词
            '了', '着', '过', '的', '得', '地', '吗', '呢', '吧', '啊', '哦', '嗯', '唉', '呀',
            # 数量词
            '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '百', '千', '万', '亿',
            '个', '只', '条', '张', '本', '台', '辆', '次', '回', '趟', '遍', '套', '束', '件', '场',
            # 时间词
            '年', '月', '日', '时', '分', '秒', '今天', '昨天', '明天', '现在', '以前', '以后',
            # 泛指
            '东西', '事情', '问题', '方面', '部分', '情况', '人', '人们',
            # 英文停用词
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being',
            # 其他常见无意义词
            '暂无', '暂无简介', '未知', '未分类', '暂无数据'
        }

# 字段权重配置（用于索引构建时的重复次数）
FIELD_REPEAT_COUNT = {
    'title': 5,       # 标题：重复5次（最高权重）
    'author': 4,      # 作者：重复4次
    'category': 4,    # 分类：重复4次（提升到与作者同级）
    'tags': 3,        # 标签：重复3次
    'description': 1  # 简介：1次
}

# 字段权重配置（用于相似度计算）
FIELD_WEIGHTS = {
    'title': 3.0,      # 标题权重最高
    'author': 2.5,     # 作者次之
    'category': 2.0,   # 分类
    'tags': 1.8,       # 标签
    'description': 1.0 # 简介权重较低
}


class TFIDFVectorizer:
    """TF-IDF向量化器（使用 jieba 分词）"""

    def __init__(self):
        self.vocabulary_ = {}
        self.idf_ = {}
        self._stopwords = STOPWORDS

    def _tokenize(self, text: str) -> List[str]:
        """
        分词（使用 jieba）

        步骤：
        1. 清理文本（去除特殊字符）
        2. jieba 分词（精确模式）
        3. 过滤停用词和短词
        4. 返回有效词语列表
        """
        if not text:
            return []

        # 去除特殊字符，保留中文、英文、数字
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', str(text))
        text = text.strip()

        if not text:
            return []

        # 使用 jieba 分词（精确模式）
        tokens = []
        try:
            # cut 返回生成器，转换为列表
            raw_tokens = list(cut(text, cut_all=False))
        except:
            # 降级：按空格分词
            raw_tokens = text.split()

        # 过滤：长度>=2、非停用词、非纯数字/英文��除非长度较长）
        for token in raw_tokens:
            token = token.strip()
            if len(token) < 2:
                continue
            if token.lower() in self._stopwords:
                continue
            if token.isdigit() and len(token) < 4:
                # 短数字过滤（如"2025"保留，"01"过滤）
                continue
            if re.match(r'^[a-zA-Z]{1,2}$', token):
                # 过滤短英文单词
                continue
            tokens.append(token)

        return tokens

    def fit_transform(self, documents: List[str]) -> List[List[float]]:
        """
        拟合并转换文档为TF-IDF向量

        参数:
            documents: 文档列表

        返回:
            TF-IDF向量列表
        """
        if not documents:
            return []

        # 分词
        tokenized_docs = [self._tokenize(doc) for doc in documents]

        # 构建词汇表
        vocab = set()
        for tokens in tokenized_docs:
            vocab.update(tokens)
        self.vocabulary_ = {word: i for i, word in enumerate(sorted(vocab))}
        logger.info(f"词汇表大小: {len(self.vocabulary_)}")

        # 计算TF（词频）
        tf_list = []
        for tokens in tokenized_docs:
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1
            tf_list.append({word: count / total for word, count in tf.items()})

        # 计算IDF（逆文档频率）
        N = len(documents)
        df = defaultdict(int)
        for tokens in tokenized_docs:
            for word in set(tokens):
                df[word] += 1

        self.idf_ = {}
        for word in self.vocabulary_:
            df_word = df.get(word, 0)
            # 平滑IDF：+1避免除零，+N避免log(0)
            self.idf_[word] = math.log((N + 1) / (df_word + 1)) + 1

        # 计算TF-IDF向量
        vectors = []
        for tf in tf_list:
            vector = [0.0] * len(self.vocabulary_)
            for word, tf_val in tf.items():
                if word in self.vocabulary_:
                    idx = self.vocabulary_[word]
                    vector[idx] = tf_val * self.idf_.get(word, 1.0)
            vectors.append(vector)

        return vectors

    def transform(self, documents: List[str]) -> List[List[float]]:
        """转换新文档为TF-IDF向量（使用已拟合的词汇表）"""
        if not documents:
            return []

        tokenized_docs = [self._tokenize(doc) for doc in documents]
        tf_list = []
        for tokens in tokenized_docs:
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1
            tf_list.append({word: count / total for word, count in tf.items()})

        vectors = []
        for tf in tf_list:
            vector = [0.0] * len(self.vocabulary_)
            for word, tf_val in tf.items():
                if word in self.vocabulary_:
                    idx = self.vocabulary_[word]
                    vector[idx] = tf_val * self.idf_.get(word, 1.0)
            vectors.append(vector)

        return vectors


class RAGEngine:
    """
    RAG检索增强引擎

    功能：
    1. 为用户图书库构建向量索引
    2. 语义检索找到相关内容
    3. 生成检索增强的上下文
    4. 生成推荐理由
    """

    def __init__(self):
        self.vectorizer = TFIDFVectorizer()
        self.book_vectors_ = []
        self.books_ = []
        self.is_indexed = False

    def build_index(self, books: List[Any]) -> None:
        """
        为用户图书库构建检索索引

        参数:
            books: Book对象列表
        """
        if not books:
            self.is_indexed = False
            return

        self.books_ = books

        # 构建文档内容（按字段加权拼接）
        documents = []
        for book in books:
            # 按权重重复字段，使重要字段在TF-IDF中占比更高
            parts = []
            # 标题（最高权重）
            if book.title:
                parts.extend([book.title] * FIELD_REPEAT_COUNT['title'])
            # 作者（次高权重）
            if book.author:
                parts.extend([book.author] * FIELD_REPEAT_COUNT['author'])
            # 分类（高权重）
            if book.category:
                parts.extend([book.category] * FIELD_REPEAT_COUNT['category'])
            # 标签
            if hasattr(book, 'tags'):
                try:
                    from models import BookTag, Tag
                    tag_records = BookTag.query.filter_by(book_id=book.id).join(Tag).all()
                    tag_names = [record.tag.tag_name for record in tag_records if record.tag]
                    parts.extend(tag_names * FIELD_REPEAT_COUNT['tags'])
                except:
                    pass
            # 简介
            if book.description:
                parts.append(book.description)

            documents.append(' '.join(parts))

        # 向量化
        if documents:
            self.book_vectors_ = self.vectorizer.fit_transform(documents)
            self.is_indexed = True
            logger.info(f"RAG索引构建完成，共 {len(books)} 本书，词汇量: {len(self.vectorizer.vocabulary_)}")
        else:
            self.is_indexed = False

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1)) + 1e-8
        norm2 = math.sqrt(sum(b * b for b in vec2)) + 1e-8

        return dot_product / (norm1 * norm2)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        检索相关图书（多级匹配策略）

        策略：
        1. 精确匹配（书名完全包含查询词）
        2. 模糊匹配（作者/分类包含查询词）
        3. 语义匹配（TF-IDF向量相似度）

        参数:
            query: 查询文本
            top_k: 返回结果数量

        返回:
            相关图书列表
        """
        if not self.is_indexed or not query:
            return []

        query_lower = query.lower().strip()
        if not query_lower:
            return []

        # 多级匹配策略
        results = []

        # 第一级：精确匹配书名
        for i, book in enumerate(self.books_):
            if book.title and query_lower in book.title.lower():
                results.append((i, 1.0, '书名匹配'))

        # 第二级：精确匹配作者
        if len(results) < top_k:
            for i, book in enumerate(self.books_):
                if book.author and query_lower in book.author.lower():
                    if i not in [r[0] for r in results]:
                        results.append((i, 0.95, '作者匹配'))

        # 第三级：匹配分类
        if len(results) < top_k:
            for i, book in enumerate(self.books_):
                if book.category and query_lower in book.category.lower():
                    if i not in [r[0] for r in results]:
                        results.append((i, 0.9, '分类匹配'))

        # 第四级：TF-IDF语义相似度
        if len(results) < top_k:
            try:
                query_vector = self.vectorizer.transform([query])
                if query_vector:
                    similarities = []
                    for i, book_vector in enumerate(self.book_vectors_):
                        sim = self.cosine_similarity(query_vector[0], book_vector)
                        if sim > 0.01:  # 阈值过滤低相似度
                            similarities.append((i, sim))

                    similarities.sort(key=lambda x: x[1], reverse=True)
                    for i, sim in similarities[:top_k]:
                        if i not in [r[0] for r in results]:
                            results.append((i, sim, '语义匹配'))
            except Exception as e:
                logger.error(f"TF-IDF检索异常: {e}")

        # 截取top_k
        results = results[:top_k]

        # 构建返回格式
        final_results = []
        for idx, score, match_type in results:
            book = self.books_[idx]
            reason = self._generate_match_reason(book, query, score)
            final_results.append({
                'book': book.to_dict(),
                'score': score,
                'match_reason': reason
            })

        return final_results

    def search_by_author(self, author_query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        按作者名搜索图书

        参数:
            author_query: 作者查询
            top_k: 返回数量

        返回:
            相关图书列表
        """
        if not self.is_indexed:
            return []

        results = []
        author_lower = author_query.lower().strip()

        for i, book in enumerate(self.books_):
            if book.author:
                author_lower_name = book.author.lower()
                if author_lower in author_lower_name:
                    results.append({
                        'book': book.to_dict(),
                        'score': 1.0,
                        'match_reason': f'作者"{book.author}"匹配'
                    })
                    if len(results) >= top_k:
                        break

        return results

    def _generate_match_reason(self, book: Any, query: str, score: float) -> str:
        """生成匹配原因说明"""
        query_lower = query.lower().strip()
        reasons = []

        # 检查字段匹配
        if book.title and query_lower in book.title.lower():
            reasons.append('标题相关')
        if book.author and query_lower in book.author.lower():
            reasons.append('作者相关')
        if book.category and query_lower in book.category.lower():
            reasons.append('分类相关')
        if book.description and query_lower in book.description.lower():
            reasons.append('内容相关')

        # 检查标签
        if hasattr(book, 'tags'):
            try:
                from models import BookTag, Tag
                tag_records = BookTag.query.filter_by(book_id=book.id).join(Tag).all()
                for record in tag_records:
                    if record.tag and query_lower in record.tag.tag_name.lower():
                        reasons.append('标签相关')
                        break
            except:
                pass

        # 生成理由
        if reasons:
            return '、'.join(reasons) + f'（相似度 {score:.0%}）'
        elif score > 0.8:
            return f'高度相关（相似度 {score:.0%}）'
        elif score > 0.5:
            return f'中度相关（相似度 {score:.0%}）'
        else:
            return f'可能相关（相似度 {score:.0%}）'

    def generate_context(self, query: str, top_k: int = 3) -> str:
        """
        生成检索增强的上下文（用于问答）

        参数:
            query: 查询文本
            top_k: 参考图书数量

        返回:
            上下文字符串
        """
        results = self.search(query, top_k)

        if not results:
            return ''

        context_parts = ['根据您的图书库，以下是相关参考信息：\n']

        for i, result in enumerate(results, 1):
            book = result['book']
            context_parts.append(f'{i}. 《{book["title"]}》')
            if book.get('author'):
                context_parts.append(f'   作者���{book["author"]}')
            if book.get('category'):
                context_parts.append(f'   分类：{book["category"]}')
            if book.get('description'):
                desc = book['description'][:200]
                if len(book['description']) > 200:
                    desc += '...'
                context_parts.append(f'   简介：{desc}')
            context_parts.append('')

        return '\n'.join(context_parts)


# 全局RAG引擎实例
_rag_engine = RAGEngine()


def get_rag_engine() -> RAGEngine:
    """获取全局RAG引擎实例"""
    return _rag_engine


def rebuild_rag_index(books: List[Any]) -> None:
    """重建RAG索引"""
    _rag_engine.build_index(books)


def rag_search(query: str, top_k: int = 5, include_authors: bool = True) -> List[Dict[str, Any]]:
    """
    全局搜索接口

    策略：
    1. 先使用RAG引擎的多级匹配检索
    2. 如结果不足且启用作者搜索，补充作者匹配结果
    """
    results = _rag_engine.search(query, top_k)

    # 补充作者搜索结果
    if include_authors and len(results) < top_k:
        author_results = _rag_engine.search_by_author(query, top_k - len(results))
        existing_ids = {r['book']['id'] for r in results}
        for r in author_results:
            if r['book']['id'] not in existing_ids:
                results.append(r)

    return results


def rag_generate_context(query: str, top_k: int = 3) -> str:
    """全局生成上下文接口"""
    return _rag_engine.generate_context(query, top_k)

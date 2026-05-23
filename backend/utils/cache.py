# -*- coding: utf-8 -*-
"""
缓存模块

功能：
1. ISBN查询结果缓存（避免重复爬取）
2. API响应缓存
3. 图书元数据缓存

使用内存缓存，支持TTL过期
"""
import time
import hashlib
import json
import logging
from typing import Any, Optional, Dict
from collections import OrderedDict
from threading import Lock

logger = logging.getLogger(__name__)


class CacheEntry:
    """缓存条目"""

    def __init__(self, key: str, value: Any, ttl: int):
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
        self.hits = 0

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl <= 0:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self) -> None:
        """更新访问时间"""
        self.created_at = time.time()
        self.hits += 1


class LRUCache:
    """LRU缓存实现"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        参数:
            max_size: 最大缓存条目数
            default_ttl: 默认过期时间（秒），0表示永不过期
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = Lock()
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                if entry.is_expired():
                    del self.cache[key]
                    self.stats['misses'] += 1
                    return None
                # 移到末尾（最近使用）
                self.cache.move_to_end(key)
                entry.touch()
                self.stats['hits'] += 1
                return entry.value
            self.stats['misses'] += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        if ttl is None:
            ttl = self.default_ttl

        with self.lock:
            if key in self.cache:
                del self.cache[key]
            elif len(self.cache) >= self.max_size:
                # LRU淘汰：移除最老的条目
                self.cache.popitem(last=False)
                self.stats['evictions'] += 1

            self.cache[key] = CacheEntry(key, value, ttl)

    def delete(self, key: str) -> bool:
        """删除缓存"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        with self.lock:
            total = self.stats['hits'] + self.stats['misses']
            hit_rate = self.stats['hits'] / total if total > 0 else 0
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'evictions': self.stats['evictions'],
                'hit_rate': round(hit_rate * 100, 2)
            }


class ISBNCache:
    """
    ISBN查询结果缓存

    缓存从各API爬取的图书信息，避免重复查询
    """

    def __init__(self, max_size: int = 10000, ttl: int = 86400):
        """
        参数:
            max_size: 最大缓存ISBN数量（默认10000）
            ttl: 过期时间（默认24小时）
        """
        self.cache = LRUCache(max_size=max_size, default_ttl=ttl)

    def _make_key(self, isbn: str, source: str = 'default') -> str:
        """生成缓存键"""
        isbn = isbn.strip().replace('-', '').replace(' ', '')
        return f"isbn:{isbn}:{source}"

    def get(self, isbn: str, source: str = 'default') -> Optional[Dict[str, Any]]:
        """获取缓存的图书信息"""
        key = self._make_key(isbn, source)
        return self.cache.get(key)

    def set(self, isbn: str, data: Dict[str, Any], source: str = 'default') -> None:
        """缓存图书信息"""
        key = self._make_key(isbn, source)
        self.cache.set(key, data)

    def invalidate(self, isbn: str) -> None:
        """使指定ISBN的缓存失效"""
        # 清除该ISBN的所有来源缓存
        for source in ['default', 'douban_api', 'openlibrary', 'googlebooks', 'jd', 'dangdang', 'douban']:
            key = self._make_key(isbn, source)
            self.cache.delete(key)

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self.cache.get_stats()


class APIResponseCache:
    """
    API响应缓存

    缓存推荐、问答等API响应
    """

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        参数:
            max_size: 最大缓存条目数（默认1000）
            ttl: 过期时间（默认1小时）
        """
        self.cache = LRUCache(max_size=max_size, default_ttl=ttl)

    def _make_key(self, prefix: str, **kwargs) -> str:
        """生成缓存键"""
        parts = [prefix]
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            if isinstance(value, (list, dict)):
                value = json.dumps(value, sort_keys=True, ensure_ascii=False)
            parts.append(f"{key}={value}")
        key_str = ':'.join(parts)
        # hash过长则截断
        if len(key_str) > 200:
            key_str = hashlib.md5(key_str.encode()).hexdigest()
        return key_str

    def get(self, prefix: str, **kwargs) -> Optional[Any]:
        """获取缓存的API响应"""
        key = self._make_key(prefix, **kwargs)
        return self.cache.get(key)

    def set(self, prefix: str, data: Any, ttl: Optional[int] = None, **kwargs) -> None:
        """缓存API响应"""
        key = self._make_key(prefix, **kwargs)
        self.cache.set(key, data, ttl)

    def invalidate(self, prefix: str = None) -> None:
        """使缓存失效"""
        if prefix:
            # 清除所有以prefix开头的缓存（简化处理，这里清空所有）
            self.cache.clear()
        else:
            self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self.cache.get_stats()


# 全局缓存实例
isbn_cache = ISBNCache()
api_cache = APIResponseCache()


def get_isbn_cache() -> ISBNCache:
    """获取ISBN缓存实例"""
    return isbn_cache


def get_api_cache() -> APIResponseCache:
    """获取API响应缓存实例"""
    return api_cache


def clear_all_caches() -> Dict[str, Any]:
    """清空所有缓存"""
    isbn_stats = isbn_cache.get_stats()
    api_stats = api_cache.get_stats()
    isbn_cache.cache.clear()
    api_cache.cache.clear()
    return {
        'isbn_cache': isbn_stats,
        'api_cache': api_stats
    }

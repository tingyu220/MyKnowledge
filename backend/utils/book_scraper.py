# -*- coding: utf-8 -*-
"""
图书信息爬取模块

数据源（按优先级）：
  1. Open Library API：公开接口，无需爬虫，支持 ISBN-10/13。
  2. Google Books API：支持 isbn 查询，无需 Key，有速率限制。
  3. 豆瓣、京东、当当：网页爬取，遵守 robots.txt 规则，受反爬与页面改版影响，作补充。

指定网站爬取：在 config 或环境变量中设置 BOOK_SOURCES，逗号分隔，如：
  BOOK_SOURCES=openlibrary,googlebooks    仅用 API，不爬国内站
  BOOK_SOURCES=openlibrary,douban,jd,dangdang  默认全部

robots.txt 遵守：
  - 爬取前检查 robots.txt，禁止访问的 URL 自动跳过
  - 遵守 Crawl-delay 延迟要求
  - 使用规范的 User-Agent: MyKnowledgeBot/1.0

简介提取：
  - 自动识别并提取网页中的书籍简介
  - 支持多个选择器，按优先级尝试
  - 自动清理多余空白和换行
  - 限制在 2000 字以内（数据库字段支持）

流程：接收 ISBN -> 检查缓存 -> 依次尝试各数据源 -> 缓存结果 -> 任一返回有效 title 即成功。
技术：Requests；BeautifulSoup 解析 HTML；Open Library / Google Books 解析 JSON；urllib.robotparser 解析 robots.txt。

缓存：
  - ISBN查询结果缓存24小时
  - 避免重复爬取相同的ISBN
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests
from bs4 import BeautifulSoup
from utils.robots_checker import check_robots_and_wait
from utils.cache import get_isbn_cache

logger = logging.getLogger(__name__)

# 统一的 User-Agent（遵守 robots.txt 规范）
SCRAPER_USER_AGENT = 'MyKnowledgeBot/1.0 (+https://github.com) (Educational/Research Use)'

# 可选：从 config 读取数据源与调试开关，避免循环引用时可直接改此处
try:
    from config import Config
    BOOK_SOURCES = getattr(Config, 'BOOK_SOURCES', None)
    SCRAPER_DEBUG = getattr(Config, 'SCRAPER_DEBUG', False)
    _total_timeout = getattr(Config, 'SCRAPER_TIMEOUT', None)
except Exception:
    BOOK_SOURCES = None
    SCRAPER_DEBUG = False
    _total_timeout = None

# 默认数据源顺序（优先使用稳定的豆瓣API获取中文分类）
# 可通过 BOOK_SOURCES 环境变量覆盖
DEFAULT_SOURCES = [
    'douban_api',       # 豆瓣API：返回干净的中文分类，优先使用
    'openlibrary',      # Open Library：作为备选
    'googlebooks',      # Google Books：备选
    'amazon',           # Amazon API：备选
    'goodreads',        # Goodreads：备选
    'douban',           # 豆瓣爬虫：兜底
]

# 各数据源超时配置（秒）
SOURCE_TIMEOUTS = {
    'openlibrary': 10,    # Open Library：稳定
    'douban_api': 8,      # 豆瓣API：国内，快速
    'amazon': 8,          # Amazon
    'goodreads': 8,       # Goodreads
    'googlebooks': 8,     # Google Books（国内可能不可用）
    'douban': 12,         # 豆瓣爬虫：兜底
    'jd': 5,              # 京东：反爬强
    'dangdang': 5,        # 当当：反爬强
}

# 总超时时间（秒）- 从 config 读取，默认 20（给豆瓣爬虫更多时间）
TOTAL_SCRAPER_TIMEOUT = _total_timeout if isinstance(_total_timeout, (int, float)) else 20

# 统一返回字段（缺少的填空字符串）
FIELDS = ('title', 'author', 'publisher', 'publish_date', 'description', 'cover_url', 'category')

# 简介最大长度（字符数，约 2000 字）
DESCRIPTION_MAX_LENGTH = 2000


def _extract_and_clean_description(soup, selectors, max_len=DESCRIPTION_MAX_LENGTH):
    """
    通用简介提取函数，尝试多个选择器，返回清理后的文本
    
    :param soup: BeautifulSoup 对象
    :param selectors: 选择器列表，按优先级排序，每个可以是字符串（CSS选择器）或字典 {'tag': 'div', 'id': 'xxx', 'class': 'xxx'}
    :param max_len: 最大长度，默认 2000
    :return: 清理后的简介文本
    """
    description = ''
    
    for selector in selectors:
        elem = None
        if isinstance(selector, str):
            # CSS 选择器
            elem = soup.select_one(selector)
        elif isinstance(selector, dict):
            # 字典形式：{'tag': 'div', 'id': 'xxx', 'class': 'xxx'} 或 {'tag': 'div', 'id': 'xxx', 'class': ['xxx', 'yyy']}
            tag = selector.get('tag', 'div')
            attrs = {}
            if 'id' in selector:
                attrs['id'] = selector['id']
            if 'class' in selector:
                # BeautifulSoup 的 class 可以是字符串或列表
                cls = selector['class']
                if isinstance(cls, list):
                    attrs['class'] = cls
                elif isinstance(cls, str):
                    # 字符串可能包含多个类名，用空格分隔
                    attrs['class'] = [c.strip() for c in cls.split() if c.strip()]
            elem = soup.find(tag, attrs=attrs) if attrs else soup.find(tag)
        
        if elem:
            text = elem.get_text(separator=' ', strip=True)
            if text and len(text) > len(description):
                description = text
                if len(description) >= max_len:
                    break
    
    # 清理：移除多余空白、换行
    if description:
        import re
        description = re.sub(r'\s+', ' ', description)  # 多个空白合并为一个空格
        description = description.strip()
        # 截断到最大长度
        if len(description) > max_len:
            description = description[:max_len].rsplit(' ', 1)[0] + '...'  # 在单词边界截断
    
    return description


def _normalize_result(data: dict[str, Any]) -> dict[str, str]:
    """保证返回包含所有 FIELDS，缺失的用 ''。description 限制在 2000 字以内。"""
    out = {k: (data.get(k) or '') for k in FIELDS}
    for k in out:
        if not isinstance(out[k], str):
            out[k] = str(out[k]).strip() if out[k] is not None else ''
        else:
            out[k] = (out[k] or '').strip()
    
    # description 特殊处理：确保不超过 2000 字
    if 'description' in out and len(out['description']) > DESCRIPTION_MAX_LENGTH:
        out['description'] = out['description'][:DESCRIPTION_MAX_LENGTH].rsplit(' ', 1)[0] + '...'
    
    return out


def scrape_book_info(isbn: str, timeout: float = TOTAL_SCRAPER_TIMEOUT) -> dict[str, str] | None:
    """
    快速尝试多个数据源，任一返回有效 title 即成功。
    整体超时 timeout 秒。

    使用缓存避免重复查询同一ISBN
    """
    import time
    import signal
    from functools import wraps

    isbn = (isbn or '').strip().replace('-', '').replace(' ', '')
    if not isbn:
        return None

    # 检查缓存
    isbn_cache = get_isbn_cache()
    cached = isbn_cache.get(isbn)
    if cached:
        print(f"[DEBUG] ISBN={isbn} 命中缓存，直接返回")
        return cached

    sources = BOOK_SOURCES if BOOK_SOURCES is not None else DEFAULT_SOURCES
    print(f"[DEBUG] 开始爬取 ISBN={isbn}, 总超时={timeout}s")

    source_funcs = {
        'douban_api': lambda: scrape_from_douban_api(isbn),
        'openlibrary': lambda: scrape_from_openlibrary(isbn),
        'googlebooks': lambda: scrape_from_googlebooks(isbn),
        'amazon': lambda: scrape_from_amazon(isbn),
        'goodreads': lambda: scrape_from_goodreads(isbn),
        'douban': lambda: scrape_from_douban(isbn),
        'jd': lambda: scrape_from_jd(isbn),
        'dangdang': lambda: scrape_from_dangdang(isbn),
    }

    def call_with_timeout(name, func, timeout_seconds):
        """带单次超时的数据源调用"""
        import threading

        result = {'data': None, 'error': None, 'done': False}

        def worker():
            try:
                result['data'] = func()
            except Exception as e:
                result['error'] = str(e)
            finally:
                result['done'] = True

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout_seconds)

        if thread.is_alive():
            # 超时，返回 None
            return None
        if result['error']:
            print(f"[DEBUG] {name} 异常: {str(result['error'])[:50]}")
        return result['data']

    start_time = time.time()

    for name in sources:
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            print(f"[DEBUG] 总超时 {timeout}s，退出")
            break

        # 获取该数据源的超时时间（默认5秒）
        source_timeout = SOURCE_TIMEOUTS.get(name, 5)
        # 剩余时间不能超过数据源超时
        remaining = timeout - elapsed
        actual_timeout = min(source_timeout, remaining)

        print(f"[DEBUG] 尝试数据源: {name} (超时={actual_timeout}s)")

        result = call_with_timeout(name, source_funcs[name], actual_timeout)
        if result and (result.get('title') or '').strip():
            print(f"[DEBUG] {name} 返回成功! 耗时 {time.time()-start_time:.1f}s")
            normalized = _normalize_result(result)
            # 缓存结果（24小时）
            isbn_cache.set(isbn, normalized)
            return normalized
        print(f"[DEBUG] {name} 无有效结果")

    print(f"[DEBUG] 所有数据源失败，ISBN={isbn}")
    return None


# ---------- Open Library API（首选，无需爬虫） ----------


def scrape_from_openlibrary(isbn: str) -> dict[str, str] | None:
    """
    从 Open Library Books API 获取图书信息。
    文档：https://openlibrary.org/dev/docs/api/books
    请求：GET openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=data&format=json
    """
    import socket
    import time
    socket.setdefaulttimeout(10)

    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&jscmd=data&format=json"
    headers = {
        'User-Agent': SCRAPER_USER_AGENT,
        'Accept': 'application/json',
    }

    # 简单重试机制（最多2次）
    max_retries = 2
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=SOURCE_TIMEOUTS.get('openlibrary', 10))
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError as e:
            print(f"[Open Library] 连接失败 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 等待1秒后重试
                continue
            return None
        except Exception as e:
            print(f"[Open Library] 请求异常: {e}")
            return None

    key = f'ISBN:{isbn}'
    # 也尝试 ISBN-13 / ISBN-10 互查
    if key not in data:
        for k in data:
            if k.startswith('ISBN:'):
                key = k
                break
        else:
            return None

    raw = data[key]
    title = (raw.get('title') or '').strip()
    if not title:
        return None

    authors = raw.get('authors') or []
    if isinstance(authors, dict):
        authors = [authors]
    author = ', '.join(
        a.get('name', '') for a in authors if isinstance(a, dict) and a.get('name')
    ).strip()

    publishers = raw.get('publishers') or []
    if isinstance(publishers, dict):
        publishers = [publishers]
    publisher = ', '.join(
        p.get('name', '') if isinstance(p, dict) else str(p)
        for p in (publishers or [])
    ).strip()

    publish_date = (raw.get('publish_date') or '').strip()

    description = ''
    for field in ('description', 'notes', 'excerpts', 'first_sentence'):
        v = raw.get(field)
        if isinstance(v, str):
            desc = v.strip()
            if len(desc) > len(description):
                description = desc
        elif isinstance(v, dict):
            desc = v.get('value') or v.get('type')
            if isinstance(desc, str):
                desc = desc.strip()
                if len(desc) > len(description):
                    description = desc
        elif isinstance(v, list) and v:
            for item in v:
                if isinstance(item, dict):
                    desc = item.get('value') or item.get('text')
                    if isinstance(desc, str):
                        desc = desc.strip()
                        if len(desc) > len(description):
                            description = desc
                elif isinstance(item, str):
                    desc = item.strip()
                    if len(desc) > len(description):
                        description = desc

    if len(description) > DESCRIPTION_MAX_LENGTH:
        description = description[:DESCRIPTION_MAX_LENGTH].rsplit(' ', 1)[0] + '...'

    cover_url = ''
    cov = raw.get('cover')
    if isinstance(cov, dict):
        cover_url = (cov.get('medium') or cov.get('large') or cov.get('small') or '').strip()
    if not cover_url and raw.get('covers'):
        cid = raw['covers'][0] if raw['covers'] else None
        if cid is not None:
            cover_url = f"https://covers.openlibrary.org/b/id/{cid}-M.jpg"

    subjects = raw.get('subjects') or []
    if isinstance(subjects, dict):
        subjects = list(subjects.values()) if subjects else []

    # 过滤掉明显不是分类的项（如作者名、年份、奖项等）
    filtered = []
    exclude_patterns = [
        'fiction', 'nonfiction', 'literature', 'english literature',
        'award', 'prize', 'hugo', 'nebula', 'pulitzer',
        'audio', 'cd', 'dvd', 'electronic',
        'Accessible Book', 'Full Text', 'Lending', 'Catalog',
        '1900', '2000', '2010', '2020',  # 年份
    ]
    for s in (subjects or [])[:5]:
        name = s.get('name', '') if isinstance(s, dict) else str(s)
        name_lower = name.lower()
        # 跳过太短或包含排除模式的
        if len(name) < 3:
            continue
        if any(p.lower() in name_lower for p in exclude_patterns):
            continue
        # 跳过包含冒号开头的（通常是 tags）
        if ':' in name:
            continue
        filtered.append(name)

    category = ', '.join(filtered[:3]).strip()

    return {
        'title': title,
        'author': author,
        'publisher': publisher,
        'publish_date': publish_date,
        'description': description,
        'cover_url': cover_url,
        'category': category,
    }


# ---------- 豆瓣 API（官方接口，无需爬虫，速度快） ----------


def scrape_from_douban_api(isbn: str) -> dict[str, str] | None:
    """
    从豆瓣图书 API 获取图书信息。
    接口：GET https://api.douban.com/v2/book/isbn/:isbn
    无需 API Key，有频率限制。
    返回中文数据，封面和简介质量较好。
    """
    url = f"https://api.douban.com/v2/book/isbn/{isbn}"
    headers = {
        'User-Agent': SCRAPER_USER_AGENT,
        'Accept': 'application/json',
    }
    try:
        resp = requests.get(url, headers=headers, timeout=SOURCE_TIMEOUTS.get('douban_api', 5))
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None

    title = (data.get('title') or '').strip()
    if not title:
        return None

    # 作者可能是字符串或列表
    author_raw = data.get('author')
    if isinstance(author_raw, list):
        author = ', '.join(str(a).strip() for a in author_raw if a).strip()
    elif isinstance(author_raw, str):
        author = author_raw.strip()
    else:
        author = ''

    publisher = (data.get('publisher') or '').strip()
    publish_date = (data.get('pubdate') or '').strip()

    description = ''
    desc_raw = data.get('summary') or data.get('content') or ''
    if isinstance(desc_raw, str):
        description = desc_raw.strip()
    if len(description) > DESCRIPTION_MAX_LENGTH:
        description = description[:DESCRIPTION_MAX_LENGTH].rsplit(' ', 1)[0] + '...'

    cover_url = (data.get('image') or '').strip()
    if cover_url and cover_url.startswith('http:'):
        cover_url = 'https:' + cover_url[5:]

    # 分类
    tags = data.get('tags') or []
    if isinstance(tags, list):
        category = ', '.join(str(t.get('name', '')) for t in tags[:3] if t.get('name')).strip()
    else:
        category = ''

    return {
        'title': title,
        'author': author,
        'publisher': publisher,
        'publish_date': publish_date,
        'description': description,
        'cover_url': cover_url,
        'category': category,
    }


# ---------- Google Books API（备选，支持 isbn 查询） ----------


def scrape_from_googlebooks(isbn: str) -> dict[str, str] | None:
    """
    从 Google Books API 获取图书信息。
    请求：GET www.googleapis.com/books/v1/volumes?q=isbn:{isbn}
    无需 API Key，有速率限制。
    """
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&maxResults=1"
    headers = {
        'User-Agent': SCRAPER_USER_AGENT,
        'Accept': 'application/json',
    }

    try:
        resp = requests.get(url, headers=headers, timeout=SOURCE_TIMEOUTS.get('googlebooks', 8))
        # 处理HTTP错误
        if resp.status_code == 503:
            print(f"[Google Books] 服务暂时不可用 (503 Service Unavailable)")
            return None
        if resp.status_code != 200:
            print(f"[Google Books] HTTP错误: {resp.status_code}")
            return None
        data = resp.json()
    except requests.exceptions.ConnectionError as e:
        print(f"[Google Books] 连接失败: {e}")
        return None
    except requests.exceptions.Timeout as e:
        print(f"[Google Books] 请求超时: {e}")
        return None
    except Exception as e:
        print(f"[Google Books] 异常: {e}")
        return None

    items = data.get('items') or []
    if not items:
        return None

    vi = items[0].get('volumeInfo') or {}
    title = (vi.get('title') or '').strip()
    if not title:
        return None

    authors = vi.get('authors') or []
    author = ', '.join(str(a) for a in authors).strip() if authors else ''

    publisher = (vi.get('publisher') or '').strip()

    publish_date = (vi.get('publishedDate') or '').strip()

    description = ''
    desc = vi.get('description') or vi.get('textSnippet')
    if isinstance(desc, str):
        description = desc.strip()
    if len(description) > DESCRIPTION_MAX_LENGTH:
        description = description[:DESCRIPTION_MAX_LENGTH].rsplit(' ', 1)[0] + '...'

    cover_url = ''
    imgs = vi.get('imageLinks') or {}
    for k in ('medium', 'thumbnail', 'small', 'smallThumbnail', 'large'):
        u = imgs.get(k)
        if isinstance(u, str) and u.strip():
            cover_url = u.strip()
            if cover_url.startswith('http:'):
                cover_url = 'https:' + cover_url[5:]
            break

    # 分类
    categories = vi.get('categories') or []
    if isinstance(categories, list):
        category = ', '.join(str(c) for c in categories[:3] if c).strip()
    else:
        category = ''

    return {
        'title': title,
        'author': author,
        'publisher': publisher,
        'publish_date': publish_date,
        'description': description,
        'cover_url': cover_url,
        'category': category,
    }


# ---------- 豆瓣（网页爬取，易受反爬与改版影响） ----------


def scrape_from_douban(isbn: str) -> dict[str, str] | None:
    """从豆瓣图书详情页爬取（遵守 robots.txt）。直接访问 ISBN 详情页。"""
    # 直接用 ISBN 访问豆瓣图书详情页（更可靠）
    detail_url = f"https://book.douban.com/isbn/{isbn}/"
    
    # 检查 robots.txt
    if not check_robots_and_wait(detail_url):
        if SCRAPER_DEBUG:
            logger.warning(f"豆瓣 robots.txt 禁止访问: {detail_url}")
        return None
    
    headers = {
        'User-Agent': SCRAPER_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://book.douban.com/',
    }
    try:
        resp = requests.get(detail_url, headers=headers, timeout=SOURCE_TIMEOUTS.get('douban', 10))
        resp.raise_for_status()
        # 修复编码：强制使用 UTF-8 解码，避免乱码
        resp.encoding = 'utf-8'
    except Exception as e:
        print(f"[豆瓣] 详情页请求失败: {e}")
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    
    title_elem = soup.find('span', property='v:itemreviewed')
    title = (title_elem.get_text() or '').strip() if title_elem else ''
    if not title:
        # 尝试备用选择器
        title_elem = soup.find('h1')
        if title_elem:
            title = (title_elem.get_text() or '').strip()
    if not title:
        print(f"[豆瓣] 未找到标题")
        return None

    info_elem = soup.find('div', id='info')
    info_text = (info_elem.get_text() or '') if info_elem else ''

    author = ''
    m = re.search(r'作者[:\s]+([^\n]+)', info_text)
    if m:
        author = m.group(1).strip()

    publisher = ''
    m = re.search(r'出版社[:\s]+([^\n]+)', info_text)
    if m:
        publisher = m.group(1).strip()

    publish_date = ''
    m = re.search(r'出版年[:\s]+([^\n]+)', info_text)
    if m:
        publish_date = m.group(1).strip()

    # 豆瓣简介：尝试多个选择器
    # 优先尝试完整简介（展开的），再尝试简短简介
    description = ''
    intro_div = soup.find('div', id='link-report')
    if intro_div:
        # 尝试完整简介（展开的）
        full_span = intro_div.find('span', class_='all hidden')
        if full_span:
            description = full_span.get_text(separator=' ', strip=True)
        else:
            # 尝试简短简介
            short_span = intro_div.find('span', class_='short')
            if short_span:
                description = short_span.get_text(separator=' ', strip=True)
    
    # 如果还没找到，尝试其他选择器
    if not description:
        description = _extract_and_clean_description(
            soup,
            [
                'div.intro',
                'div.summary',
                'div.content',
            ]
        )
    
    # 清理和截断
    if description:
        description = re.sub(r'\s+', ' ', description).strip()
        if len(description) > DESCRIPTION_MAX_LENGTH:
            description = description[:DESCRIPTION_MAX_LENGTH].rsplit(' ', 1)[0] + '...'

    cover_url = ''
    cover_img = soup.find('img', alt=title) or soup.find('div', id='mainpic')
    if cover_img and cover_img.name == 'img':
        cover_url = (cover_img.get('src') or '').strip()
    elif cover_img:
        img = cover_img.find('img')
        if img:
            cover_url = (img.get('src') or '').strip()

    # 分类：从页面提取标签/分类
    category = ''
    # 方法1：查找 "标签" 后的链接
    tag_links = soup.find_all('a', class_='tag')
    if tag_links:
        tags = [a.get_text(strip=True) for a in tag_links[:3] if a.get_text(strip=True)]
        category = ', '.join(tags)
    else:
        # 方法2：查找 info 区附近的分类
        if info_elem:
            # 从 info 区查找冒号后的内容
            info_html = str(info_elem)
            m = re.search(r'丛书[:\s]+([^\n<]+)', info_text)
            if m:
                category = m.group(1).strip()

    return {
        'title': title,
        'author': author,
        'publisher': publisher,
        'publish_date': publish_date,
        'description': description,
        'cover_url': cover_url,
        'category': category,
    }


# ---------- 京东（搜索页多 AJAX 渲染，requests 常拿不到商品列表） ----------


def scrape_from_jd(isbn: str) -> dict[str, str] | None:
    """从京东图书搜索 + 详情页爬取（遵守 robots.txt）。京东搜索多为 JS 渲染，可能拿不到结果。"""
    url = f"https://search.jd.com/Search?keyword={isbn}&enc=utf-8"
    
    # 检查 robots.txt
    if not check_robots_and_wait(url):
        if SCRAPER_DEBUG:
            logger.warning(f"京东 robots.txt 禁止访问: {url}")
        return None
    
    headers = {
        'User-Agent': SCRAPER_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    resp = requests.get(url, headers=headers, timeout=SOURCE_TIMEOUTS.get('jd', 8))
    resp.raise_for_status()
    # 修复编码
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')

    product = soup.find('div', class_='p-name')
    if not product:
        return None

    title_elem = product.find('em')
    title = (title_elem.get_text() or '').strip() if title_elem else ''
    if not title:
        return None

    link = product.find('a')
    if not link:
        return None

    href = link.get('href') or ''
    detail_url = ('https:' + href) if href.startswith('//') else href
    if not detail_url.startswith('http'):
        return None
    
    # 检查详情页 robots.txt 并等待延迟
    if not check_robots_and_wait(detail_url):
        if SCRAPER_DEBUG:
            logger.warning(f"京东 robots.txt 禁止访问详情页: {detail_url}")
        return None
    
    detail_resp = requests.get(detail_url, headers=headers, timeout=SOURCE_TIMEOUTS.get('jd', 8))
    detail_resp.raise_for_status()
    # 修复编码
    detail_resp.encoding = 'utf-8'
    dsoup = BeautifulSoup(detail_resp.text, 'html.parser')

    author = ''
    ae = dsoup.find('a', href=re.compile(r'/author/'))
    if ae:
        author = (ae.get_text() or '').strip()

    publisher = ''
    pe = dsoup.find('a', href=re.compile(r'/publisher/'))
    if pe:
        publisher = (pe.get_text() or '').strip()

    publish_date = ''
    plist = dsoup.find('div', class_='p-parameter-list')
    if plist:
        m = re.search(r'出版时间[:\s]+(\d{4}-\d{2}(?:-\d{2})?)', plist.get_text() or '')
        if m:
            publish_date = m.group(1)

    # 京东简介：尝试多个选择器
    description = _extract_and_clean_description(
        dsoup,
        [
            'div.book-detail-content',  # 图书详情内容
            'div.itemInfo-wrap div.itemInfo-tips',  # 商品信息提示
            'div.p-parameter-list',  # 参数列表（可能包含简介）
            'div.detail-content',  # 详情内容
        ]
    )

    cover_url = ''
    ce = dsoup.find('img', id='spec-img')
    if ce:
        cover_url = (ce.get('src') or '').strip()
        if cover_url and not cover_url.startswith('http'):
            cover_url = 'https:' + cover_url

    return {
        'title': title,
        'author': author,
        'publisher': publisher,
        'publish_date': publish_date,
        'description': description,
        'cover_url': cover_url,
        'category': '',
    }


# ---------- Amazon Books API（通过ISBN搜索） ----------


def scrape_from_amazon(isbn: str) -> dict[str, str] | None:
    """
    从 Amazon 商品搜索获取图书信息。
    使用 ISBN 搜索，返回 JSON 数据。
    """
    url = f"https://www.amazon.cn/s?k={isbn}&i=stripbooks&ref=ntt_srch_stp_1"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/json',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }

    try:
        resp = requests.get(url, headers=headers, timeout=SOURCE_TIMEOUTS.get('amazon', 8))
        if resp.status_code != 200:
            return None
        # 修复编码
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 查找第一个商品
        product = soup.find('div', class_='sg-col-inner')
        if not product:
            return None

        # 获取标题
        title_elem = product.find('span', class_='a-size-medium')
        if not title_elem:
            title_elem = product.find('h2')
        title = (title_elem.get_text() or '').strip() if title_elem else ''

        if not title:
            return None

        # 获取作者
        author = ''
        author_elem = product.find('a', class_='a-size-base')
        if author_elem:
            author = (author_elem.get_text() or '').strip()

        # 获取出版社
        publisher = ''

        # 获取封面
        cover_url = ''
        img_elem = product.find('img', class_='s-image')
        if img_elem:
            cover_url = (img_elem.get('src') or img_elem.get('data-src') or '').strip()

        return {
            'title': title,
            'author': author,
            'publisher': publisher,
            'publish_date': '',
            'description': '',
            'cover_url': cover_url,
            'category': '',
        }
    except Exception as e:
        print(f"[Amazon] 请求异常: {e}")
        return None


# ---------- Goodreads API ----------


def scrape_from_goodreads(isbn: str) -> dict[str, str] | None:
    """
    从 Goodreads API 获取图书信息。
    文档：https://www.goodreads.com/api
    注意：Goodreads需要API Key，这里使用网页搜索方式
    """
    url = f"https://www.goodreads.com/search?q={isbn}&search_type=books&search[field]=isbn"
    headers = {
        'User-Agent': SCRAPER_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml',
    }

    try:
        resp = requests.get(url, headers=headers, timeout=SOURCE_TIMEOUTS.get('goodreads', 8))
        if resp.status_code != 200:
            return None
        # 修复编码
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 查找第一个结果
        book_elem = soup.find('tr', class_='bookalike')
        if not book_elem:
            return None

        # 获取标题
        title_elem = book_elem.find('span', class_='bookTitle')
        title = (title_elem.get_text() or '').strip() if title_elem else ''

        if not title:
            return None

        # 获取作者
        author = ''
        author_elem = book_elem.find('span', class_='authorName')
        if author_elem:
            author = (author_elem.get_text() or '').strip()

        # 获取封面
        cover_url = ''
        img_elem = book_elem.find('img')
        if img_elem:
            cover_url = (img_elem.get('src') or '').strip()

        return {
            'title': title,
            'author': author,
            'publisher': '',
            'publish_date': '',
            'description': '',
            'cover_url': cover_url,
            'category': '',
        }
    except Exception as e:
        print(f"[Goodreads] 请求异常: {e}")
        return None


# ---------- 当当（网页爬取） ----------


def scrape_from_dangdang(isbn: str) -> dict[str, str] | None:
    """从当当图书搜索 + 详情页爬取（遵守 robots.txt）。"""
    url = f"https://search.dangdang.com/?key={isbn}"
    
    # 检查 robots.txt
    if not check_robots_and_wait(url):
        if SCRAPER_DEBUG:
            logger.warning(f"当当 robots.txt 禁止访问: {url}")
        return None
    
    headers = {
        'User-Agent': SCRAPER_USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    resp = requests.get(url, headers=headers, timeout=SOURCE_TIMEOUTS.get('dangdang', 8))
    resp.raise_for_status()
    # 修复编码
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')

    product = soup.find('a', class_='pic')
    if not product:
        return None

    detail_url = (product.get('href') or '').strip()
    if not detail_url:
        return None
    if not detail_url.startswith('http'):
        detail_url = 'https:' + detail_url
    
    # 检查详情页 robots.txt 并等待延迟
    if not check_robots_and_wait(detail_url):
        if SCRAPER_DEBUG:
            logger.warning(f"当当 robots.txt 禁止访问详情页: {detail_url}")
        return None
    
    detail_resp = requests.get(detail_url, headers=headers, timeout=SOURCE_TIMEOUTS.get('dangdang', 8))
    detail_resp.raise_for_status()
    # 修复编码
    detail_resp.encoding = 'utf-8'
    dsoup = BeautifulSoup(detail_resp.text, 'html.parser')

    title_elem = dsoup.find('h1', class_='name_info')
    title = (title_elem.get_text() or '').strip() if title_elem else ''
    if not title:
        return None

    author = ''
    ae = dsoup.find('span', class_='t1')
    if ae:
        alink = ae.find('a')
        if alink:
            author = (alink.get_text() or '').strip()

    publisher = ''
    pe = dsoup.find('span', class_='t1', string=re.compile('出版社'))
    if pe:
        nx = pe.find_next_sibling() or pe.find_next()
        if nx:
            pa = nx.find('a') if nx.name != 'a' else nx
            if pa:
                publisher = (pa.get_text() or '').strip()

    publish_date = ''
    pde = dsoup.find('span', string=re.compile('出版时间'))
    if pde:
        nx = pde.find_next_sibling() or pde.find_next('span')
        if nx:
            publish_date = (nx.get_text() or '').strip()

    # 当当简介：尝试多个选择器
    description = _extract_and_clean_description(
        dsoup,
        [
            'div.descrip',  # 简介
            'div.content',  # 内容
            'div.book_intro',  # 图书简介
            'div.detail',  # 详情
        ]
    )

    cover_url = ''
    ce = dsoup.find('img', id='largePic')
    if ce:
        cover_url = (ce.get('src') or '').strip()

    return {
        'title': title,
        'author': author,
        'publisher': publisher,
        'publish_date': publish_date,
        'description': description,
        'cover_url': cover_url,
        'category': '',
    }

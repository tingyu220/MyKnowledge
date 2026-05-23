# -*- coding: utf-8 -*-
"""
robots.txt 解析与检查模块
遵守网站的爬虫规则，避免违反 robots.txt 协议
"""
import time
import urllib.robotparser
from urllib.parse import urlparse
from typing import Optional


class RobotsChecker:
    """robots.txt 检查器，支持缓存和延迟控制"""
    
    def __init__(self, user_agent: str = 'MyKnowledgeBot/1.0'):
        """
        初始化 robots.txt 检查器
        :param user_agent: 爬虫的 User-Agent
        """
        self.user_agent = user_agent
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_fetch: dict[str, float] = {}
        self._crawl_delays: dict[str, float] = {}
        self._last_request: dict[str, float] = {}
    
    def _get_robots_url(self, base_url: str) -> str:
        """获取 robots.txt 的 URL"""
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    def _fetch_robots(self, base_url: str) -> Optional[urllib.robotparser.RobotFileParser]:
        """
        获取并解析 robots.txt（带缓存）
        :param base_url: 网站基础 URL
        :return: RobotFileParser 对象，失败返回 None
        """
        robots_url = self._get_robots_url(base_url)
        domain = urlparse(base_url).netloc
        
        # 检查缓存（5 分钟有效期）
        if domain in self._parsers:
            last_fetch = self._last_fetch.get(domain, 0)
            if time.time() - last_fetch < 300:  # 5 分钟缓存
                return self._parsers[domain]
        
        try:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            
            # 缓存解析结果
            self._parsers[domain] = rp
            self._last_fetch[domain] = time.time()
            
            # 获取 Crawl-delay
            delay = rp.crawl_delay(self.user_agent)
            if delay:
                self._crawl_delays[domain] = float(delay)
            
            return rp
        except Exception as e:
            # robots.txt 获取失败，记录但不阻止爬取（某些网站可能没有）
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"无法获取 robots.txt ({robots_url}): {e}")
            return None
    
    def can_fetch(self, url: str) -> bool:
        """
        检查是否允许爬取指定 URL
        :param url: 要爬取的 URL
        :return: True 允许，False 禁止
        """
        try:
            rp = self._fetch_robots(url)
            if rp is None:
                # 无法获取 robots.txt，默认允许（但建议谨慎）
                return True
            
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            # 解析失败，默认允许（但建议谨慎）
            return True
    
    def get_crawl_delay(self, url: str) -> float:
        """
        获取指定网站的爬取延迟（秒）
        :param url: 网站 URL
        :return: 延迟秒数，默认 1.0
        """
        domain = urlparse(url).netloc
        return self._crawl_delays.get(domain, 1.0)
    
    def wait_if_needed(self, url: str):
        """
        如果需要，等待爬取延迟
        :param url: 要爬取的 URL
        """
        domain = urlparse(url).netloc
        delay = self.get_crawl_delay(url)
        last_request = self._last_request.get(domain, 0)
        elapsed = time.time() - last_request
        
        if elapsed < delay:
            wait_time = delay - elapsed
            time.sleep(wait_time)
        
        self._last_request[domain] = time.time()


# 全局 robots.txt 检查器实例
_robots_checker = RobotsChecker(user_agent='MyKnowledgeBot/1.0 (+https://github.com) (Educational/Research Use)')


def check_robots_and_wait(url: str) -> bool:
    """
    检查 robots.txt 并等待延迟（便捷函数）
    :param url: 要爬取的 URL
    :return: True 允许爬取，False 禁止
    """
    if not _robots_checker.can_fetch(url):
        return False
    
    _robots_checker.wait_if_needed(url)
    return True

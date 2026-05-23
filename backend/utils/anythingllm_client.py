# -*- coding: utf-8 -*-
"""
AnythingLLM API 客户端

提供与 AnythingLLM 向量数据库的交互功能：
1. 向量搜索（检索相关文档）
2. 工作区验证
3. 错误处理和重试

基于测试结果，正确的工作区 slug 是：mykownledge
"""
import os
import requests
import json
import logging
from typing import List, Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class AnythingLLMClient:
    """
    AnythingLLM API 客户端

    配置参数（从 config.py 或环境变量读取）：
    - API_KEY: AnythingLLM API 密钥
    - BASE_URL: AnythingLLM 服务地址（如 http://localhost:3001）
    - WORKSPACE_SLUG: 工作区标识符（slug，注意大小写）

    用法示例：
        client = AnythingLLMClient()
        results = client.vector_search("心理学书籍", limit=5)
    """

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        workspace_slug: str = None
    ):
        """
        初始化 AnythingLLM 客户端

        参数:
            api_key: API密钥（优先从环境变量 ANYTHINGLLM_API_KEY 读取）
            base_url: 服务地址（优先从环境变量 ANYTHINGLLM_BASE_URL 读取）
            workspace_slug: 工作区slug（优先从环境变量 ANYTHINGLLM_WORKSPACE_SLUG 读取）
        """
        # 从环境变量或参数读取配置
        self.api_key = api_key or os.environ.get('ANYTHINGLLM_API_KEY', '')
        self.base_url = (base_url or os.environ.get('ANYTHINGLLM_BASE_URL', 'http://localhost:3001')).rstrip('/')
        self.workspace_slug = workspace_slug or os.environ.get('ANYTHINGLLM_WORKSPACE_SLUG', 'mykownledge')

        if not self.api_key:
            raise ValueError("ANYTHINGLLM_API_KEY 未设置，请通过参数或环境变量配置")

        # 设置请求头
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info(f"AnythingLLMClient 已初始化: {self.base_url}, workspace: {self.workspace_slug}")

    def health_check(self) -> bool:
        """
        健康检查：验证连接和工作区

        返回:
            bool: 连接成功返回 True
        """
        try:
            url = f"{self.base_url}/api/v1/workspaces"
            resp = self.session.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                workspaces = data.get('workspaces', [])
                slugs = [ws.get('slug') for ws in workspaces]
                if self.workspace_slug in slugs:
                    logger.info(f"工作区 '{self.workspace_slug}' 验证成功")
                    return True
                else:
                    logger.error(f"工作区 '{self.workspace_slug}' 不存在，可用工作区: {slugs}")
                    return False
            else:
                logger.error(f"健康检查失败: {resp.status_code} - {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"健康检查异常: {e}")
            return False

    def vector_search(
        self,
        query: str,
        limit: int = 10,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        在 AnythingLLM 工作区中执行向量搜索

        参数:
            query: 搜索查询（如 "心理学书籍"）
            limit: 返回结果数量上限
            **kwargs: 其他参数（目前未使用）

        返回:
            List[Dict]: 检索结果列表，每个结果包含：
                - text: 原文内容
                - score: 相似度分数
                - metadata: 元数据（如文件名、来源等）
        """
        if not query or not query.strip():
            logger.warning("搜索查询为空")
            return []

        # AnythingLLM 向量搜索端点（已确认有效）
        url = f"{self.base_url}/api/v1/workspace/{self.workspace_slug}/vector-search"

        payload = {
            "query": query.strip(),
            "limit": limit
        }

        try:
            logger.debug(f"向量搜索: {query[:50]}...")
            resp = self.session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if resp.status_code == 200:
                data = resp.json()
                results = data.get('results', [])
                logger.info(f"向量搜索成功，找到 {len(results)} 条结果")
                return results
            else:
                logger.error(f"向量搜索失败: {resp.status_code} - {resp.text[:300]}")
                return []

        except requests.exceptions.Timeout:
            logger.error("向量搜索超时（30秒）")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"向量搜索请求异常: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"响应解析失败: {e}, 原始响应: {resp.text[:200]}")
            return []

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        兼容性搜索方法（某些版本AnythingLLM可能使用/search端点）

        当前使用 vector_search 实现，作为别名
        """
        return self.vector_search(query, limit)

    def retrieve(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        兼容性检索方法（别名）

        当前使用 vector_search 实现
        """
        return self.vector_search(query, limit)

    def get_workspace_info(self) -> Optional[Dict[str, Any]]:
        """
        获取工作区信息

        返回:
            工作区信息字典，失败返回 None
        """
        try:
            url = f"{self.base_url}/api/v1/workspace/{self.workspace_slug}"
            resp = self.session.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.warning(f"获取工作区信息失败: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"获取工作区信息异常: {e}")
            return None

    def upload_document(self, filepath: str, filename: str = None) -> Optional[Dict]:
        """
        上传文档到 AnythingLLM

        ��数:
            filepath: 文件路径（绝对路径）
            filename: 可选，自定义文件名（默认为basename）

        返回:
            Dict: 包含 location、filename 等信息的字典，失败返回 None
        """
        url = f"{self.base_url}/api/v1/document/upload"

        if not filename:
            filename = os.path.basename(filepath)

        try:
            with open(filepath, 'rb') as f:
                files = {
                    'file': (filename, f, 'text/plain')
                }
                # 注意：有些版本 AnythingLLM 需要 addToWorkspaces 参数
                data = {
                    'addToWorkspaces': self.workspace_slug
                }

                resp = self.session.post(
                    url,
                    headers=self.headers,  # 上传文件时 requests 会自动移除 Content-Type
                    files=files,
                    data=data,
                    timeout=60
                )

            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"文档上传成功: {filename} -> {result.get('location')}")
                return result
            else:
                logger.error(f"文档上传失败: {resp.status_code} - {resp.text[:300]}")
                return None

        except FileNotFoundError:
            logger.error(f"文件不存在: {filepath}")
            return None
        except Exception as e:
            logger.error(f"文档上传异常: {e}")
            return None

    def delete_document(self, location: str) -> bool:
        """
        删除 AnythingLLM 中的文档

        参数:
            location: 文档的 location（如 "custom-documents/0001-a1b2.json"）

        返回:
            bool: 是否成功
        """
        url = f"{self.base_url}/api/v1/document/delete"

        payload = {
            "location": location
        }

        try:
            resp = self.session.delete(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if resp.status_code == 200:
                logger.info(f"文档删除成功: {location}")
                return True
            else:
                logger.warning(f"文档删除失败: {resp.status_code} - {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"文档删除异常: {e}")
            return False

    def update_workspace_documents(
        self,
        slug: str,
        add_docs: List[str] = None,
        remove_docs: List[str] = None
    ) -> bool:
        """
        更新工作区的文档列表（添加/删除）

        参数:
            slug: 工作区 slug
            add_docs: 要添加的文档 location 列表
            remove_docs: 要删除的文档 location 列表

        返回:
            bool: 是否成功
        """
        url = f"{self.base_url}/api/v1/workspace/{slug}/update-embeddings"

        payload = {}
        if add_docs:
            payload['adds'] = add_docs
        if remove_docs:
            payload['deletes'] = remove_docs

        if not payload:
            return True  # nothing to do

        try:
            resp = self.session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if resp.status_code == 200:
                logger.info(f"工作区 '{slug}' 文档更新成功")
                return True
            else:
                logger.error(f"工作区更新失败: {resp.status_code} - {resp.text[:300]}")
                return False
        except Exception as e:
            logger.error(f"工作区更新异常: {e}")
            return False

    def sync_book_document(self, book_id: int, txt_filepath: str) -> bool:
        """
        同步单本图书的文档到 AnythingLLM 工作区

        流程：
            1. 查找该图书已有的文档记录（通过 book_id）
            2. 从工作区删除旧文档
            3. 上传新文档
            4. 将新文档添加到工作区并更新映射表

        参数:
            book_id: 图书ID
            txt_filepath: TXT文件路径

        返回:
            bool: 是否成功
        """
        try:
            # 延迟导入，避免循环依赖
            from models import AnythingLLMDoc
            from app import db as flask_db

            # 1. 查找旧记录
            old_doc = AnythingLLMDoc.query.filter_by(book_id=book_id).first()

            # 2. 上传新文档
            upload_result = self.upload_document(txt_filepath, filename=f"{book_id:04d}.txt")
            if not upload_result:
                return False

            new_location = upload_result.get('location')
            if not new_location:
                logger.error("上传响应缺少 location 字段")
                return False

            # 3. 删除旧文档（如果存在）
            if old_doc:
                success = self.delete_document(old_doc.location)
                if not success:
                    logger.warning(f"删除旧文档失败，但将继续添加新文档: {old_doc.location}")

            # 4. 添加到工作区
            success = self.update_workspace_documents(
                slug=self.workspace_slug,
                add_docs=[new_location]
            )

            if success:
                # 5. 保存/更新映射记录
                if old_doc:
                    old_doc.location = new_location
                    old_doc.filename = f"{book_id:04d}.txt"
                else:
                    new_doc = AnythingLLMDoc(
                        book_id=book_id,
                        location=new_location,
                        filename=f"{book_id:04d}.txt"
                    )
                    flask_db.session.add(new_doc)

                flask_db.session.commit()
                logger.info(f"图书ID={book_id} 文档同步成功")
                return True
            else:
                # 工作区添加失败，删除刚上传的文档（回滚）
                self.delete_document(new_location)
                return False

        except Exception as e:
            logger.error(f"同步文档失败 (book_id={book_id}): {e}")
            return False


# 全局客户端实例（懒加载）
_client_instance = None


def get_anythingllm_client() -> AnythingLLMClient:
    """
    获取全局 AnythingLLM 客户端实例（单例模式）

    返回:
        AnythingLLMClient 实例
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = AnythingLLMClient()
    return _client_instance


def vector_search(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    便捷函数：执行向量搜索

    参数:
        query: 搜索查询
        limit: 返回数量

    返回:
        搜索结果列表
    """
    client = get_anythingllm_client()
    return client.vector_search(query, limit)


def health_check() -> bool:
    """
    便捷函数：健康检查

    返回:
        bool: 连接正常返回 True
    """
    client = get_anythingllm_client()
    return client.health_check()

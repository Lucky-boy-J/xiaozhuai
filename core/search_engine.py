import logging
import httpx
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from typing import Optional

logger = logging.getLogger("search")


class SearchEngine:
    def __init__(self, config: dict):
        self.config = config
        self.backend = config.get("backend", "serper")
        self.api_key = config.get("api_key", "") or ""
        if not self.api_key:
            if self.backend == "serper":
                self.api_key = os.environ.get("SERPER_API_KEY", "")
            elif self.backend == "serpapi":
                self.api_key = os.environ.get("SERPAPI_API_KEY", "")
        self.max_results = config.get("max_results", 5)
        self.timeout = config.get("timeout", 10)
        self.time_window_days = int(config.get("time_window_days", 30) or 30)
        self.min_credibility = float(config.get("min_credibility", 0.25) or 0.25)
        self.trusted_domains = set(config.get("trusted_domains", []) or [])
        self.blocked_domains = set(config.get("blocked_domains", []) or [])
        self.allow_unknown_date = bool(config.get("allow_unknown_date", True))
        self.source_mode = (config.get("source_mode", "any") or "any").strip().lower()
        self.source_domains = [d.strip().lower() for d in (config.get("source_domains", []) or []) if str(d).strip()]
    def search(self, query: str) -> list[dict]:
        
        query = self._apply_source_domains_to_query(query)
        logger.info(f"Searching: {query!r} via {self.backend}")        
        try:
            if self.backend == "serper":
                return self._search_serper(query)
            elif self.backend == "serpapi":
                return self._search_serpapi(query)
            elif self.backend == "brave":
                return self._search_brave(query)
            elif self.backend == "tavily":
                return self._search_tavily(query)
            else:
                return self._search_duckduckgo(query)
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return []

    # ── Serper.dev（推荐）────────────────────────────────

    def _search_serper(self, query: str) -> list[dict]:
        """
        Serper.dev Google Search API
        注册：https://serper.dev
        免费：2500次/月
        """
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "q": query,
            "num": self.max_results,
            "hl": "zh-cn",
            "gl": "cn",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        # 知识图谱（直接答案）
        if "knowledgeGraph" in data:
            kg = data["knowledgeGraph"]
            results.append({
                "title":   kg.get("title", ""),
                "url":     kg.get("website", ""),
                "content": kg.get("description", ""),
                "date":    "",
            })
        # 普通搜索结果
        for r in data.get("organic", [])[:self.max_results]:
            domain = self._extract_domain(r.get("link", ""))
            if not self._domain_allowed(domain):
                continue
            results.append({
                "title":   r.get("title", ""),
                "url":     r.get("link", ""),
                "content": r.get("snippet", ""),
                "date":    r.get("date", ""),
            })
        # 新闻结果
        for r in data.get("news", [])[:3]:
            results.append({
                "title":   r.get("title", ""),
                "url":     r.get("link", ""),
                "content": r.get("snippet", ""),
                "date":    r.get("date", ""),
            })
        return results[:self.max_results]

    # ── SerpApi ──────────────────────────────────────────

    def _search_serpapi(self, query: str) -> list[dict]:
        """
        SerpApi Google Search
        注册：https://serpapi.com
        免费：100次/月
        """
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": self.api_key,
            "engine": "google",
            "num": self.max_results,
            "hl": "zh-cn",
            "gl": "cn",
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("organic_results", [])[:self.max_results]:
            domain = self._extract_domain(r.get("link", ""))
            if not self._domain_allowed(domain):
                continue
            results.append({
                "title":   r.get("title", ""),
                "url":     r.get("link", ""),
                "content": r.get("snippet", ""),
                "date":    r.get("date", ""),
            })
        return results

    # ── Brave Search API ─────────────────────────────────

    def _search_brave(self, query: str) -> list[dict]:
        """
        Brave Search API
        注册：https://api.search.brave.com
        免费：2000次/月
        """
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
        }
        params = {
            "q": query,
            "count": self.max_results,
            "search_lang": "zh-hans",
            "freshness": "pd",    # pd=过去一天, pw=过去一周, pm=过去一月
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("web", {}).get("results", [])[:self.max_results]:
            results.append({
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "content": r.get("description", ""),
                "date":    r.get("age", ""),
            })
        return results

    # ── Tavily ───────────────────────────────────────────

    def _search_tavily(self, query: str) -> list[dict]:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": self.max_results,
            "search_depth": self.config.get("search_depth", "advanced"),
            "topic": self.config.get("topic", "general"),
            "include_answer": False,
            "include_raw_content": False,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("results", []):
            domain = self._extract_domain(r.get("url", ""))
            if not self._domain_allowed(domain):
                continue
            results.append({
                "title":   r.get("title", ""),
                "url":     r.get("url", ""),
                "content": r.get("content", "")[:600],
                "date":    r.get("published_date", ""),
            })
        return results

    # ── DuckDuckGo（兜底）───────────────────────────────

    def _search_duckduckgo(self, query: str) -> list[dict]:
        from duckduckgo_search import DDGS
        import time
        results = []
        for attempt in range(3):
            try:
                with DDGS(timeout=self.timeout) as ddgs:
                    for r in ddgs.text(query, max_results=self.max_results,
                                       region="wt-wt"):
                        domain = self._extract_domain(r.get("href", ""))
                        if not self._domain_allowed(domain):
                            continue
                        results.append({
                            "title":   r.get("title", ""),
                            "url":     r.get("href", ""),
                            "content": r.get("body", "")[:600],
                            "date":    "",
                        })
                if results:
                    break
            except Exception as e:
                logger.warning(f"DDG attempt {attempt+1} failed: {e}")
                time.sleep(1)
        return results

    # ── 格式化 ───────────────────────────────────────────

    def format_results_as_context(self, results: list[dict], query: str) -> str:
        filtered = self._filter_results(results)
        if not filtered:
            return f"搜索「{query}」未找到可信且在时间窗口内的结果，请基于自身知识回答并明确说明信息可能不是最新的。"
 
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=self.time_window_days)
 
        dated = []
        unknown = []
        for r in filtered:
            dt = self._parse_date(r.get("date", ""))
            item = dict(r)
            item["_dt"] = dt
            if dt is None:
                unknown.append(item)
            else:
                dated.append(item)
 
        dated.sort(key=lambda x: x["_dt"], reverse=True)
 
        lines = [
            f"以下是关于「{query}」的实时搜索结果（仅供参考，搜索可能存在索引延迟；时间窗口：最近 {self.time_window_days} 天；当前时间：{now.date()}）：",
            ""
        ]
        idx = 1
        for r in dated:
            dt = r["_dt"]
            date_str = dt.astimezone(timezone.utc).date().isoformat() if dt else ""
            lines.append(f"**[{idx}] {r.get('title','')}**  📅 {date_str}")
            lines.append(f"🔗 {r.get('url','')}")
            if r.get("content"):
                lines.append(r["content"])
            lines.append("")
            idx += 1
 
        if self.allow_unknown_date and unknown:
            lines.append("以下来源未提供明确日期，涉及时效性结论时请谨慎使用：")
            lines.append("")
            for r in unknown:
                lines.append(f"**[{idx}] {r.get('title','')}**  📅 日期未知")
                lines.append(f"🔗 {r.get('url','')}")
                if r.get("content"):
                    lines.append(r["content"])
                lines.append("")
                idx += 1
 
        lines.append("---")
        lines.append(
            "请只基于以上来源回答；需要时间敏感结论时仅使用有日期且在时间窗口内的来源，并用 [编号] 标注引用。"
        )
        return "\n".join(lines)
 
    def format_results_as_sources(self, results: list[dict], query: str) -> str:
        filtered = self._filter_results(results)
        if not filtered:
            return ""
 
        dated = []
        unknown = []
        for r in filtered:
            dt = self._parse_date(r.get("date", ""))
            item = dict(r)
            item["_dt"] = dt
            if dt is None:
                unknown.append(item)
            else:
                dated.append(item)
 
        dated.sort(key=lambda x: x["_dt"], reverse=True)
 
        lines = [
            "",
            "---",
            f"来源（查询：{query}）：",
        ]
        idx = 1
        for r in dated:
            url = (r.get("url") or "").strip()
            title = (r.get("title") or "").strip() or url
            domain = self._extract_domain(url)
            dt = r["_dt"]
            date_str = dt.astimezone(timezone.utc).date().isoformat() if dt else ""
            meta = " · ".join([p for p in (date_str, domain) if p])
            suffix = f"（{meta}）" if meta else ""
            lines.append(f"- [{idx}] [{title}]({url}){suffix}")
            idx += 1
 
        if self.allow_unknown_date and unknown:
            for r in unknown:
                url = (r.get("url") or "").strip()
                title = (r.get("title") or "").strip() or url
                domain = self._extract_domain(url)
                meta = " · ".join([p for p in ("日期未知", domain) if p])
                suffix = f"（{meta}）" if meta else ""
                lines.append(f"- [{idx}] [{title}]({url}){suffix}")
                idx += 1
 
        return "\n".join(lines)
    def _filter_results(self, results: list[dict]) -> list[dict]:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=self.time_window_days)
        out = []
        for r in results:
            url = (r.get("url") or "").strip()
            domain = self._extract_domain(url)
            if domain and domain in self.blocked_domains:
                continue
            score = self._credibility_score(domain)
            if score < self.min_credibility:
                continue
            dt = self._parse_date(r.get("date", ""))
            if dt is not None and dt < window_start:
                continue
            if dt is None and not self.allow_unknown_date:
                continue
            out.append(r)
        if self.source_mode == "only" and self.source_domains:
            out = [r for r in out if self._domain_allowed(self._extract_domain((r.get("url") or "").strip()))]
            return out[: self.max_results]
 
        if self.source_mode == "prefer" and self.source_domains:
            allowed = []
            other = []
            for r in out:
                domain = self._extract_domain((r.get("url") or "").strip())
                (allowed if self._domain_allowed(domain) else other).append(r)
            return (allowed + other)[: self.max_results]

        return out[: self.max_results]
 
    def _credibility_score(self, domain: str) -> float:
        if not domain:
            return 0.0
        if domain in self.trusted_domains:
            return 1.0
        if domain.endswith((".gov", ".gov.cn")):
            return 1.0
        if domain.endswith((".edu", ".edu.cn")):
            return 0.9
        if domain.endswith(".org"):
            return 0.8
        if any(k in domain for k in ("wikipedia.org", "github.com")):
            return 0.8
        if any(k in domain for k in ("zhihu.com", "tieba.baidu.com", "reddit.com", "weibo.com")):
            return 0.2
        return 0.5
 
    @staticmethod
    def _extract_domain(url: str) -> str:
        if not url:
            return ""
        try:
            u = urlparse(url)
            host = u.netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            return host
        except Exception:
            return ""
        
            
    def _domain_allowed(self, domain: str) -> bool:
        if not self.source_domains:
            return True
        if not domain:
            return False
        d = domain.lower()
        for allowed in self.source_domains:
            if d == allowed:
                return True
            if d.endswith("." + allowed):
                return True
        return False
 
    def _apply_source_domains_to_query(self, query: str) -> str:
        if not query:
            return query
        if not self.source_domains:
            return query
        if self.source_mode not in ("only", "prefer"):
            return query
        site_filters = " OR ".join([f"site:{d}" for d in self.source_domains])
        return f"{query} ({site_filters})"

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        s = str(date_str).strip()
        now = datetime.now(timezone.utc)
 
        m = re.search(r"(\d+)\s*(分钟前|小时|小时前|天前|周前|个月前)", s)
        if m:
            n = int(m.group(1))
            unit = m.group(2)
            if unit == "分钟前":
                return now - timedelta(minutes=n)
            if unit in ("小时", "小时前"):
                return now - timedelta(hours=n)
            if unit == "天前":
                return now - timedelta(days=n)
            if unit == "周前":
                return now - timedelta(days=7 * n)
            if unit == "个月前":
                return now - timedelta(days=30 * n)
 
        if s in ("昨天",):
            return now - timedelta(days=1)
 
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(s[:10], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass
 
        m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", s)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return datetime(y, mo, d, tzinfo=timezone.utc)
            except Exception:
                return None
 
        return None
        if not results:
            return f"搜索「{query}」未找到相关结果，请基于自身知识回答并说明信息可能不是最新的。"


        lines = [
            f"以下是关于「{query}」的实时搜索结果，请优先参考日期最新的内容：",
            ""
        ]
        for i, r in enumerate(results, 1):
            date_str = f"  📅 {r['date']}" if r.get("date") else ""
            lines.append(f"**​[{i}] {r['title']}​**{date_str}")
            lines.append(f"🔗 {r['url']}")
            if r.get("content"):
                lines.append(r["content"])
            lines.append("")

        lines.append("---")
        lines.append(
            "请综合以上搜索结果给出准确回答，标注信息来源编号，"
            "如结果存在时效差异请以最新日期为准。"
        )
        return "".join(lines)
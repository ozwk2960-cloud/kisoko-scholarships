"""スクレイパー基盤。

各ソースは BaseSource を継承し fetch_items() を実装する。
- 実行時は run() が例外を捕捉し (items, status) を返す（1ソースの失敗が全体を止めない）。
- テスト時は fetcher を差し替えてfixtureを読ませる（ネットワーク非依存）。
"""

from __future__ import annotations

import time
import urllib.robotparser
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from .. import config
from ..models import Scholarship

Fetcher = Callable[[str], str]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class FetchError(RuntimeError):
    def __init__(self, msg: str, retryable: bool = True) -> None:
        super().__init__(msg)
        self.retryable = retryable


class HttpFetcher:
    """UA・タイムアウト・リトライ・レート制御つきの GET。"""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": config.USER_AGENT})
        self._robots_cache: dict = {}
        self._last_request_at = 0.0

    # -- robots.txt --
    def allowed(self, url: str) -> bool:
        """RFC 9309 準拠の判定。

        200            -> ルールを解釈
        3xx            -> requests がリダイレクト追従
        4xx / 5xx / 例外 -> 「取得不能」とみなし許可（429 は保守的に不許可）
        """
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in self._robots_cache:
            self._robots_cache[origin] = self._load_robots(origin)
        rp = self._robots_cache[origin]
        if rp is None:
            return True
        return rp.can_fetch(config.USER_AGENT, url)

    def _load_robots(self, origin: str):
        rp = urllib.robotparser.RobotFileParser()
        try:
            resp = self._session.get(f"{origin}/robots.txt", timeout=config.REQUEST_TIMEOUT)
        except requests.RequestException:
            return None
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            return rp
        if resp.status_code == 429:
            rp.disallow_all = True
            return rp
        # その他（403/404/5xx 等）は「robots.txt なし」= 全許可
        return None

    # -- GET --
    def __call__(self, url: str) -> str:
        if not self.allowed(url):
            raise FetchError(f"robots.txt により拒否: {url}")

        # レート制御
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < config.POLITE_DELAY:
            time.sleep(config.POLITE_DELAY - elapsed)

        last_exc: Optional[Exception] = None
        for attempt in range(config.MAX_RETRIES):
            try:
                resp = self._session.get(url, timeout=config.REQUEST_TIMEOUT)
                self._last_request_at = time.monotonic()
                if resp.status_code != 200:
                    # 4xx はリトライしても無駄なので即中断
                    retryable = resp.status_code >= 500 or resp.status_code == 429
                    raise FetchError(f"HTTP {resp.status_code}: {url}", retryable)
                resp.encoding = resp.apparent_encoding or resp.encoding
                return resp.text
            except (requests.RequestException, FetchError) as e:
                last_exc = e
                retryable = getattr(e, "retryable", True)
                if retryable and attempt < config.MAX_RETRIES - 1:
                    time.sleep(config.BACKOFF_BASE * (2 ** attempt))
                else:
                    break
        raise FetchError(f"取得失敗（{config.MAX_RETRIES}回試行）: {url} :: {last_exc}")


class BaseSource:
    #: source_status / Scholarship.source に入る表示名
    name: str = "BASE"
    #: ID 生成用スラッグ
    slug: str = "base"

    def __init__(self, fetcher: Optional[Fetcher] = None) -> None:
        self.fetch: Fetcher = fetcher or HttpFetcher()

    # サブクラスが実装
    def fetch_items(self) -> List[Scholarship]:
        raise NotImplementedError

    def run(self) -> Tuple[List[Scholarship], dict]:
        """(items, status) を返す。例外は status.ok=False に変換。"""
        fetched_at = _utc_now_iso()
        try:
            items = self.fetch_items()
            for it in items:
                it.source = self.name
                it.validate_light()
            return items, {
                "source": self.name,
                "ok": True,
                "count": len(items),
                "fetched_at": fetched_at,
            }
        except Exception as e:  # noqa: BLE001  ここで握りつぶすのが仕様
            return [], {
                "source": self.name,
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
                "fetched_at": fetched_at,
            }

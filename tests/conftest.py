"""テスト共通のフィクスチャ。

オフライン fetcher: 実 URL を tests/fixtures/*.html に対応づけ、ネットワークなしで
各ソースの parse をテストする。
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# 実 URL -> フィクスチャファイル名
URL_TO_FIXTURE = {
    # JASSO index
    "https://www.jasso.go.jp/ryugaku/scholarship_a/daigakuin/index.html": "jasso_daigakuin_index.html",
    "https://www.jasso.go.jp/ryugaku/scholarship_a/gakubu/index.html": "jasso_gakubu_index.html",
    # JASSO 大学院学位取得型
    "https://www.jasso.go.jp/ryugaku/scholarship_a/daigakuin/2026.html": "jasso_daigakuin_2026.html",
    "https://www.jasso.go.jp/ryugaku/scholarship_a/daigakuin/2025.html": "jasso_daigakuin_2025.html",
    # JASSO 学部学位取得型
    "https://www.jasso.go.jp/ryugaku/scholarship_a/gakubu/2027.html": "jasso_gakubu_2027.html",
    "https://www.jasso.go.jp/ryugaku/scholarship_a/gakubu/2026.html": "jasso_gakubu_2026.html",
    "https://www.jasso.go.jp/ryugaku/scholarship_a/gakubu/2025.html": "jasso_gakubu_2025.html",
    # トビタテ
    "https://tobitate-mext.jasso.go.jp/": "tobitate_top.html",
    "https://tobitate-mext.jasso.go.jp/newprogram/uv/": "tobitate_uv.html",
}


def load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8", errors="replace") as fh:
        return fh.read()


@pytest.fixture
def fixture_fetcher():
    def _fetch(url: str) -> str:
        name = URL_TO_FIXTURE.get(url)
        if name is None:
            raise AssertionError(f"フィクスチャ未登録の URL: {url}")
        return load_fixture(name)

    return _fetch

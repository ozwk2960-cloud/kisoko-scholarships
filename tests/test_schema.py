"""生成される JSON がスキーマに適合することを検証する。"""

from __future__ import annotations

import json
import os

import jsonschema
import pytest

from scraper.merge import merge
from scraper.run import SCHEMA_PATH
from scraper.sources.jasso import JassoSource
from scraper.sources.tobitate import TobitateSource

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def test_schema_itself_is_valid(schema):
    jsonschema.Draft202012Validator.check_schema(schema)


def test_merged_output_conforms(schema, fixture_fetcher):
    j_items, j_status = JassoSource(fetcher=fixture_fetcher).run()
    t_items, t_status = TobitateSource(fetcher=fixture_fetcher).run()
    merged = merge(
        results={"JASSO": j_items, "トビタテ": t_items},
        statuses=[j_status, t_status],
        previous=None, today="2026-08-30",
    )
    jsonschema.validate(instance=merged, schema=schema)
    assert len(merged["scholarships"]) >= 3


def test_sample_data_conforms(schema):
    with open(os.path.join(ROOT, "public", "scholarships.sample.json"), encoding="utf-8") as fh:
        jsonschema.validate(instance=json.load(fh), schema=schema)


def test_committed_scholarships_json_conforms_if_present(schema):
    path = os.path.join(ROOT, "public", "scholarships.json")
    if not os.path.exists(path):
        pytest.skip("scholarships.json 未生成")
    with open(path, encoding="utf-8") as fh:
        jsonschema.validate(instance=json.load(fh), schema=schema)


def test_missing_optional_fields_are_explicit_null(schema, fixture_fetcher):
    """解析できなかった任意項目は欠損ではなく null で出ていること。"""
    items, _ = JassoSource(fetcher=fixture_fetcher).run()
    d = items[0].to_dict()
    for key in ("amount_monthly_jpy", "deadline", "duration_text", "description"):
        assert key in d  # キー自体は必ず存在する

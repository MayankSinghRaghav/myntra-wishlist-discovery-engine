"""Offline sanity checks for the pure logic (dedup, enum coercion, scoring).
Run: python test_pipeline.py   (or: pytest -q)
"""
import collect
import classify
import analyze
import ingest_apify


def test_collect():
    collect._selftest()


def test_classify():
    classify._selftest()


def test_analyze():
    analyze._selftest()


def test_ingest_apify():
    ingest_apify._selftest()


if __name__ == "__main__":
    test_collect()
    test_classify()
    test_analyze()
    test_ingest_apify()
    print("ALL SELFTESTS PASSED")

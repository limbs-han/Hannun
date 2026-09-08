import gzip
import io
import json
import urllib.error

from jobs import backup_to_b as bk

LISTING = {"FileStatuses": {"FileStatus": [
    {"pathSuffix": "part-00001-b.c000.txt"},
    {"pathSuffix": "part-00000-a.c000.txt"},
    {"pathSuffix": "_SUCCESS"},
]}}
PARTS = {"part-00000-a.c000.txt": b'{"a":1}\n{"a":2}\n', "part-00001-b.c000.txt": b'{"b":3}\n'}


def _opener(url):
    if "op=LISTSTATUS" in url:
        return io.BytesIO(json.dumps(LISTING).encode())
    for name, body in PARTS.items():
        if name in url:
            return io.BytesIO(body)
    raise AssertionError(url)


def test_list_parts_sorted_without_marker_files():
    assert bk.list_parts("2026-09-07", opener=_opener) == [
        "part-00000-a.c000.txt", "part-00001-b.c000.txt"]


def test_missing_partition_returns_none():
    def not_found(url):
        raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

    assert bk.list_parts("1999-01-01", opener=not_found) is None


def test_archive_joins_parts_and_counts_lines(tmp_path):
    out = tmp_path / "news.tar.gz"
    parts = ["part-00000-a.c000.txt", "part-00001-b.c000.txt"]
    assert bk.archive_parts("2026-09-07", parts, out, opener=_opener) == 3
    assert gzip.open(out, "rb").read() == b'{"a":1}\n{"a":2}\n{"b":3}\n'  # 순서 유지, 유실 없음

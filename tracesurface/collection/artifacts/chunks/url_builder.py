from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse


def absolute_chunk_url(path: str, base_url: str) -> str:
    if path.startswith("http"):
        return path.split("?", 1)[0]
    return urljoin(base_url + "/", path).split("?", 1)[0]


def vite_asset_url(path: str, base_url: str) -> str:
    parsed = urlparse(base_url)
    val = path if path.startswith("/") else "/" + path
    return urlunparse(parsed._replace(path=val, query="", fragment=""))


def clean_relative_import(source_url: str, rel_path: str) -> str:
    abs_url = urljoin(source_url, rel_path)
    clean = urlparse(abs_url)
    return urlunparse(clean._replace(query="", fragment=""))

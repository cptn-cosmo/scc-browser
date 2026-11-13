"""Async client for star-citizen-characters.com built on QNetworkAccessManager."""

from __future__ import annotations

import json
import re
from typing import Callable

from PySide6.QtCore import QObject, QStandardPaths, QUrl, QUrlQuery
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkDiskCache,
    QNetworkReply,
    QNetworkRequest,
)

SITE = "https://www.star-citizen-characters.com"
USER_AGENT = b"scc-browser/1.0 (Linux; Qt)"

ORDERS = [("latest", "LATEST"), ("like", "MOST LIKED"), ("download", "MOST DOWNLOADED")]


def character_page_url(head_id: str) -> str:
    return f"{SITE}/character/{head_id}"


def clean_search(text: str) -> str:
    # Same normalisation the website applies before querying.
    s = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s\s+", " ", s).strip()


class Api(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.nam = QNetworkAccessManager(self)
        cache = QNetworkDiskCache(self)
        cache_dir = QStandardPaths.writableLocation(QStandardPaths.CacheLocation)
        cache.setCacheDirectory(f"{cache_dir}/http")
        cache.setMaximumCacheSize(300 * 1024 * 1024)
        self.nam.setCache(cache)
        self._pix: dict[str, QPixmap] = {}
        self._pix_waiting: dict[str, list[Callable]] = {}

    def _request(self, url: str, cacheable=False) -> QNetworkRequest:
        req = QNetworkRequest(QUrl(url))
        req.setHeader(QNetworkRequest.UserAgentHeader, USER_AGENT)
        req.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute,
            QNetworkRequest.NoLessSafeRedirectPolicy,
        )
        req.setTransferTimeout(30000)
        if cacheable:
            req.setAttribute(
                QNetworkRequest.CacheLoadControlAttribute, QNetworkRequest.PreferCache
            )
        return req

    @staticmethod
    def _finish(reply: QNetworkReply, cb: Callable[[bytes | None, str | None], None]):
        def done():
            if reply.error() != QNetworkReply.NoError:
                cb(None, reply.errorString())
            else:
                cb(bytes(reply.readAll().data()), None)
            reply.deleteLater()
        reply.finished.connect(done)
        return reply

    # -- endpoints --------------------------------------------------------
    def fetch_heads(self, page: int, search: str, order: str, cb) -> QNetworkReply:
        """cb(body_dict | None, error | None); body = {rows, hasNextPage, hasPrevPage}."""
        q = QUrlQuery()
        q.addQueryItem("page", str(page))
        s = clean_search(search)
        if s:
            q.addQueryItem("search", s)
        q.addQueryItem("orderBy", order)
        url = QUrl(f"{SITE}/api/heads")
        url.setQuery(q)

        def parsed(data, err):
            if err:
                return cb(None, err)
            try:
                cb(json.loads(data)["body"], None)
            except (ValueError, KeyError, TypeError) as e:
                cb(None, f"Unexpected response from site: {e}")

        return self._finish(self.nam.get(self._request(url.toString())), parsed)

    def fetch_bytes(self, url: str, cb) -> QNetworkReply:
        return self._finish(self.nam.get(self._request(url)), cb)

    def report_download(self, head_id: str):
        """Bump the site's download counter, like the website's own button does."""
        req = self._request(f"{SITE}/api/head/download")
        req.setHeader(QNetworkRequest.ContentTypeHeader, "application/json")
        reply = self.nam.post(req, json.dumps({"characterId": head_id}).encode())
        reply.finished.connect(reply.deleteLater)

    def pixmap(self, url: str, cb: Callable[[QPixmap], None]):
        """Load an image (memory + disk cached). cb is called with a QPixmap."""
        if not url:
            return
        if url in self._pix:
            cb(self._pix[url])
            return
        waiting = self._pix_waiting.setdefault(url, [])
        waiting.append(cb)
        if len(waiting) > 1:
            return

        def done(data, err):
            pm = QPixmap()
            if data:
                pm.loadFromData(data)
            if not pm.isNull():
                self._pix[url] = pm
            for fn in self._pix_waiting.pop(url, []):
                try:
                    fn(pm)
                except RuntimeError:
                    pass  # receiving widget already deleted
        self._finish(self.nam.get(self._request(url, cacheable=True)), done)

#!/usr/bin/env python3
import argparse
import json
import re
import time
from html import unescape
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter, Retry


FAQ_SOURCE_URL_DEFAULT = "https://api.grucode.dev/api/site/frequently_asked_questions/"
UPLOAD_URL_DEFAULT = "https://ai.grucode.dev/api/v1/documents/upload_direct"


# ---------------------------
# Helpers
# ---------------------------

def mk_session(timeout: int = 15, retries: int = 4, backoff: float = 0.5) -> requests.Session:
    sess = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    sess.mount("http://", adapter)
    sess.mount("https://", adapter)
    sess.request_timeout = timeout
    return sess


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(html: Optional[str]) -> str:
    if not html:
        return ""
    text = unescape(_TAG_RE.sub(" ", html))
    text = _WS_RE.sub(" ", text).strip()
    return text


def to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v == 1 or v is True
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "y")


def parse_keywords(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    # Handle cases like "['a','b']" or "a, b , c"
    s = s.strip("[]")
    parts = [p.strip(" '\"") for p in s.split(",")]
    return [p for p in parts if p]


def safe_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


def build_document_text(question: str, answer_text: str) -> str:
    # Keep it simple and LLM-friendly
    return f"Q: {question}\nA: {answer_text}"


def build_metadata(record: Dict[str, Any], locale: str) -> Dict[str, Any]:
    return {
        "faq_id": record.get("_id"),
        "approval_status": record.get("approval_status") or record.get("status"),
        "created_by": record.get("created_by"),
        "created_by_id": record.get("created_by_id"),
        "created_at_ts": record.get("created_at_ts"),
        "approved_by": record.get("approved_by"),
        "approved_by_id": record.get("approved_by_id"),
        "approved_at_ts": record.get("approved_at_ts"),
        "updated_by": record.get("updated_by"),
        "updated_at_ts": record.get("updated_at_ts"),
        "rank": safe_float(record.get("rank")),
        "keywords": parse_keywords(record.get("keywords")),
        "related": record.get("related"),
        "source_table": "frequently_asked_questions",
        "locale": locale,
        "active": to_bool(record.get("active")),
        "deleted": to_bool(record.get("deleted")),
    }


def should_ingest(record: Dict[str, Any]) -> bool:
    active = to_bool(record.get("active"))
   
    return active


# ---------------------------
# Core
# ---------------------------

def fetch_faqs(sess: requests.Session, url: str) -> List[Dict[str, Any]]:
    resp = sess.get(url, timeout=sess.request_timeout)
    if not resp.ok:
        raise RuntimeError(f"FAQ fetch failed: {resp.status_code} {resp.text[:200]}")
    try:
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"FAQ fetch not JSON: {e}\n{resp.text[:200]}")
    # Accept either direct list or wrapped in {result_data: [...]}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "result_data" in data and isinstance(data["result_data"], list):
            return data["result_data"]
        # Some APIs use "data"
        if "data" in data and isinstance(data["data"], list):
            return data["data"]
    raise RuntimeError("FAQ payload format not recognized.")


def upload_doc(
    sess: requests.Session,
    upload_url: str,
    content: str,
    filename: str,
    metadata: Dict[str, Any],
    doc_type: str = "text",
    source: str = "faq_db",
    language: str = "en",
    chunking: bool = False,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    summarize: bool = False,
) -> Dict[str, Any]:
    payload = {
        "content": content,
        "doc_type": doc_type,
        "metadata": json.dumps(metadata),  # MUST be a JSON object, not a string
        "filename": filename,
        "source": source,
        "language": language,
        "summarize": summarize,
        "chunking": chunking,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    resp = sess.post(upload_url, headers=headers, data=json.dumps(payload), timeout=sess.request_timeout)
    if not resp.ok:
        raise RuntimeError(f"Upload failed ({filename}): {resp.status_code} {resp.text[:200]}")
    try:
        return resp.json()
    except Exception:
        return {"raw_text": resp.text}


def run(
    source_url: str,
    upload_url: str,
    locale: str,
    language: str,
    chunking: bool,
    chunk_size: int,
    chunk_overlap: int,
    summarize: bool,
    dry_run: bool,
    max_docs: Optional[int],
    sleep_ms: int,
):
    sess = mk_session()
    faqs = fetch_faqs(sess, source_url)

    total = len(faqs)
    ingested = 0
    skipped = 0
    failed = 0

    for i, rec in enumerate(faqs, start=1):
        try:
            if not should_ingest(rec):
                skipped += 1
                continue

            q = (rec.get("question") or "").strip()
            a_html = rec.get("answer")
            a_text = strip_html(a_html) if a_html else (rec.get("answer_text") or "").strip()
            if not q or not a_text:
                skipped += 1
                continue

            content = build_document_text(q, a_text)
            meta = build_metadata(rec, locale=locale)

            filename = f"faq_{rec.get('_id','unknown')}.txt"

            if dry_run:
                print(f"[DRY-RUN] Would upload: id={rec.get('_id')} len={len(content)} locale={locale}")
            else:
                _ = upload_doc(
                    sess=sess,
                    upload_url=upload_url,
                    content=content,
                    filename=filename,
                    metadata=meta,
                    doc_type="text",
                    source="faq_db",
                    language=language,
                    chunking=chunking,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    summarize=summarize,
                )
                # You can log/inspect response if needed:
                # print(json.dumps(resp, indent=2))
                ingested += 1

            if max_docs and ingested >= max_docs:
                break

            if sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)

        except Exception as e:
            failed += 1
            print(f"[ERROR] id={rec.get('_id')} :: {e}")

    print("\n=== Summary ===")
    print(f"Total fetched : {total}")
    print(f"Ingested     : {ingested}")
    print(f"Skipped      : {skipped}")
    print(f"Failed       : {failed}")


# ---------------------------
# CLI
# ---------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load FAQs into AI Localize (upload_direct).")
    parser.add_argument("--source-url", default=FAQ_SOURCE_URL_DEFAULT, help="FAQ API endpoint")
    parser.add_argument("--upload-url", default=UPLOAD_URL_DEFAULT, help="Upload endpoint")
    parser.add_argument("--locale", default="en_ZA", help="Locale tag to store in metadata")
    parser.add_argument("--language", default="en", help="Document language")
    parser.add_argument("--chunking", action="store_true", help="Enable chunking on upload")
    parser.add_argument("--chunk-size", type=int, default=400, help="Chunk size if chunking")
    parser.add_argument("--chunk-overlap", type=int, default=40, help="Chunk overlap if chunking")
    parser.add_argument("--summarize", action="store_true", help="Ask service to summarize after upload")
    parser.add_argument("--dry-run", action="store_true", help="Do not upload, just show what would happen")
    parser.add_argument("--max-docs", type=int, default=None, help="Stop after N successful uploads")
    parser.add_argument("--sleep-ms", type=int, default=0, help="Sleep between uploads (ms)")
    args = parser.parse_args()

    run(
        source_url=args.source_url,
        upload_url=args.upload_url,
        locale=args.locale,
        language=args.language,
        chunking=args.chunking,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        summarize=args.summarize,
        dry_run=args.dry_run,
        max_docs=args.max_docs,
        sleep_ms=args.sleep_ms,
    )

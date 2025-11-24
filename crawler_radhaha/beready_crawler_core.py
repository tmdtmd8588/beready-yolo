# -*- coding: utf-8 -*-
import re
import sqlite3
import os  # ✅ 추가
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

DB_PATH = "cafeteria.db"
# 이 파일은 serve.py와 같은 경로에 저장됨 #

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lilac_menu(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  day_text TEXT NOT NULL,
  menu TEXT NOT NULL,
  UNIQUE(day_text, menu)
);
"""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA busy_timeout=3000;")
    conn.commit()
    conn.close()

# ---------- upsert 추가 ----------
def upsert(items: List[tuple]) -> int:
    if not items:
        return 0
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    added = 0
    for day, menu in items:
        cur.execute(
            "INSERT OR IGNORE INTO lilac_menu(day_text, menu) VALUES (?, ?)",
            (day, menu),
        )
        if cur.rowcount:
            added += 1
    conn.commit()
    conn.close()
    return added

# ✅ MongoDB 또는 SQLite에서 데이터를 가져오는 공통 함수 추가
def _fetch_rows() -> List[tuple]:
    """
    MongoDB가 설정되어 있다면 MongoDB에서,
    아니면 기존 SQLite에서 데이터를 가져온다.
    """
    if os.getenv("MONGODB_URI"):
        try:
            from crawler_radhaha.db import fetch_all  # db.py 안에 Mongo 용 fetch_all 있어야 함
            return fetch_all()
        except Exception as e:
            print("[WARN] MongoDB fetch 실패, SQLite로 fallback:", e)

    # 기본 SQLite 동작 유지
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT day_text, menu FROM lilac_menu")
    rows = cur.fetchall()
    conn.close()
    return rows

DATE_RE = re.compile(r"(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일")

def _label_to_date(label: str) -> Optional[datetime]:
    m = DATE_RE.search(label or "")
    if not m:
        return None
    month, day = int(m.group("m")), int(m.group("d"))
    today = datetime.today().date()
    candidates = [
        datetime(today.year - 1, month, day).date(),
        datetime(today.year,     month, day).date(),
        datetime(today.year + 1, month, day).date(),
    ]
    return datetime(min(candidates, key=lambda d: abs(d - today)).year, month, day)

def _week_window(d: datetime):
    monday = d - timedelta(days=d.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday

def get_latest_week_from_db() -> Dict:
    # ✅ 여기만 한 줄 변경 (SQLite → Mongo 지원)
    rows = _fetch_rows()

    if not rows:
        return {"week_start": None, "days": []}

    by_label: Dict[str, Dict] = {}
    for label, menu in rows:
        if label not in by_label:
            by_label[label] = {"date": _label_to_date(label), "menus": []}
        by_label[label]["menus"].append(menu)

    dated = [v["date"] for v in by_label.values() if v["date"]]
    if not dated:
        labels_sorted = sorted(by_label.keys())[-5:]
        return {
            "week_start": None,
            "days": [{"label": lb, "menus": by_label[lb]["menus"]} for lb in labels_sorted]
        }

    latest = max(dated)
    w_start, w_end = _week_window(latest)

    items = [(dt, lb, info["menus"]) for lb, info in by_label.items()
             if (dt := info["date"]) and w_start.date() <= dt.date() <= w_end.date()]
    items.sort(key=lambda x: x[0])

    return {
        "week_start": w_start.strftime("%Y-%m-%d"),
        "days": [{"date": d.strftime("%Y-%m-%d"), "label": lb, "menus": menus}
                 for d, lb, menus in items]
    }

# ---------- Pydantic Models ----------
class DayMenu(BaseModel):
    date: Optional[str]=None
    label: str
    menus: List[str]

class LatestWeekResponse(BaseModel):
    week_start: Optional[str]
    days: List[DayMenu]

# ---------- fastapi용 Router ----------
router = APIRouter()

@router.get("/api/lilac/menu/health", response_model=dict)
def health():
    return {"ok": True}

@router.get("/api/lilac/menu", response_model=LatestWeekResponse)
def api_latest_week():
    return get_latest_week_from_db()


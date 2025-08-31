# -*- coding: utf-8 -*-
# Created by rad-haha(absinthe6),안시은 ,2025
# Part of Team Project: [beready]
# License: MIT
"""
beready_crawler_core.py
- DB 스키마/저장/조회
- FastAPI: DB에서 최신 '주간(월~금)' 메뉴 JSON 반환
"""

import re
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 원 코드 그대로 유지
DB_PATH = "cafeteria.db"

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
    # 동시성 완화
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA busy_timeout=3000;")
    conn.commit()
    conn.close()

def upsert(items: List[tuple]) -> int:
    if not items:
        return 0
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    added = 0
    for day, menu in items:
        cur.execute("INSERT OR IGNORE INTO lilac_menu(day_text, menu) VALUES (?, ?)", (day, menu))
        if cur.rowcount:
            added += 1
    conn.commit()
    conn.close()
    return added

# ---------- 최신 주간(월~금) 조회 ----------
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
    best = min(candidates, key=lambda d: abs(d - today))
    return datetime(best.year, best.month, best.day)

def _week_window(d: datetime):
    monday = d - timedelta(days=d.weekday())  # 0=월
    friday = monday + timedelta(days=4)
    return monday, friday

def get_latest_week_from_db() -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT day_text, menu FROM lilac_menu")
    rows = cur.fetchall()
    conn.close()

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

    items = []
    for lb, info in by_label.items():
        dt = info["date"]
        if dt and w_start.date() <= dt.date() <= w_end.date():
            items.append((dt, lb, info["menus"]))
    items.sort(key=lambda x: x[0])

    return {
        "week_start": w_start.strftime("%Y-%m-%d"),
        "days": [{"date": d.strftime("%Y-%m-%d"), "label": lb, "menus": menus}
                 for d, lb, menus in items]
    }

# ---------- FastAPI ----------
app = FastAPI(title="PKNU Lilac Menu API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"ok": True, "db": DB_PATH}

@app.get("/api/menus/latest")
def api_latest_week():
    return get_latest_week_from_db()

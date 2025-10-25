# -*- coding: utf-8 -*-
# Created by rad-haha(absinthe6),안시은 ,2025
# Part of Team Project: [beready]
# License: MIT

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

# ✅ DB 관리 통합 (SQLite → PostgreSQL 확장)
from db import init_db, upsert, engine

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
    # ✅ 여기만 SQLAlchemy 방식으로 교체
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT day_text, menu FROM lilac_menu")).all()

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
    date: Optional[str] = None
    label: str
    menus: List[str]

class LatestWeekResponse(BaseModel):
    week_start: Optional[str]
    days: List[DayMenu]

# ---------- FastAPI Router ----------
router = APIRouter(prefix="/api/lilac/menu", tags=["Lilac"])

@router.get("/health", response_model=dict)
def health():
    # ✅ DB_PATH 제거 → 간단한 OK 응답으로 변경
    return {"ok": True}

@router.get("/", response_model=LatestWeekResponse)
def api_latest_week():
    return get_latest_week_from_db()

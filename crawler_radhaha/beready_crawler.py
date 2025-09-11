# -*- coding: utf-8 -*-
# Created by rad-haha(absinthe6),안시은 ,2025
# Part of Team Project: [beready]
# License: MIT
"""
beready_crawler.py
- PKNU 라일락 주간식단표 크롤러
- 목록에서 최신 글 → 상세 표에서 '중식' 5일치 파싱 → core.upsert로 DB 저장
"""

import re
from typing import List, Tuple, Optional, Dict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from core import init_db, upsert  # DB는 core 모듈 사용

LIST_URL = "https://www.pknu.ac.kr/main/399"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": LIST_URL,
    "Accept-Language": "ko,en;q=0.9",
    "Cache-Control": "no-cache",
}

# ---------------- HTTP ----------------
def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or r.encoding
    return r.text

# ------------- 목록 → 최신 글 URL -------------
def find_latest_view_url(list_html: str, base_url: str) -> Optional[str]:
    soup = BeautifulSoup(list_html, "html.parser")
    a = soup.select_one("td.title a[href*='action=view']")
    if a and a.get("href"):
        return urljoin(base_url, a["href"])
    a = soup.select_one("table a[href*='action=view']")
    if a and a.get("href"):
        return urljoin(base_url, a["href"])
    a = soup.select_one("a[href*='action=view']")
    if a and a.get("href"):
        return urljoin(base_url, a["href"])
    return None

# ------------- 상세: 라일락 표 찾기 -------------
WEEK_EN  = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday"}
DATE_PAT = re.compile(r"\d{1,2}\s*월\s*\d{1,2}\s*일")

def find_lilac_table(view_html: str) -> Optional[Tag]:
    soup = BeautifulSoup(view_html, "html.parser")
    t = soup.select_one("table.con03_sub_2")
    if t:
        return t
    for table in soup.find_all("table"):
        first_tr = table.find("tr")
        if not first_tr:
            continue
        first_text = first_tr.get_text(" ", strip=True)
        if any(w in first_text for w in WEEK_EN) or DATE_PAT.search(first_text):
            return table
    return soup.find("table")

# ------------- 유틸 -------------
def cell_text(el: Optional[Tag]) -> str:
    if not el:
        return ""
    return el.get_text("\n", strip=True).replace("\r", "")

def squash_slash(lines: List[str]) -> List[str]:
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        cur = lines[i]
        if cur == "/" and out and i + 1 < n:
            out[-1] = f"{out[-1]}/{lines[i+1]}"
            i += 2
            continue
        out.append(cur)
        i += 1
    return out

def pick_5_header(cells: List[Tag]) -> List[Tag]:
    picked = []
    for c in cells:
        tx = cell_text(c)
        if not tx or "구분" in tx or "운영정보" in tx:
            continue
        picked.append(c)
        if len(picked) == 5:
            break
    return picked

def pick_5_dates(cells: List[Tag]) -> List[Tag]:
    cleaned = [c for c in cells if "운영정보" not in cell_text(c)]
    return cleaned[:5]

# ------------- 표 파싱 (중식 5일) -------------
def parse_lunch_from_table(table: Tag) -> List[Tuple[str, str]]:
    rows_out: List[Tuple[str, str]] = []
    trs = table.find_all("tr")
    if len(trs) < 3:
        return rows_out

    h1 = trs[0].find_all(["th", "td"])
    h2 = trs[1].find_all(["th", "td"])

    day_cells  = pick_5_header(h1)
    date_cells = pick_5_dates(h2)

    labels: List[str] = []
    for i in range(5):
        d_txt = cell_text(date_cells[i]) if i < len(date_cells) else ""
        w_txt = cell_text(day_cells[i])  if i < len(day_cells)  else ""
        if d_txt and w_txt and w_txt not in d_txt:
            labels.append(f"{d_txt} ({w_txt})")
        elif d_txt:
            labels.append(d_txt)
        elif w_txt:
            labels.append(w_txt)
        else:
            labels.append(f"Day{i+1}")

    lunch_tr = None
    for tr in trs[2:]:
        first_two = tr.find_all(["th", "td"])[:2]
        left_text = " ".join(cell_text(c) for c in first_two)
        if "중식" in left_text:
            lunch_tr = tr
            break
    if not lunch_tr:
        lunch_tr = trs[2]

    tds = lunch_tr.find_all(["th", "td"])
    skip = 0
    for i, c in enumerate(tds[:2]):
        if "구분" in cell_text(c) or "중식" in cell_text(c):
            skip = i + 1
    if skip == 0:
        skip = 1
    candidates = [c for c in tds[skip:] if "운영정보" not in cell_text(c)]
    menu_cells = candidates[:5]

    ban_words = ("운영", "문의", "전화", "Open", "Close")
    for i, cell in enumerate(menu_cells):
        day = labels[i] if i < len(labels) else f"Day{i+1}"
        raw = cell_text(cell)
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
        lines = [ln for ln in lines if not any(b in ln for b in ban_words)]
        lines = squash_slash(lines)
        for dish in lines:
            rows_out.append((day, dish))

    return rows_out

# ------------- 1회 크롤링 실행 -------------
def crawl_once() -> int:
    """
    목록 → 최신 글 → 상세 표에서 '중식' 5일치 파싱 → DB 저장
    반환값: 새로 추가된 row 수
    """
    init_db()
    list_html = fetch_html(LIST_URL)
    view_url = find_latest_view_url(list_html, LIST_URL)
    if not view_url:
        print("[ERROR] 최신 글 링크를 못 찾았어.")
        return 0

    view_html = fetch_html(view_url)
    table = find_lilac_table(view_html)
    if not table:
        print("[ERROR] 라일락 표를 못 찾았어.")
        return 0

    items = parse_lunch_from_table(table)
    added = upsert(items)
    print(f"[DONE] TOTAL added: {added}")

    # 디버그 출력(선택)
    grouped: Dict[str, List[str]] = {}
    for d, m in items:
        grouped.setdefault(d, []).append(m)
    for d in grouped:
        print(f"{d}:")
        print(" - " + " · ".join(grouped[d]))
        print()

    return added

if __name__ == "__main__":
    crawl_once()

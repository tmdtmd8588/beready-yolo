# db.py (루트)
import os
from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError

MONGODB_URI = os.getenv("MONGODB_URI")
DBNAME = os.getenv("MONGODB_DBNAME", "beready")
COLL = os.getenv("MONGODB_COLL", "lilac_menu")

_client = MongoClient(MONGODB_URI)
_db = _client[DBNAME]
_col = _db[COLL]

def init_db():
    # day_text+menu 유니크
    _col.create_index([("day_text", 1), ("menu", 1)], unique=True)

def upsert(items):
    if not items:
        return 0
    ops = [
        UpdateOne(
            {"day_text": d, "menu": m},
            {"$setOnInsert": {"day_text": d, "menu": m}},
            upsert=True
        )
        for d, m in items
    ]
    try:
        res = _col.bulk_write(ops, ordered=False)
        return len(res.upserted_ids) if res.upserted_ids else 0
    except BulkWriteError as e:
        # 중복 충돌은 무시하고 upsert된 건수만 추출
        return len((e.details or {}).get("upserted", []) or [])

def fetch_all():
    # [(day_text, menu), ...] 형태로 반환
    return [(doc.get("day_text",""), doc.get("menu",""))
            for doc in _col.find({}, {"_id":0, "day_text":1, "menu":1})]

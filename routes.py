from fastapi import APIRouter
from globals import person_count, wait_time, person_count_lock

router = APIRouter()

@router.get("/api/estimate/lilac")
def get_lilac():
    with person_count_lock:
        return {"people": person_count, "wait_time": wait_time}

@router.get("/api/estimate/dalelac/korea")
def get_dalelac_korea():
    with person_count_lock:
        return {"people": person_count, "wait_time": wait_time}

@router.get("/api/estimate/dalelac/japan")
def get_dalelac_japan():
    with person_count_lock:
        return {"people": person_count, "wait_time": wait_time}

@router.get("/api/estimate/dalelac/specialty")
def get_dalelac_specialty():
    with person_count_lock:
        return {"people": person_count, "wait_time": wait_time}

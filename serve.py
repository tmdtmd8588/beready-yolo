from fastapi import FastAPI
from crawler_radhaha.beready_crawler_core import router as lilacdiet_router
from main_yolo2 import router as yolo_router

app = FastAPI(title="Beready API (YOLO + LilacDiet)")

# 라우터 합치기: 두 모듈을 하나로 합쳐 서버에 띄우기
app.include_router(lilacdiet_router)
app.include_router(yolo_router)

# fastapi 서버 헬스 체크용
@app.get("/healthz")
def healthz():
    return {"ok": True}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading
import uvicorn

# 모듈 import
from crawler_radhaha import beready_crawler_core, beready_crawler
from crawler_radhaha.beready_crawler import crawl_once
from yolo.main_yolo import router as yolo_router, start_yolo_threads

from db import init_db
# db 추가

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(beready_crawler_core.router)
app.include_router(yolo_router)

@app.on_event("startup")
def startup_event():
    def delayed_start():
        time.sleep(1)
        print("[INFO] YOLO thread starting...")
        try:
            start_yolo_threads()
        except Exception as e:
            print(f"[ERROR] YOLO thread failed: {e}")

    threading.Thread(target=delayed_start, daemon=True).start()
    
@app.get("/trigger")
def trigger_crawl():
    added = crawl_once()
    return {"added": added}
    
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)







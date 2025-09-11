from fastapi import FastAPI

# 각각의 앱 import
from main_yolo2 import app as yolo_app
from crawler_radhaha.beready_crawler_core import app as lilac_app

app = FastAPI(title="BeReady Unified API")

# mount (서브앱으로 붙이기)
app.mount("/yolo", yolo_app)
app.mount("/lilac", lilac_app)

@app.get("/healthz")
def healthz():
    return {"ok": True}

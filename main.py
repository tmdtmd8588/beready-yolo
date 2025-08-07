import warnings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading
import uvicorn

from detection import detect_people, calculate_wait_time
from routes import router

warnings.filterwarnings("ignore", category=FutureWarning)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.on_event("startup")
def startup_event():
    threading.Thread(target=detect_people, daemon=True).start()
    threading.Thread(target=calculate_wait_time, daemon=True).start()

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)

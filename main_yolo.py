import threading # 사람 탐지 로직을 백그라운드에서 실행
import cv2 # OpenCV, 비디오 프레임 읽고 시각화에 사용
import warnings 
from fastapi import FastAPI # REST API 서버 프레임워크
import uvicorn # FastAPI 앱을 실행하기 위한 ASGI 서버
from ultralytics import YOLO  # YOLOv8 객체 탐지 모델
from fastapi.middleware.cors import CORSMiddleware 
import time

warnings.filterwarnings("ignore", category=FutureWarning)

app = FastAPI() # FastAPI 객체 생성

app.add_middleware( # CORS (Cross-Origin Resource Sharing) 문제 해결을 위한 미들웨어 추가, 클라이언트가 다른 도메인에서 이 API에 요청할 수 있도록 허용
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인에서 요청 허용 (보안상 실 서비스에선 특정 도메인만 허용하는 것이 좋음) ["http://localhost:포트번호"]로 제한 가능
    allow_credentials=True, # 쿠키, 인증 정보 등을 포함한 요청 허용
    allow_methods=["*"], # GET, POST, PUT 등 모든 메서드 허용
    allow_headers=["*"], # 모든 헤더 허용
)

person_count = 0 # 감지된 사람 수를 저장하는 전역 변수
average_counts = []  # 평균 계산용 리스트
wait_time = 0  # 예상 대기 시간 (분)

PERSON_CLASS_ID = 0  # YOLOv8 모델에서 ID: 0번이 사람
person_count_lock = threading.Lock() # threading.Lock 사용

model = YOLO("yolov8n.pt")  # YOLOv8 모델 로드
video_path = "http://172.30.1.81:8080/video"
#video_path = "http://172.30.1.30:8080/video" # 감지할 비디오 파일 경로
cap = cv2.VideoCapture(video_path) # OpenCV의 VideoCapture 객체를 생성

def detect_people(): # 사람 탐지 함수
    global person_count
    while True: # 무한 루프 시작
        ret, frame = cap.read() # cap.read()로 영상에서 프레임을 하나씩 읽음
        if not ret: # ret == False이면 루프 종료
            break

        frame = cv2.resize(frame, (640, 360)) # YOLO 처리 속도 향상을 위해 프레임을 640x360으로 리사이즈
        results = model(frame, verbose=False)[0] # 프레임을 YOLO 모델에 입력하고, 첫 번째 결과 ([0])를 가져옴

        person_detections = [box for box in results.boxes if int(box.cls[0]) == PERSON_CLASS_ID] # cls[0] == 0인 객체만 필터링, 사람 클래스만 감지

        with person_count_lock: # 사람 수 변경 시
            person_count = len(person_detections)
            current_wait_time = wait_time #임시로 예상대기시간도 표시하기위해 추가

        for box in person_detections: # 박스 그리기
            x1, y1, x2, y2 = map(int, box.xyxy[0]) # 경계 상자 좌표
            conf = float(box.conf[0]) # 신뢰도(확률)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2) # 프레임에 초록색 박스를 그림
            cv2.putText(frame, f'Person {conf:.2f}', (x1, y1 - 10), # 프레임에 라벨을 그림
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        cv2.putText(frame, f'People: {person_count}', (10, 30), # 현재 감지된 사람 수를 좌상단에 표시
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        
        # 예상 대기 시간 표시
        cv2.putText(frame, f'Wait Time: {current_wait_time} min', (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        cv2.imshow('YOLOv8 Person Detection', frame) # 프레임을 실시간으로 화면에 표시
        if cv2.waitKey(1) & 0xFF == 27:  # 사용자가 ESC키를 누르면 루프 종료
            break

    cap.release() # cap 객체가 사용하던 영상 스트림을 종료
    cv2.destroyAllWindows() # OpenCV가 생성한 모든 창(윈도우)을 닫음

def calculate_wait_time():
    global wait_time
    while True:
        for _ in range(6):
            with person_count_lock:
                average_counts.append(person_count)
            time.sleep(10)

        avg = sum(average_counts) / len(average_counts)
        wait_time = int(avg * 2)  # 1명당 2분 소요로 가정

        average_counts.clear()

@app.get("/api/count") # FastAPI의 데코레이터로, "/api/count" 경로에 대해 GET 요청을 처리하도록 지정
def get_count(): # API 요청이 들어올 때 실행될 핸들러 함수 # API 호출 시
    with person_count_lock:
        return {"count": person_count, "wait_time": wait_time}

@app.on_event("startup") # FastAPI 서버가 실행될 때 한 번 실행되는 이벤트
def startup_event(): # 메인 스레드를 차단하지 않고 사람 감지를 비동기 처리
    threading.Thread(target=detect_people, daemon=True).start()
    threading.Thread(target=calculate_wait_time, daemon=True).start()

if __name__ == "__main__": # 현재 스크립트가 직접 실행될 때만 내부 코드를 실행
    uvicorn.run("main_yolo:app", reload=True) # FastAPI 서버를 실행하는 명령
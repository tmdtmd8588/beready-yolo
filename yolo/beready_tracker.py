import cv2
from ultralytics import YOLO
import numpy as np
import time
from tracker.byte_tracker import BYTETracker # ByteTrack 불러오기
import threading

# ----------------- 설정 -----------------
VIDEO_PATH = "people.mp4" # 카메라 URL 또는 파일 경로
MODEL_PATH = "yolov8n.pt" # YOLO 모델 파일 경로
detect_interval = 1 # 몇 프레임마다 detection 실행할지(1이면 매 프레임)
conf_threshold = 0.2 # 검출 신뢰도 임계값
scale = 0.5 # 화면 표시 시 축소 비율(성능/표시용)
max_missed = 150  # 150프레임 미검출 시 사라진 것으로 간주
# ----------------------------------------

# 전역 변수
wait = 20.0
current_people_count = 0
running = False

# 외부에서 wait 값을 가져갈 때 사용
def get_wait():
    return wait

# 별도 스레드에서 실행할 추적 루프
def start_tracker():
    global wait, current_people_count, running

    if running:
        print("[INFO] Tracker already running.")
        return
    running = True

    # np.float 호환성 처리
    if not hasattr(np, "float"):
        np.float = float

    cap = cv2.VideoCapture(VIDEO_PATH) # cap으로 비디오 스트림 열기
    if not cap.isOpened():
        print(f"[ERROR] Cannot open video: {VIDEO_PATH}")
        running = False
        return


         
    print("Camera opened:", cap.isOpened()) # cap.isOpened()로 성공 여부 확인 가능
    model = YOLO(MODEL_PATH)  # model로 YOLOv8 로드

    # ByteTrack 초기 설정값
    class Args:
        track_thresh = 0.5
        track_buffer = 30
        match_thresh = 0.8
        aspect_ratio_thresh = 3.0
        min_box_area = 10
        mot20 = False

    tracker = BYTETracker(Args()) # ByteTrack 객체 생성

    frame_count = 0 # 프레임 번호
    target_id = None # 현재 추적중인 대상id (없으면 None)
    meta = {}  
    # 각 추적 ID별 메타데이터(처음 본 시각, 마지막으로 본 프레임, 연속 미검출 횟수) # {id: {"first_seen":ts, "last_seen_frame":n, "missed":k}}

    while running:
        ret, frame = cap.read() # cap.read()로 영상에서 프레임을 하나씩 읽음
        if not ret: # 영상이 끝났거나 읽기 실패 시 종료
            print("Frame read failed. Stopping.")
            break

        frame_count += 1  # 현재까지 읽은 영상 프레임(장면)의 개수를 세는 카운터 변수
        h, w = frame.shape[:2]  # h,w는 영상 높이/너비 (트래커 업데이트에 사용)
        detections = []

        # -------- YOLO 감지 ----------
        if frame_count % detect_interval == 0:
            results = model(frame, conf=conf_threshold, verbose=False)[0] # 프레임을 YOLO 모델에 입력, YOLO 모델을 이용한 객체 감지 수행
            for box in results.boxes: # 각 객체의 경계박스 좌표와 클래스, 신뢰도 추출
                xyxy = box.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy[:4])
                score = float(box.conf[0])
                cls = int(box.cls[0])
                if cls == 0 and score >= conf_threshold:
                    detections.append([x1, y1, x2, y2, score])

            # ByteTrack 입력 형식에 맞게 NumPy 배열 변환
            detections = np.array(detections, dtype=np.float32) if detections else np.empty((0, 5), dtype=np.float32)

            # ByteTrack으로 추적 업데이트 (새로운/기존 트랙 갱신)
            online_targets = tracker.update(detections, [h, w], [h, w])
        else:
            online_targets = []

        # -------- tracks 처리 ----------
        present_ids = set() # 현재 프레임에서 감지된 추적 ID 집합
        tracks = [] # 시각화 및 ‘맨 뒤 선택’에 사용할 [x1,y1,x2,y2,track_id] 리스트

        for t in online_targets:
            track_id = t.track_id
            tlwh = t.tlwh # [x, y, w, h] 형식의 바운딩박스
            x1, y1, w_box, h_box = map(int, tlwh)
            x2, y2 = x1 + w_box, y1 + h_box
            tracks.append([x1, y1, x2, y2, track_id])
            present_ids.add(track_id)

            # 메타데이터 갱신
            if track_id not in meta: # 처음 등장한 ID는 첫 시각과 프레임 저장
                meta[track_id] = {"first_seen": time.time(), "last_seen_frame": frame_count, "missed": 0}
            else:  # 이미 존재하면 last_seen_frame을 갱신하고 missed를 0으로 초기화
                meta[track_id]["last_seen_frame"] = frame_count
                meta[track_id]["missed"] = 0

        # 부재(ID 미검출) 처리
        for pid in meta.keys():
            if pid not in present_ids:
                meta[pid]["missed"] += 1  # 현재 프레임에 존재하지 않은 ID는 연속 미검출 횟수(missed)를 1 증가

        # 사라진 타겟 처리
        if target_id is not None and target_id in meta and meta[target_id]["missed"] >= max_missed:  # 현재 타겟이 있고 missed가 max_missed(여기선 20) 이상이면
            disappear_ts = time.time()
            wait_time = disappear_ts - meta[target_id]["first_seen"]  # 대상이 완전히 사라진 것으로 보고 대기시간 계산(현재 시각 − first_seen)
            wait = wait_time / current_people_count if current_people_count > 0 else wait_time
            print(f"[INFO] 대상 {target_id} 사라짐 → 대기시간 {wait_time:.2f}초, wait {wait:.2f}초")
            del meta[target_id]  # 사라진 사람의 meta 삭제
            target_id = None  # target_id를 해제

        # 타겟이 아닌 오래된 ID 삭제 (누적 방지)
        for pid in list(meta.keys()):
            if meta[pid]["missed"] >= max_missed:
                del meta[pid]

        # 새로운 타겟 선택
        if target_id is None and tracks: # 타겟이 없다면 중심 x 좌표가 가장 작은(왼쪽) 사람을 선택하여 target_id로 고정
            leftmost = min(tracks, key=lambda t: (t[0] + t[2]) / 2)
            target_id = leftmost[4]
            current_people_count = len(tracks)  # 현재 프레임에 보이는 사람 수 저장
            if meta[target_id]["first_seen"] is None:
                meta[target_id]["first_seen"] = time.time()
            print(f"[INFO] 새로운 대상 선택: ID={target_id}, 현재 인원수={current_people_count}")
        """
        # 시각화
        for x1, y1, x2, y2, tid in tracks:
            color = (0, 0, 255) if tid == target_id else (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"ID {tid}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.imshow("Queue Tracker", cv2.resize(frame, (0, 0), fx=scale, fy=scale))
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break
        """

    cap.release()
    #cv2.destroyAllWindows()
    running = False
    print("[INFO] Tracker stopped.")


#FastAPI startup 이벤트용
def start_tracker_thread():
    t = threading.Thread(target=start_tracker, daemon=True)
    t.start()





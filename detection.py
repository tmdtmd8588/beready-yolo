import time
import cv2
from ultralytics import YOLO
from globals import person_count, average_counts, wait_time, PERSON_CLASS_ID, person_count_lock

model = YOLO("yolov8n.pt")
video_path = "http://172.30.1.30:8080/video"
cap = cv2.VideoCapture(video_path)

def detect_people():
    global person_count, wait_time
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (640, 360))
        results = model(frame, verbose=False)[0]

        person_detections = [box for box in results.boxes if int(box.cls[0]) == PERSON_CLASS_ID]

        with person_count_lock:
            person_count = len(person_detections)
            current_wait_time = wait_time

        for box in person_detections:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            conf = float(box.conf[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f'Person {conf:.2f}', (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        cv2.putText(frame, f'People: {person_count}', (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame, f'Wait Time: {current_wait_time} min', (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        cv2.imshow('YOLOv8 Person Detection', frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

def calculate_wait_time():
    global wait_time
    while True:
        for _ in range(6):
            with person_count_lock:
                average_counts.append(person_count)
            time.sleep(10)

        avg = sum(average_counts) / len(average_counts)
        wait_time = int(avg * 2)
        average_counts.clear()

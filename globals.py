import threading

person_count = 0
average_counts = []
wait_time = 0

PERSON_CLASS_ID = 0
person_count_lock = threading.Lock()

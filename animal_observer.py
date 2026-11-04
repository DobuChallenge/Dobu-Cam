"""Adapter for petObserver's detector; inference never blocks live video."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'petObserver' / 'petObserver'))
from detector_alimentacao_cachorro import Deteccao, YOLO


class AnimalObserver:
    def __init__(self, model, confidence=0.5):
        import torch
        torch.set_num_threads(2)
        self.model = YOLO(model)
        self.confidence = confidence
        self.condition = threading.Condition()
        self.pending = None
        self.result = (0, 0, [])
        self.error = None
        threading.Thread(target=self._run, daemon=True).start()

    def submit(self, frame):
        with self.condition:
            self.pending = frame.copy()
            self.condition.notify()

    def snapshot(self):
        with self.condition:
            return self.result

    def _run(self):
        sequence = 0
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.pending is not None)
                frame, self.pending = self.pending, None
            try:
                result = self.model.predict(frame, conf=self.confidence, imgsz=640, verbose=False)[0]
                detections = []
                for box in result.boxes:
                    name = self.model.names[int(box.cls[0])]
                    if name in ('dog', 'cat'):
                        detections.append(Deteccao(name, float(box.conf[0]), *map(float, box.xyxy[0])))
                sequence += 1
                with self.condition:
                    self.result = (sequence, time.monotonic(), detections)
                    self.error = None
            except Exception as exc:
                if self.error != str(exc):
                    print(f'Identificacao de animais indisponivel: {exc}', flush=True)
                self.error = str(exc)
                time.sleep(1)
            time.sleep(0.25)

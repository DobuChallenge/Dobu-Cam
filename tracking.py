"""Temporal evidence for presence; movement alone never confirms an animal."""
from collections import deque


class PresenceTracker:
    def __init__(self, hold_seconds=2.5):
        self.hold_seconds = hold_seconds
        self.reset()

    def reset(self):
        self.hits = deque(maxlen=3)
        self.last_seen = None
        self.animal = None
        self.present = False

    def update(self, animal, now, new_analysis=True):
        if new_analysis:
            self.hits.append(animal is not None)
            if animal is not None:
                self.animal = animal
                self.last_seen = now
            if sum(self.hits) >= 2:
                self.present = True
        if self.last_seen is None or now - self.last_seen > self.hold_seconds:
            self.present = False
            self.hits.clear()
            self.animal = None
        return self.present

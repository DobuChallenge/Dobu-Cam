import math


def valid_region(region):
    if not isinstance(region, dict):
        return False
    values = [region.get(key) for key in ('x', 'y', 'width', 'height')]
    if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in values):
        return False
    x, y, width, height = values
    return x >= 0 and y >= 0 and width > 0 and height > 0 and x + width <= 1.001 and y + height <= 1.001


class BowlMonitor:
    def __init__(self):
        self.reset()

    def reset(self):
        self.config = None
        self.items = {kind: {'since': None, 'last': None, 'counted': False, 'count': 0, 'last_event_at': None}
                      for kind in ('food', 'water')}

    def update(self, config, box, species, confidence, now, timestamp):
        if config != self.config:
            self.reset()
            self.config = {kind: config.get(kind) for kind in self.items}
        confirmed = species in ('cat', 'dog') and confidence >= 0.5 and valid_region(box)
        overlaps = {}
        for kind in self.items:
            region = config.get(kind)
            score = 0
            if confirmed and valid_region(region):
                width = max(0, min(box['x'] + box['width'], region['x'] + region['width']) - max(box['x'], region['x']))
                height = max(0, min(box['y'] + box['height'], region['y'] + region['height']) - max(box['y'], region['y']))
                score = width * height / (region['width'] * region['height'])
            overlaps[kind] = score
        ambiguous = sum(score >= .4 for score in overlaps.values()) > 1
        for kind, item in self.items.items():
            if item['last'] is not None and now - item['last'] > 4:
                item.update(since=None, last=None, counted=False)
            if ambiguous or overlaps[kind] < 0.4:
                continue
            if item['since'] is None:
                item['since'] = now
            item['last'] = now
            if not item['counted'] and now - item['since'] >= 4:
                item['count'] += 1
                item['counted'] = True
                item['last_event_at'] = timestamp

    def snapshot(self, config, now, online):
        return {kind: {
            'configured': valid_region(config.get(kind)),
            'active': bool(online and valid_region(config.get(kind)) and item['last'] is not None and now - item['last'] <= 4),
            'count': item['count'] if valid_region(config.get(kind)) else 0,
            'last_event_at': item['last_event_at'] if valid_region(config.get(kind)) else None,
        } for kind, item in self.items.items()}

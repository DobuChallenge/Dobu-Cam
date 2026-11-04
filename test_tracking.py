import unittest
from tracking import PresenceTracker


class PresenceTests(unittest.TestCase):
    def test_single_false_detection_does_not_confirm_presence(self):
        tracker = PresenceTracker()
        self.assertFalse(tracker.update(object(), 0))
        self.assertFalse(tracker.update(None, 0.5))
        self.assertFalse(tracker.update(None, 1))

    def test_two_positive_analyses_allow_short_occlusion(self):
        tracker = PresenceTracker()
        animal = object()
        self.assertFalse(tracker.update(animal, 0))
        self.assertFalse(tracker.update(None, 0.5))
        self.assertTrue(tracker.update(animal, 1))
        self.assertTrue(tracker.update(None, 2))
        self.assertIs(tracker.animal, animal)
        self.assertFalse(tracker.update(None, 4))

    def test_cached_result_is_not_an_independent_confirmation(self):
        tracker = PresenceTracker()
        animal = object()
        tracker.update(animal, 0)
        self.assertFalse(tracker.update(animal, 0.3, new_analysis=False))
        self.assertTrue(tracker.update(animal, 0.5))
        self.assertFalse(tracker.update(None, 4, new_analysis=False))

    def test_replay_reset_discards_previous_scene(self):
        tracker = PresenceTracker()
        tracker.update(object(), 0)
        tracker.update(object(), 0.5)
        tracker.reset()
        self.assertFalse(tracker.present)
        self.assertIsNone(tracker.animal)


if __name__ == '__main__':
    unittest.main()

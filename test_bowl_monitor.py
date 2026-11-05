import unittest
from bowl_monitor import BowlMonitor


class BowlMonitorTests(unittest.TestCase):
    def setUp(self):
        self.monitor = BowlMonitor()
        self.region = {'x': .1, 'y': .6, 'width': .2, 'height': .2}
        self.config = {'water': self.region, 'food': None}

    def update(self, time, box=None, species='cat'):
        self.monitor.update(self.config, box, species, .9, time, f'2026-11-04T10:00:{int(time):02d}')

    def test_no_regions_no_events(self):
        self.config = {'water': None, 'food': None}
        for time in range(10):
            self.update(time, self.region)
        self.assertEqual(self.monitor.snapshot(self.config, 9, True)['water']['count'], 0)

    def test_dwell_counts_once_and_new_visit_counts_again(self):
        for time in range(10):
            self.update(time, self.region)
        self.assertEqual(self.monitor.snapshot(self.config, 9, True)['water']['count'], 1)
        self.update(15)
        for time in range(16, 22):
            self.update(time, self.region)
        self.assertEqual(self.monitor.snapshot(self.config, 21, True)['water']['count'], 2)

    def test_person_missing_detection_and_short_visit_do_not_count(self):
        for time in range(10):
            self.update(time, self.region, 'person')
        self.update(11, self.region)
        self.update(12, self.region)
        self.update(18)
        self.assertEqual(self.monitor.snapshot(self.config, 18, True)['water']['count'], 0)

    def test_config_change_resets_counts_and_offline_is_not_active(self):
        for time in range(6):
            self.update(time, self.region)
        self.assertFalse(self.monitor.snapshot(self.config, 5, False)['water']['active'])
        self.config = {'water': None, 'food': self.region}
        self.update(6, self.region)
        self.assertEqual(self.monitor.snapshot(self.config, 6, True)['water']['count'], 0)
        self.assertEqual(self.monitor.snapshot(self.config, 6, True)['food']['count'], 0)

    def test_animal_covering_both_bowls_is_ambiguous(self):
        self.config = {'water': self.region, 'food': {'x': .5, 'y': .6, 'width': .2, 'height': .2}}
        for time in range(10):
            self.update(time, {'x': 0, 'y': 0, 'width': 1, 'height': 1})
        self.assertEqual(self.monitor.snapshot(self.config, 9, True)['water']['count'], 0)
        self.assertEqual(self.monitor.snapshot(self.config, 9, True)['food']['count'], 0)

    def test_backend_receives_live_boxes_and_exposes_separate_results(self):
        import json
        from unittest.mock import patch
        import backend
        old_config = backend.state['bowl_config']
        old_source = backend.selected_source
        original_state = dict(backend.state)
        original_monitor = backend.bowl_monitor
        try:
            backend.bowl_monitor = BowlMonitor()
            backend.state['bowl_config'] = self.config
            backend.selected_source = 'celular'
            with backend.app.test_client() as client:
                for time in range(6):
                    with patch('backend.time.monotonic', return_value=time):
                        result = client.post('/update/1', data={'species': 'cat', 'confidence': .9, 'animal_box': json.dumps(self.region)})
                        self.assertEqual(result.status_code, 200)
                readings = result.get_json()['bowl_observations']
                self.assertEqual(readings['water']['count'], 1)
                self.assertEqual(readings['food']['count'], 0)
        finally:
            backend.state.update(original_state)
            backend.state['bowl_config'] = old_config
            backend.selected_source = old_source
            backend.bowl_monitor = original_monitor


class DemoSourceTests(unittest.TestCase):
    def test_starting_demo_clears_previous_bowl_marks(self):
        from unittest.mock import patch
        import backend
        original_state = dict(backend.state)
        original_source = backend.selected_source
        original_monitor = backend.bowl_monitor
        try:
            backend.bowl_monitor = BowlMonitor()
            backend.state['bowl_config'] = {'food': {'x': .1, 'y': .1, 'width': .2, 'height': .2}, 'water': ''}
            with patch.object(backend, 'capture_process', None), patch('backend.subprocess.Popen'), backend.app.test_client() as client:
                response = client.post('/camera-source', json={'source': 'exemplo'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(backend.state['bowl_config'], {'food': '', 'water': ''})
                readings = client.get('/status').get_json()['bowl_observations']
                self.assertEqual(readings['food']['count'], 0)
                self.assertEqual(readings['water']['count'], 0)
        finally:
            backend.state.update(original_state)
            backend.selected_source = original_source
            backend.bowl_monitor = original_monitor


if __name__ == '__main__':
    unittest.main()

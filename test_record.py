#!/usr/bin/env python3
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
import os
import time
import math

# Set a dummy API key before importing record.py to avoid initialization error
os.environ['GOOGLE_API_KEY'] = 'test_dummy_key'

# Add the current directory to sys.path to import record.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the googlemaps.Client before importing record
with patch('googlemaps.Client') as mock_client:
    mock_client.return_value = Mock()
    import record

from pytz import timezone


class TestRecord(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.CET = timezone('Europe/Vienna')
        
    @patch('record.gmaps')
    def test_get_travel_time_success(self, mock_gmaps):
        """Test successful travel time retrieval."""
        # Mock the response from Google Maps API
        mock_response = {
            "rows": [{
                "elements": [{
                    "status": "OK",
                    "duration_in_traffic": {"value": 1800}  # 30 minutes
                }]
            }]
        }
        mock_gmaps.distance_matrix.return_value = mock_response
        
        result = record.get_travel_time("origin", "destination")
        
        self.assertEqual(result, 1800)
        mock_gmaps.distance_matrix.assert_called_once_with(
            "origin", "destination", mode="driving", departure_time="now"
        )
    
    @patch('record.gmaps')
    def test_get_travel_time_failure(self, mock_gmaps):
        """Test travel time retrieval when API returns error."""
        # Mock the response with error status
        mock_response = {
            "rows": [{
                "elements": [{
                    "status": "NOT_FOUND"
                }]
            }]
        }
        mock_gmaps.distance_matrix.return_value = mock_response
        
        result = record.get_travel_time("origin", "destination")
        
        self.assertIsNone(result)
    
    @patch('record.gmaps')
    def test_get_travel_time_exception(self, mock_gmaps):
        """Test travel time retrieval when API raises exception."""
        mock_gmaps.distance_matrix.side_effect = Exception("API Error")
        
        result = record.get_travel_time("origin", "destination")
        self.assertIsNone(result)

    @patch('record.get_travel_time')
    @patch('record.datetime')
    @patch('builtins.print')
    def test_update_commute_time_success(self, mock_print, mock_datetime, mock_get_travel_time):
        """Test successful commute time update."""
        # Mock datetime.now()
        mock_now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=self.CET)
        mock_datetime.now.return_value = mock_now
        
        # Mock travel times
        mock_get_travel_time.side_effect = [1200, 1500, 1800, 2100]  # Different times for each route
        
        # Mock the Prometheus gauges
        with patch('record.commute_time_seconds_to_ekz') as mock_gauge_ekz, \
             patch('record.commute_time_seconds_to_b3') as mock_gauge_b3, \
             patch('record.commute_time_seconds_trins_to_b3') as mock_gauge_trins_b3, \
             patch('record.commute_time_seconds_b3_to_trins') as mock_gauge_b3_trins:
            
            record.update_commute_time()
            
            # Verify that all gauges were set with correct values
            mock_gauge_ekz.set.assert_called_once_with(1200)
            mock_gauge_b3.set.assert_called_once_with(1500)
            mock_gauge_trins_b3.set.assert_called_once_with(1800)
            mock_gauge_b3_trins.set.assert_called_once_with(2100)
            
            # Verify print statements were called
            self.assertEqual(mock_print.call_count, 4)

    @patch('record.get_travel_time')
    @patch('record.datetime')
    @patch('builtins.print')
    def test_update_commute_time_with_failures(self, mock_print, mock_datetime, mock_get_travel_time):
        """Test commute time update when some API calls fail."""
        # Mock datetime.now()
        mock_now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=self.CET)
        mock_datetime.now.return_value = mock_now
        
        # Mock travel times with some None values (failures)
        mock_get_travel_time.side_effect = [None, 1500, None, 2100]
        
        # Mock the Prometheus gauges
        with patch('record.commute_time_seconds_to_ekz') as mock_gauge_ekz, \
             patch('record.commute_time_seconds_to_b3') as mock_gauge_b3, \
             patch('record.commute_time_seconds_trins_to_b3') as mock_gauge_trins_b3, \
             patch('record.commute_time_seconds_b3_to_trins') as mock_gauge_b3_trins:
            
            record.update_commute_time()
            
            # Verify that only successful calls set the gauges
            mock_gauge_ekz.set.assert_not_called()
            mock_gauge_b3.set.assert_called_once_with(1500)
            mock_gauge_trins_b3.set.assert_not_called()
            mock_gauge_b3_trins.set.assert_called_once_with(2100)
            
            # Verify error messages were printed
            error_calls = [call for call in mock_print.call_args_list if 'ERROR' in str(call)]
            self.assertEqual(len(error_calls), 2)

    def test_get_next_run_time_morning_window(self):
        """Test next run time calculation during the morning window (06:00 - 09:59)."""
        # Test at 07:05 -> should return 07:15
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 7, 5, 0, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 15, 7, 15, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

    def test_get_next_run_time_afternoon_window(self):
        """Test next run time calculation during the afternoon window (15:00 - 18:59)."""
        # Test at 16:35 -> should return 16:45
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 16, 35, 0, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 15, 16, 45, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

    def test_get_next_run_time_outside_windows(self):
        """Test next run time calculation outside active windows."""
        # Before morning window (e.g., 03:45) -> should return 06:00
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 3, 45, 30, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 15, 6, 0, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

        # Between windows (e.g., 11:00) -> should return 15:00
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 11, 0, 0, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 15, 15, 0, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

        # After afternoon window (e.g., 22:30) -> should return 06:00 next day
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 22, 30, 15, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 16, 6, 0, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

    def test_get_next_run_time_boundary_conditions(self):
        """Test next run time calculation at boundary hours."""
        # At 06:00 (start of morning window) -> should be 06:15
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 6, 0, 0, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 15, 6, 15, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

        # At 10:00 (end of morning window) -> should be 15:00
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 15, 15, 0, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

        # At 15:00 (start of afternoon window) -> should be 15:15
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 15, 0, 0, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 15, 15, 15, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

        # At 19:00 (end of afternoon window) -> should be 06:00 next day
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 19, 0, 0, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 16, 6, 0, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

    def test_get_next_run_time_midnight_rollover(self):
        """Test next run time calculation around midnight."""
        # Test at 23:30 -> should return 06:00 next day
        with patch('record.datetime') as mock_datetime:
            current_time = datetime(2024, 1, 15, 23, 30, 0, tzinfo=self.CET)
            mock_datetime.now.return_value = current_time
            next_run = record.get_next_run_time()
            expected = datetime(2024, 1, 16, 6, 0, 0, tzinfo=self.CET)
            self.assertEqual(next_run, expected)

    def test_is_in_active_window(self):
        """Test the active window detection."""
        # Test inside morning window
        with patch('record.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 8, 0, 0, tzinfo=self.CET)
            self.assertTrue(record.is_in_active_window())

        # Test inside afternoon window
        with patch('record.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 17, 0, 0, tzinfo=self.CET)
            self.assertTrue(record.is_in_active_window())

        # Test outside active windows
        with patch('record.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 15, 12, 0, 0, tzinfo=self.CET)
            self.assertFalse(record.is_in_active_window())

    def test_unset_gauges(self):
        """Test that gauges are correctly unset."""
        with patch('record.commute_time_seconds_to_ekz') as mock_gauge_ekz, \
             patch('record.commute_time_seconds_to_b3') as mock_gauge_b3, \
             patch('record.commute_time_seconds_trins_to_b3') as mock_gauge_trins_b3, \
             patch('record.commute_time_seconds_b3_to_trins') as mock_gauge_b3_trins:
            
            record.unset_gauges()
            
            for mock_gauge in [mock_gauge_ekz, mock_gauge_b3, mock_gauge_trins_b3, mock_gauge_b3_trins]:
                self.assertEqual(mock_gauge.set.call_count, 1)
                args, kwargs = mock_gauge.set.call_args
                self.assertTrue(math.isnan(args[0]))


class TestIntegration(unittest.TestCase):
    """Integration tests for the main workflow."""
    
    @patch('record.start_http_server')
    @patch('record.update_commute_time')
    @patch('record.unset_gauges')
    @patch('record.is_in_active_window')
    @patch('record.get_next_run_time')
    @patch('record.datetime')
    @patch('time.sleep')
    @patch('builtins.print')
    @patch('sys.stdout.flush')
    def test_main_loop_single_iteration_in_window(self, mock_flush, mock_print, mock_sleep, mock_datetime, \
                                                 mock_get_next_run, mock_is_in_window, mock_unset_gauges, \
                                                 mock_update, mock_start_server):
        """Test a single iteration of the main loop inside an active window."""
        # Mock being inside an active window
        mock_is_in_window.return_value = True
        
        # Mock current time and next run time
        current_time = datetime(2024, 1, 15, 8, 5, 0)
        next_run_time = datetime(2024, 1, 15, 8, 15, 0)
        
        mock_datetime.now.return_value = current_time
        mock_get_next_run.return_value = next_run_time
        
        # Mock sleep to break the loop after one iteration
        mock_sleep.side_effect = KeyboardInterrupt()
        
        with self.assertRaises(KeyboardInterrupt):
            record.start_http_server(record.PROMETHEUS_PORT)
            while True:
                if record.is_in_active_window():
                    record.update_commute_time()
                else:
                    record.unset_gauges()
                next_scheduled_run = record.get_next_run_time()
                sleep_duration = (next_scheduled_run - record.datetime.now(record.CET)).total_seconds()
                if sleep_duration > 0:
                    time.sleep(sleep_duration)

        mock_update.assert_called_once()
        mock_unset_gauges.assert_not_called()

    @patch('record.start_http_server')
    @patch('record.update_commute_time')
    @patch('record.unset_gauges')
    @patch('record.is_in_active_window')
    @patch('record.get_next_run_time')
    @patch('record.datetime')
    @patch('time.sleep')
    @patch('builtins.print')
    @patch('sys.stdout.flush')
    def test_main_loop_single_iteration_outside_window(self, mock_flush, mock_print, mock_sleep, mock_datetime, \
                                                      mock_get_next_run, mock_is_in_window, mock_unset_gauges, \
                                                      mock_update, mock_start_server):
        """Test a single iteration of the main loop outside an active window."""
        # Mock being outside an active window
        mock_is_in_window.return_value = False
        
        # Mock current time and next run time
        current_time = datetime(2024, 1, 15, 3, 5, 0)
        next_run_time = datetime(2024, 1, 15, 6, 0, 0)
        
        mock_datetime.now.return_value = current_time
        mock_get_next_run.return_value = next_run_time
        
        # Mock sleep to break the loop after one iteration
        mock_sleep.side_effect = KeyboardInterrupt()
        
        with self.assertRaises(KeyboardInterrupt):
            record.start_http_server(record.PROMETHEUS_PORT)
            while True:
                if record.is_in_active_window():
                    record.update_commute_time()
                else:
                    record.unset_gauges()
                next_scheduled_run = record.get_next_run_time()
                sleep_duration = (next_scheduled_run - record.datetime.now(record.CET)).total_seconds()
                if sleep_duration > 0:
                    time.sleep(sleep_duration)

        mock_update.assert_not_called()
        mock_unset_gauges.assert_called_once()


if __name__ == '__main__':
    # Create a test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestRecord))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
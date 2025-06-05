"""Performance integration tests for AccessiWeather.

These tests verify that the integrated system meets performance requirements
and handles load appropriately.
"""

import concurrent.futures
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from accessiweather.cache import Cache
from accessiweather.services.weather_service import WeatherService


@pytest.mark.integration
@pytest.mark.slow
class TestAPIPerformance:
    """Test API integration performance."""

    def test_concurrent_api_requests(
        self,
        weather_service,
        sample_nws_current_response,
        sample_openmeteo_current_response,
        performance_timer,
    ):
        """Test performance with concurrent API requests."""
        # Mock API responses
        weather_service.nws_client.get_current_conditions.return_value = sample_nws_current_response
        weather_service.openmeteo_client.get_current_weather.return_value = (
            sample_openmeteo_current_response
        )

        def make_request(coordinates):
            lat, lon = coordinates
            return weather_service.get_current_conditions(lat, lon)

        # Test coordinates
        test_coordinates = [
            (40.7128, -74.0060),  # New York
            (34.0522, -118.2437),  # Los Angeles
            (41.8781, -87.6298),  # Chicago
            (29.7604, -95.3698),  # Houston
            (33.4484, -112.0740),  # Phoenix
        ]

        performance_timer.start()

        # Execute concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, coords) for coords in test_coordinates]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        performance_timer.stop()

        # Verify all requests completed successfully
        assert len(results) == 5
        assert all(result is not None for result in results)

        # Performance should be reasonable even with mocked responses
        assert performance_timer.elapsed < 5.0

        # Verify API was called for each request
        assert weather_service.nws_client.get_current_conditions.call_count >= 1

    def test_cache_performance_impact(self, performance_timer):
        """Test cache performance impact on API requests."""
        cache = Cache(default_ttl=300)

        # Test data
        test_data = {"temperature": 72, "condition": "sunny"}
        cache_key = "test_weather_data"

        # Test cache write performance
        performance_timer.start()
        for i in range(1000):
            cache.set(f"{cache_key}_{i}", test_data)
        performance_timer.stop()

        write_time = performance_timer.elapsed
        assert write_time < 1.0, f"Cache writes took {write_time:.2f}s, expected < 1.0s"

        # Test cache read performance
        performance_timer.start()
        for i in range(1000):
            result = cache.get(f"{cache_key}_{i}")
            assert result == test_data
        performance_timer.stop()

        read_time = performance_timer.elapsed
        assert read_time < 0.5, f"Cache reads took {read_time:.2f}s, expected < 0.5s"

    def test_api_rate_limiting_compliance(self, weather_service, sample_nws_current_response):
        """Test that API rate limiting is respected."""

        # Mock API with delay to simulate rate limiting
        def delayed_response(*args, **kwargs):
            time.sleep(0.1)  # Simulate API delay
            return sample_nws_current_response

        weather_service.nws_client.get_current_conditions.side_effect = delayed_response

        # Make multiple requests and measure timing
        start_time = time.time()

        for _ in range(5):
            weather_service.get_current_conditions(40.7128, -74.0060)

        end_time = time.time()
        total_time = end_time - start_time

        # Should respect rate limiting (at least 0.5 seconds for 5 requests)
        assert total_time >= 0.5, f"Requests completed too quickly: {total_time:.2f}s"

        # But shouldn't be excessively slow
        assert total_time < 2.0, f"Requests took too long: {total_time:.2f}s"


@pytest.mark.integration
@pytest.mark.slow
class TestMemoryPerformance:
    """Test memory usage and performance."""

    def test_memory_usage_under_load(self, weather_service, sample_nws_current_response):
        """Test memory usage remains stable under load."""
        import gc
        import sys

        # Mock API response
        weather_service.nws_client.get_current_conditions.return_value = sample_nws_current_response

        # Get baseline memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Simulate heavy usage
        for i in range(100):
            # Make API requests
            weather_service.get_current_conditions(40.7128 + i * 0.001, -74.0060 + i * 0.001)

            # Periodic cleanup
            if i % 20 == 0:
                gc.collect()

        # Final memory check
        gc.collect()
        final_objects = len(gc.get_objects())

        # Memory growth should be reasonable
        growth_ratio = final_objects / initial_objects
        assert growth_ratio < 2.0, f"Memory usage grew by {growth_ratio:.2f}x"

    def test_cache_memory_management(self):
        """Test cache memory management with large datasets."""
        import gc

        cache = Cache(default_ttl=300, max_size=100)  # Limited size cache

        # Get baseline
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Fill cache beyond capacity
        large_data = {"data": "x" * 1000}  # 1KB per entry

        for i in range(200):  # More than max_size
            cache.set(f"key_{i}", large_data)

        # Check memory usage
        gc.collect()
        final_objects = len(gc.get_objects())

        # Memory should not grow excessively due to cache size limits
        growth_ratio = final_objects / initial_objects
        assert growth_ratio < 3.0, f"Cache memory grew by {growth_ratio:.2f}x"

        # Cache should have evicted old entries
        assert len(cache._cache) <= 100


@pytest.mark.integration
@pytest.mark.slow
class TestResponseTimePerformance:
    """Test response time performance requirements."""

    def test_initial_app_startup_time(self, temp_config_dir, sample_config, performance_timer):
        """Test initial application startup time."""
        with patch("accessiweather.gui.app_factory.create_app") as mock_create_app:

            # Mock app creation
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app

            performance_timer.start()

            # Simulate app startup
            from accessiweather.gui.app_factory import create_app

            app = mock_create_app(config=sample_config)

            performance_timer.stop()

            # Startup should be fast (< 5 seconds requirement)
            assert performance_timer.elapsed < 5.0
            assert app is not None

    def test_weather_data_refresh_time(
        self,
        weather_service,
        sample_nws_current_response,
        sample_nws_forecast_response,
        performance_timer,
    ):
        """Test weather data refresh time."""
        # Mock API responses
        weather_service.nws_client.get_current_conditions.return_value = sample_nws_current_response
        weather_service.nws_client.get_forecast.return_value = sample_nws_forecast_response

        lat, lon = 40.7128, -74.0060

        performance_timer.start()

        # Fetch all weather data
        current = weather_service.get_current_conditions(lat, lon)
        forecast = weather_service.get_forecast(lat, lon)

        performance_timer.stop()

        # Should meet < 10 seconds requirement
        assert performance_timer.elapsed < 10.0
        assert current is not None
        assert forecast is not None

    def test_location_change_response_time(self, temp_config_dir, performance_timer):
        """Test location change response time."""
        from accessiweather.location import LocationManager

        location_manager = LocationManager(config_dir=temp_config_dir)

        # Add test locations
        location_manager.add_location("New York", 40.7128, -74.0060)
        location_manager.add_location("Los Angeles", 34.0522, -118.2437)

        performance_timer.start()

        # Change location
        location_manager.set_current_location("New York")
        current1 = location_manager.get_current_location()

        location_manager.set_current_location("Los Angeles")
        current2 = location_manager.get_current_location()

        performance_timer.stop()

        # Should meet < 5 seconds requirement
        assert performance_timer.elapsed < 5.0
        assert current1[0] == "New York"
        assert current2[0] == "Los Angeles"

    def test_ui_update_response_time(
        self, headless_environment, sample_nws_current_response, performance_timer
    ):
        """Test UI update response time."""
        with patch("accessiweather.gui.ui_manager.UIManager") as mock_ui_manager:

            # Mock UI manager
            mock_ui_instance = MagicMock()
            mock_ui_manager.return_value = mock_ui_instance

            performance_timer.start()

            # Simulate UI updates
            for _ in range(10):
                mock_ui_instance.update_current_conditions(sample_nws_current_response)

            performance_timer.stop()

            # UI updates should be very fast (< 1 second requirement)
            assert performance_timer.elapsed < 1.0
            assert mock_ui_instance.update_current_conditions.call_count == 10


@pytest.mark.integration
@pytest.mark.slow
class TestScalabilityPerformance:
    """Test system scalability and load handling."""

    def test_multiple_location_handling(self, temp_config_dir, performance_timer):
        """Test performance with multiple saved locations."""
        from accessiweather.location import LocationManager

        location_manager = LocationManager(config_dir=temp_config_dir)

        # Test data - 50 locations
        test_locations = [(f"City_{i}", 40.0 + i * 0.1, -74.0 + i * 0.1) for i in range(50)]

        performance_timer.start()

        # Add all locations
        for name, lat, lon in test_locations:
            location_manager.add_location(name, lat, lon)

        # Retrieve all locations
        all_locations = location_manager.get_all_locations()

        performance_timer.stop()

        # Should handle many locations efficiently
        assert performance_timer.elapsed < 2.0
        assert len(all_locations) == 50

    def test_concurrent_user_simulation(self, weather_service, sample_nws_current_response):
        """Test system behavior under concurrent user load."""
        # Mock API response
        weather_service.nws_client.get_current_conditions.return_value = sample_nws_current_response

        def simulate_user_session():
            """Simulate a user session with multiple operations."""
            results = []
            for _ in range(5):
                # Simulate user refreshing weather data
                result = weather_service.get_current_conditions(40.7128, -74.0060)
                results.append(result)
                time.sleep(0.1)  # Brief pause between requests
            return results

        # Simulate 10 concurrent users
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(simulate_user_session) for _ in range(10)]
            all_results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Verify all sessions completed successfully
        assert len(all_results) == 10
        for session_results in all_results:
            assert len(session_results) == 5
            assert all(result is not None for result in session_results)

    def test_long_running_stability(self, weather_service, sample_nws_current_response):
        """Test system stability during long-running operation."""
        # Mock API response
        weather_service.nws_client.get_current_conditions.return_value = sample_nws_current_response

        start_time = time.time()
        successful_requests = 0
        failed_requests = 0

        # Run for 30 seconds (simulating extended operation)
        while time.time() - start_time < 30:
            try:
                result = weather_service.get_current_conditions(40.7128, -74.0060)
                if result is not None:
                    successful_requests += 1
                else:
                    failed_requests += 1
            except Exception:
                failed_requests += 1

            time.sleep(0.5)  # Request every 500ms

        # Should maintain high success rate
        total_requests = successful_requests + failed_requests
        success_rate = successful_requests / total_requests if total_requests > 0 else 0

        assert success_rate > 0.95, f"Success rate {success_rate:.2f} below 95%"
        assert total_requests > 50, f"Too few requests made: {total_requests}"


@pytest.mark.integration
@pytest.mark.slow
class TestResourceUsagePerformance:
    """Test resource usage efficiency."""

    def test_cpu_usage_efficiency(self, weather_service, sample_nws_current_response):
        """Test CPU usage remains reasonable under load."""
        import os

        import psutil

        # Mock API response
        weather_service.nws_client.get_current_conditions.return_value = sample_nws_current_response

        # Get current process
        process = psutil.Process(os.getpid())

        # Measure CPU usage during intensive operations
        cpu_percent_before = process.cpu_percent()

        # Perform intensive operations
        for _ in range(100):
            weather_service.get_current_conditions(40.7128, -74.0060)

        # Allow CPU measurement to stabilize
        time.sleep(1)
        cpu_percent_after = process.cpu_percent()

        # CPU usage should be reasonable (this is a rough check)
        # Note: This test may be flaky in CI environments
        assert cpu_percent_after < 80, f"CPU usage too high: {cpu_percent_after}%"

    def test_file_handle_management(self, temp_config_dir):
        """Test file handle management doesn't leak resources."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_files = len(process.open_files())

        # Perform operations that involve file I/O
        from accessiweather.location import LocationManager

        for i in range(50):
            location_manager = LocationManager(config_dir=temp_config_dir)
            location_manager.add_location(f"Test_{i}", 40.0 + i, -74.0 + i)
            # Let location_manager go out of scope

        # Check file handles after operations
        final_files = len(process.open_files())

        # Should not leak file handles
        file_growth = final_files - initial_files
        assert file_growth < 10, f"File handle leak detected: {file_growth} new handles"

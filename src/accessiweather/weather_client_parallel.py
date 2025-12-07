"""Parallel fetch coordinator for multi-source weather data retrieval."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from accessiweather.models.weather import (
    CurrentConditions,
    Forecast,
    HourlyForecast,
    Location,
    SourceData,
)

if TYPE_CHECKING:
    from accessiweather.models.alerts import WeatherAlerts

logger = logging.getLogger(__name__)


class ParallelFetchCoordinator:
    """
    Coordinates parallel fetching from multiple weather sources.

    Uses asyncio.gather with return_exceptions=True to handle individual
    source failures without blocking others.
    """

    def __init__(
        self,
        timeout: float = 5.0,
    ):
        """
        Initialize the coordinator.

        Args:
            timeout: Timeout in seconds for each source request (default: 5.0)

        """
        self.timeout = timeout

    async def fetch_all(
        self,
        location: Location,
        fetch_nws: Coroutine[
            Any,
            Any,
            tuple[
                CurrentConditions | None,
                Forecast | None,
                HourlyForecast | None,
                WeatherAlerts | None,
            ],
        ]
        | None = None,
        fetch_openmeteo: Coroutine[
            Any, Any, tuple[CurrentConditions | None, Forecast | None, HourlyForecast | None]
        ]
        | None = None,
        fetch_visualcrossing: Coroutine[
            Any,
            Any,
            tuple[
                CurrentConditions | None,
                Forecast | None,
                HourlyForecast | None,
                WeatherAlerts | None,
            ],
        ]
        | None = None,
    ) -> list[SourceData]:
        """
        Fetch from all available sources in parallel.

        Args:
            location: The location to fetch weather for
            fetch_nws: Coroutine to fetch NWS data (optional)
            fetch_openmeteo: Coroutine to fetch Open-Meteo data (optional)
            fetch_visualcrossing: Coroutine to fetch Visual Crossing data (optional)

        Returns:
            List of SourceData objects from all sources

        """
        results: list[SourceData] = []
        tasks: list[tuple[str, asyncio.Task[Any]]] = []

        # Create tasks for each available source
        if fetch_nws is not None:
            task = asyncio.create_task(self._fetch_with_timeout(fetch_nws, "nws"))
            tasks.append(("nws", task))

        if fetch_openmeteo is not None:
            task = asyncio.create_task(self._fetch_with_timeout(fetch_openmeteo, "openmeteo"))
            tasks.append(("openmeteo", task))

        if fetch_visualcrossing is not None:
            task = asyncio.create_task(
                self._fetch_with_timeout(fetch_visualcrossing, "visualcrossing")
            )
            tasks.append(("visualcrossing", task))

        if not tasks:
            return results

        # Wait for all tasks to complete
        task_results = await asyncio.gather(
            *[t for _, t in tasks],
            return_exceptions=True,
        )

        # Process results
        for (source_name, _), result in zip(tasks, task_results, strict=False):
            if isinstance(result, Exception):
                # Handle exception
                source_data = self._handle_source_failure(source_name, result)
                results.append(source_data)
            elif result is None:
                # Timeout or other None result
                source_data = SourceData(
                    source=source_name,
                    fetch_time=datetime.now(UTC),
                    success=False,
                    error="Request timed out",
                )
                results.append(source_data)
            else:
                # Success - unpack the result tuple
                source_data = self._create_source_data(source_name, result)
                results.append(source_data)

        return results

    async def _fetch_with_timeout(
        self,
        coro: Coroutine[Any, Any, Any],
        source_name: str,
    ) -> Any | None:
        """
        Execute coroutine with timeout, returning None on timeout.

        Args:
            coro: The coroutine to execute
            source_name: Name of the source for logging

        Returns:
            Result of the coroutine, or None on timeout

        """
        try:
            return await asyncio.wait_for(coro, timeout=self.timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Source {source_name} timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.warning(f"Source {source_name} failed: {e}")
            raise

    def _handle_source_failure(
        self,
        source_name: str,
        error: Exception,
    ) -> SourceData:
        """
        Handle a source failure gracefully.

        Args:
            source_name: Name of the failed source
            error: The exception that occurred

        Returns:
            SourceData with success=False and error message

        """
        logger.warning(f"Source {source_name} failed: {error}")

        return SourceData(
            source=source_name,
            current=None,
            forecast=None,
            hourly_forecast=None,
            alerts=None,
            fetch_time=datetime.now(UTC),
            success=False,
            error=str(error),
        )

    def _create_source_data(
        self,
        source_name: str,
        result: tuple[Any, ...],
    ) -> SourceData:
        """
        Create SourceData from a successful fetch result.

        Args:
            source_name: Name of the source
            result: Tuple of (current, forecast, hourly_forecast, [alerts])

        Returns:
            SourceData with the fetched data

        """
        # Handle different result tuple lengths
        current = result[0] if len(result) > 0 else None
        forecast = result[1] if len(result) > 1 else None
        hourly_forecast = result[2] if len(result) > 2 else None
        alerts = result[3] if len(result) > 3 else None

        return SourceData(
            source=source_name,
            current=current,
            forecast=forecast,
            hourly_forecast=hourly_forecast,
            alerts=alerts,
            fetch_time=datetime.now(UTC),
            success=True,
            error=None,
        )

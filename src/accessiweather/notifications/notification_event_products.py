"""HWO and SPS product change workflows for notification events."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..models import AppSettings, Location, TextProduct, WeatherAlert


_HWO_RATE_LIMIT_WINDOW = timedelta(minutes=30)
_SPS_RATE_LIMIT_WINDOW = timedelta(minutes=30)

logger = logging.getLogger(__name__)


def check_hwo_update(
    manager: Any,
    location: Location,
    hwo_product: TextProduct | None,
    settings: AppSettings,
) -> None:
    """Inspect a freshly fetched HWO product and notify on material updates."""
    if hwo_product is None:
        return
    if not getattr(location, "cwa_office", None):
        return

    new_issuance = hwo_product.issuance_time
    new_text = hwo_product.product_text or ""
    signature = manager._hash_product_text(new_text)

    stored_issuance = manager.state.last_hwo_issuance_time
    stored_signature = manager.state.last_hwo_summary_signature
    stored_text = manager.state.last_hwo_text

    if stored_issuance is None and stored_signature is None:
        manager.state.last_hwo_issuance_time = new_issuance
        manager.state.last_hwo_text = new_text
        manager.state.last_hwo_summary_signature = signature
        manager._save_state()
        logger.debug(
            "_check_hwo_update: first-run baseline for %s (%s) - no notification",
            location.name,
            location.cwa_office,
        )
        return

    if stored_issuance == new_issuance and stored_signature == signature:
        return

    manager.state.last_hwo_issuance_time = new_issuance
    manager.state.last_hwo_text = new_text
    manager.state.last_hwo_summary_signature = signature
    manager._save_state()

    if not getattr(settings, "notify_hwo_update", True):
        logger.debug(
            "_check_hwo_update: notify_hwo_update disabled - suppressing dispatch for %s",
            location.name,
        )
        return

    bucket = ("HWO", location.name)
    now = datetime.now(UTC)
    last_sent = manager._last_product_notified_at.get(bucket)
    if last_sent is not None and now - last_sent < _HWO_RATE_LIMIT_WINDOW:
        logger.debug(
            "_check_hwo_update: rate-limited for %s (last=%s) - state updated, no dispatch",
            location.name,
            last_sent,
        )
        return
    manager._last_product_notified_at[bucket] = now

    message = manager._format_hwo_body(stored_text, hwo_product)
    logger.info(
        "HWO updated for %s (%s): %s -> %s",
        location.name,
        location.cwa_office,
        stored_issuance,
        new_issuance,
    )
    manager._dispatch_hwo_notification(
        location=location,
        product=hwo_product,
        message=message,
    )


def check_sps_new(
    manager: Any,
    location: Location,
    sps_products: Sequence[TextProduct] | None,
    cached_alerts: Sequence[WeatherAlert] | None,
    settings: AppSettings,
) -> None:
    """Dispatch notifications for informational Special Weather Statement products."""
    products = list(sps_products or [])
    alerts = list(cached_alerts or [])

    if not hasattr(manager, "_sps_cold_started"):
        manager._sps_cold_started = set()

    bucket_key = ("SPS", location.name)
    is_cold_start = (
        location.name not in manager._sps_cold_started and not manager.state.last_sps_product_ids
    )

    current_ids = {p.product_id for p in products}

    if is_cold_start:
        if current_ids:
            manager.state.last_sps_product_ids |= current_ids
            manager._save_state()
        manager._sps_cold_started.add(location.name)
        logger.debug(
            "_check_sps_new: cold-start baseline for %s (%d ids) - no dispatch",
            location.name,
            len(current_ids),
        )
        return

    stale = manager.state.last_sps_product_ids - current_ids
    if stale:
        manager.state.last_sps_product_ids -= stale
        manager._save_state()
        logger.debug("_check_sps_new: expired %d SPS id(s) for %s", len(stale), location.name)

    new_products = [p for p in products if p.product_id not in manager.state.last_sps_product_ids]
    if not new_products:
        return

    alert_signatures = manager._sps_alert_signatures(alerts)
    enabled = getattr(settings, "notify_sps_issued", True)

    dispatched_this_call = False
    for product in new_products:
        manager.state.last_sps_product_ids.add(product.product_id)

        if manager._sps_is_case_a(product, alert_signatures):
            logger.debug(
                "_check_sps_new: Case A (event-style) suppressed - product=%s",
                product.product_id,
            )
            continue

        if not enabled:
            logger.debug(
                "_check_sps_new: notify_sps_issued disabled - suppressing %s",
                product.product_id,
            )
            continue

        now = datetime.now(UTC)
        last_sent = manager._last_product_notified_at.get(bucket_key)
        if last_sent is not None and now - last_sent < _SPS_RATE_LIMIT_WINDOW:
            logger.debug(
                "_check_sps_new: rate-limited for %s (last=%s) - state updated, no dispatch",
                location.name,
                last_sent,
            )
            continue
        if dispatched_this_call:
            logger.debug(
                "_check_sps_new: additional Case B in same fetch rate-limited - %s",
                product.product_id,
            )
            continue

        manager._last_product_notified_at[bucket_key] = now
        dispatched_this_call = True
        message = manager._format_sps_body(product)
        logger.info(
            "SPS informational dispatch for %s (%s): %s",
            location.name,
            product.cwa_office,
            product.product_id,
        )
        manager._dispatch_sps_notification(
            location=location,
            product=product,
            message=message,
        )

    manager._save_state()

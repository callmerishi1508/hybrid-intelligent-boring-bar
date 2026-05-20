import logging
import time
from typing import Dict, Any
from azure.core.exceptions import AzureError

log = logging.getLogger(__name__)

class TwinUpdater:
    """
    Thin wrapper around ADT updates with retry logic. Designed to be testable and safe.
    """
    def __init__(self, client, max_retries: int = 2, retry_delay: float = 0.5):
        self.client = client
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def update_properties(self, twin_id: str, patch: Dict[str, Any]):
        """Update digital twin properties with automatic retry on transient errors.
        
        Args:
            twin_id: ID of the digital twin to update
            patch: JSON Patch operations list
        
        Returns:
            True if successful, False otherwise
        """
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.update_digital_twin(twin_id, patch)
                if attempt > 0:
                    log.info("ADT update succeeded on attempt %d", attempt + 1)
                else:
                    log.debug("ADT update succeeded")
                return True
            except AzureError as ex:
                is_transient = (
                    ex.status_code in (408, 429, 500, 503)  # Request timeout, throttle, server errors
                    if hasattr(ex, 'status_code') else False
                )
                if is_transient and attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    log.warning(f"ADT update attempt {attempt + 1} failed (transient): {ex.status_code if hasattr(ex, 'status_code') else ex}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                log.error(f"ADT update failed (attempt {attempt + 1}): {ex}", exc_info=False)
                return False
        return False

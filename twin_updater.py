import logging
from typing import Dict, Any
from azure.core.exceptions import AzureError

log = logging.getLogger(__name__)

class TwinUpdater:
    """
    Thin wrapper around ADT updates. Designed to be testable and safe.
    """
    def __init__(self, client):
        self.client = client

    def update_properties(self, twin_id: str, patch: Dict[str, Any]):
        try:
            resp = self.client.update_digital_twin(twin_id, patch)
            log.debug("ADT update resp: %s", resp)
            return True
        except AzureError as ex:
            log.exception("ADT update failed: %s", ex)
            return False

"""Transport boundary. Simulation never operates relays or invents telemetry."""
import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Acknowledgement:
    acknowledged: bool
    control_mode: str
    message: str
    # Only a definitive rejection of START proves the command did not start a pump.
    definitive_rejection: bool = False


class DeviceControl:
    def __init__(self, mode):
        self.mode = mode

    @property
    def available(self):
        return self.mode == 'simulated'

    def _command(self, action, device, event_id=None):
        if self.mode != 'simulated':
            logger.warning('Hardware command unavailable action=%s device=%s', action, device.device_id)
            return Acknowledgement(False, 'hardware', 'ESP32 command transport is not configured.', True)
        logger.warning('SIMULATED pump command action=%s device=%s event=%s; no hardware operated', action, device.device_id, event_id)
        return Acknowledgement(True, 'simulated', 'Simulated acknowledgement only; no physical pump was operated.')

    def start_pump(self, device, event_id=None):
        return self._command('start', device, event_id)

    def stop_pump(self, device, event_id=None):
        return self._command('stop', device, event_id)

    def emergency_stop(self, device, event_id=None):
        return self._command('emergency-stop', device, event_id)


def get_control():
    return DeviceControl(settings.irrigation_control_mode)

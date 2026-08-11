"""Inert usage-worker process boundary."""

import signal
from threading import Event
from types import FrameType

from gateway.config import ProcessName, Settings


def run(settings: Settings | None = None, *, stop_event: Event | None = None) -> None:
    """Validate worker bootstrap and block until graceful shutdown is requested."""
    resolved_settings = settings if settings is not None else Settings()
    if resolved_settings.process_name is not ProcessName.USAGE_WORKER:
        raise ValueError("usage worker requires process_name=usage-worker")

    resolved_stop_event = stop_event if stop_event is not None else Event()
    resolved_stop_event.wait()


def main() -> None:
    """Run the inert worker and translate process signals into normal shutdown."""
    stop_event = Event()

    def request_shutdown(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        stop_event.set()

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    run(stop_event=stop_event)


if __name__ == "__main__":
    main()

import time

from software_factory.services.coordinator import Coordinator


class Scheduler:
    def __init__(self, coordinator: Coordinator, poll_interval_seconds: int) -> None:
        self.coordinator = coordinator
        self.poll_interval_seconds = poll_interval_seconds

    def run_forever(self) -> None:
        while True:
            self.coordinator.run_once()
            time.sleep(self.poll_interval_seconds)


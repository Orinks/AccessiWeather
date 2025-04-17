import threading

class NationalForecastFetcher:
    def __init__(self, service):
        self.service = service
        self.thread = None
        self._stop_event = threading.Event()

    def fetch(self, on_success=None, on_error=None, additional_data=None):
        pass

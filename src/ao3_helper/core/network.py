import threading
import time

from ao3_helper.logger_setup import logger


class RateLimiter:
    """
    Singleton Thread-Safe per gestire le richieste verso AO3.
    Implementa un algoritmo 'Token Bucket' semplificato.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(RateLimiter, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.requests_per_minute = 30
        self.interval = 60.0 / self.requests_per_minute

        self.last_request_time = 0.0
        self._access_lock = threading.Lock()
        self._initialized = True
        logger.info(f"RateLimiter initialized. Interval: {self.interval:.2f}s")

    def acquire(self):
        """
        Blocca il thread chiamante finché non è sicuro effettuare una richiesta.
        """
        with self._access_lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time

            if elapsed < self.interval:
                sleep_time = self.interval - elapsed
                logger.debug(f"RateLimiter: Throttling request for {sleep_time:.2f}s...")
                time.sleep(sleep_time)

            self.last_request_time = time.time()


limiter = RateLimiter()

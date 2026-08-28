"""수집 예절 (S15P21E105-63).

같은 도메인에 1초 미만 간격으로 재요청하지 않고, robots.txt 가 금지한 URL 은
접속하지 않는다. 시계와 sleep 을 주입할 수 있어 테스트가 실제로 기다리지 않는다.
"""

import logging
import time
import urllib.robotparser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MIN_INTERVAL_SEC = 1.0


class RateLimiter:
    """도메인별 최소 요청 간격을 지키게 대기시킨다."""

    def __init__(self, interval=MIN_INTERVAL_SEC, clock=time.monotonic, sleep=time.sleep):
        self._interval = interval
        self._clock = clock
        self._sleep = sleep
        self._last = {}  # 도메인 → 마지막 요청 시각

    def wait(self, url):
        domain = urlparse(url).netloc
        now = self._clock()
        elapsed = now - self._last.get(domain, -self._interval)
        if elapsed < self._interval:
            self._sleep(self._interval - elapsed)
        self._last[domain] = self._clock()


class RobotsGate:
    """robots.txt 허용 여부를 도메인별로 캐시해서 판정한다."""

    def __init__(self, user_agent):
        self._user_agent = user_agent
        self._parsers = {}  # 도메인 → RobotFileParser 또는 None(읽기 실패)

    def allowed(self, url):
        domain = urlparse(url).netloc
        if domain not in self._parsers:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(f"https://{domain}/robots.txt")
            try:
                parser.read()
                self._parsers[domain] = parser
            except Exception:
                # 공개 RSS 를 제공하는 언론사라 robots 를 못 읽으면 허용으로 간주
                logger.warning("robots.txt 읽기 실패, 허용으로 간주: %s", domain)
                self._parsers[domain] = None
        parser = self._parsers[domain]
        return True if parser is None else parser.can_fetch(self._user_agent, url)

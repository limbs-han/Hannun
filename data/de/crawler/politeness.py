"""수집 예절 (S15P21E105-63).

같은 도메인에 1초 미만 간격으로 재요청하지 않고, robots.txt 가 금지한 URL 은
접속하지 않는다. 시계와 sleep 을 주입할 수 있어 테스트가 실제로 기다리지 않는다.
"""

import logging
import time
import urllib.error
import urllib.request
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
    """robots.txt 허용 여부를 도메인별로 캐시해서 판정한다.

    404 같은 '규칙 없음'과 네트워크 실패는 허용으로 캐시한다. 401·403·5xx 는
    일시 거부로 보고 짧게 재시도한 뒤, 그래도 실패하면 이번 실행에서만 보류하고
    다음 실행에서 다시 읽는다. 순간 장애 한 번(한겨레에서 실측)이 언론사 하나를
    영구 차단으로 만드는 것을 막기 위함이다.
    """

    _HOLD = object()  # 이번 실행 보류 표시

    def __init__(self, user_agent, sleep=time.sleep):
        self._user_agent = user_agent
        self._sleep = sleep
        self._parsers = {}  # 도메인 → RobotFileParser / None(허용) / _HOLD(보류)

    def _fetch_rules(self, domain):
        """robots.txt 본문을 돌려준다. 규칙 없음이면 None, 일시 거부면 예외."""
        request = urllib.request.Request(
            f"https://{domain}/robots.txt", headers={"User-Agent": self._user_agent}
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.read().decode("utf-8", "ignore")
        except urllib.error.HTTPError as error:
            if error.code in (401, 403) or error.code >= 500:
                raise  # 일시 거부 취급, 재시도 대상
            return None  # 404 등 = 규칙 없음
        except OSError:
            # DNS 실패 등 접속 불가(국민일보에서 실측). 명시적 거부와 달리 허용으로 간주
            return None

    def allowed(self, url):
        domain = urlparse(url).netloc
        if domain not in self._parsers:
            self._parsers[domain] = self._load(domain)
        parser = self._parsers[domain]
        if parser is self._HOLD:
            return False
        return True if parser is None else parser.can_fetch(self._user_agent, url)

    def _load(self, domain, retries=2):
        for attempt in range(retries + 1):
            try:
                rules = self._fetch_rules(domain)
            except Exception:
                if attempt < retries:
                    self._sleep(1)
                continue
            if rules is None:
                return None
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(rules.splitlines())
            return parser
        logger.warning("robots.txt 일시 거부, 이번 실행에서 보류: %s", domain)
        return self._HOLD

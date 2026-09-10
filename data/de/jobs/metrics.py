"""잡이 센 값을 Pushgateway 로 보낸다 (S15P21E105-79).

BE 서버(B)의 Pushgateway 로 밀고 그쪽 Prometheus 가 긁어간다. Prometheus 는 대상을
긁어가는 도구여서 A 를 대상에 넣으려면 A 의 지표 포트를 열어야 하는데, 우리 잡은 전부
배치라 Pushgateway 쪽이 용도에 맞다.

**Pushgateway 에는 인증이 없다.** 포트를 인터넷에 열면 누구나 가짜 지표를 밀거나 기사
건수를 읽을 수 있다. 그래서 B 는 127.0.0.1 로만 열고, 백업(S15P21E105-74)이 쓰는 키로
ssh 해서 B 안에서 curl 로 보낸다. 새로 여는 포트가 없다.

지표 이름은 모두 pipeline_ 으로 시작해 BE 서비스 지표(http_server_requests_, mysql_,
kafka_)와 섞이지 않는다. instance 라벨로 잡을 구분한다.

**지표를 못 보내도 잡은 성공해야 한다.** 모니터링 실패가 파이프라인을 멈추면 안 되므로
계산과 전송을 모두 감싸 예외를 삼키고 경고만 남긴다.

설정은 infra/.env 다. PUSHGATEWAY 가 비어 있으면 아무것도 보내지 않는다 — 로컬 개발에서
잡이 그대로 돌아야 한다. PUSHGATEWAY_SSH 를 비우면 ssh 없이 그 주소로 바로 보낸다.
"""

import logging
import os
import subprocess
import urllib.request

logger = logging.getLogger("metrics")

# 받는 쪽에서 본 주소다. ssh 경유면 B 안에서의 주소이므로 localhost 다
GATEWAY = os.environ.get("PUSHGATEWAY", "")
SSH_TARGET = os.environ.get("PUSHGATEWAY_SSH", "")
SSH_KEY = os.environ.get("PUSHGATEWAY_KEY", "/opt/airflow/.ssh/b.pem")
CONTAINER = os.environ.get("PUSHGATEWAY_CONTAINER", "news-pushgateway")
PORT = 9091
JOB = "de-pipeline"
TIMEOUT = 20
LF = chr(10)  # Prometheus 형식은 줄 단위이고 CRLF 를 받지 않는다


def _label_value(value):
    """라벨 값에 쓸 수 있는 문자만 남긴다.

    언론사 이름을 라벨로 쓰는데 따옴표나 줄바꿈이 섞이면 Prometheus 형식이 깨진다.
    지울 문자를 나열하는 대신 남길 문자를 고른다. 한글은 isalnum 이 참이다.
    """
    return "".join(c for c in str(value) if c.isalnum() or c in " ._-")


def line(name, value, labels=None):
    """지표 한 줄. 이름 앞에 pipeline_ 을 붙인다."""
    if labels:
        pairs = ",".join('%s="%s"' % (k, _label_value(v)) for k, v in sorted(labels.items()))
        return "pipeline_%s{%s} %s" % (name, pairs, value)
    return "pipeline_%s %s" % (name, value)


# Pushgateway 는 포트 매핑 없이 떠 있어 호스트 이름으로는 닿지 않는다. 컨테이너 주소를
# 보낼 때마다 묻는다 — 컨테이너를 다시 만들면 주소가 바뀌기 때문이다
_INSPECT = "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "


def _ssh(command, body=None):
    res = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=accept-new",
         "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", SSH_TARGET, command],
        input=body, timeout=TIMEOUT, capture_output=True)
    if res.returncode:
        raise RuntimeError(res.stderr.decode(errors="replace").strip()[:200])
    return res.stdout.decode(errors="replace").strip()


def _send(path, body):
    if not SSH_TARGET:
        req = urllib.request.Request(GATEWAY.rstrip("/") + path,
                                     data=body.encode("utf-8"), method="PUT")
        urllib.request.urlopen(req, timeout=TIMEOUT).close()
        return
    address = _ssh(_INSPECT + CONTAINER)
    if not address:
        raise RuntimeError("컨테이너 주소를 못 찾음: " + CONTAINER)
    _ssh("curl -sS -f -X PUT --data-binary @- http://%s:%d%s" % (address, PORT, path),
         body.encode("utf-8"))


def push(instance, lines):
    """lines 는 line() 결과 목록이거나 그 목록을 만드는 함수다.

    함수를 넘기면 계산까지 이 안에서 보호된다 — 지표를 세다 터져도 잡은 계속 간다.
    PUT 이라 같은 instance 의 옛 지표는 전부 교체된다. 지난 실행 값이 남아 오해를
    만드는 일이 없다.
    """
    if not (GATEWAY or SSH_TARGET):
        logger.info("Pushgateway 미설정, 지표 전송 건너뜀")
        return
    try:
        body = LF.join(lines() if callable(lines) else lines) + LF
        _send("/metrics/job/%s/instance/%s" % (JOB, instance), body)
        logger.info("지표 전송 완료: %s", instance)
    except Exception as exc:
        logger.warning("지표 처리 실패, 잡은 계속한다: %s", exc)

# 파이프라인 모니터링 (S15P21E105-79)

잡이 이미 세고 있던 값을 밖으로 내보내 시간축으로 본다. 새로 계산하는 것은 적재 지연과
Kafka 적재 건수 둘뿐이고, 나머지는 로그에만 있던 값이다.

## 어디로 보내고 왜 그렇게 보내나

BE 서버(B)에 Prometheus 와 Grafana 가 이미 돌고 있어 새로 세우지 않았다.

Prometheus 는 대상을 긁어가는(pull) 도구다. A 를 대상에 넣으려면 A 의 지표 포트를 열고
SSAFY 보안그룹까지 손봐야 한다. 우리 잡은 전부 배치라 Prometheus 의 짝 도구인
Pushgateway 가 용도에 맞고, 그쪽이면 A 가 보내는(push) 쪽이 된다.

**B 의 포트는 하나도 열지 않았다.** Pushgateway 에는 인증이 없어서 포트를 열면 누구나 가짜
지표를 밀거나 기사 건수를 읽을 수 있다. 포트 매핑 없이 띄우면 Prometheus 는 같은 도커
네트워크라 그대로 긁고, A 는 백업(S15P21E105-74)이 쓰는 키로 B 에 ssh 해서 컨테이너 주소로
직접 보낸다. 컨테이너를 다시 만들면 주소가 바뀌므로 보낼 때마다 `docker inspect` 로 묻는다.

서버 자원(메모리·디스크) 지표는 이 방식으로 안 된다. 필요해지면 A 에 exporter 를 띄우고
포트를 열어야 한다. 지금은 파이프라인 지표만 본다.

## 지표

이름은 모두 `pipeline_` 으로 시작한다. BE 서비스 지표(`http_server_requests_`, `mysql_`,
`kafka_`)와 섞이지 않는다. `job="de-pipeline"` 과 `instance=<잡 이름>` 으로 구분된다.

| 지표 | 잡 | 뜻 |
|---|---|---|
| `pipeline_bronze_ingested_rows` | kafka_to_bronze | 이번 실행에 Kafka 에서 bronze 로 넣은 건수 |
| `pipeline_silver_partitions_updated` | bronze_to_silver | 갱신한 dt 파티션 수. 0 이면 신규 기사 없음 |
| `pipeline_silver_dropped_rows` | bronze_to_silver | 본문 없음·형식 불량으로 제외된 건수 |
| `pipeline_silver_unknown_publisher_rows` | bronze_to_silver | 미등록 언론사 건수. `publisher` 라벨에 이름 |
| `pipeline_ingest_lag_seconds` | bronze_to_silver | 레이크의 최신 기사가 몇 초 전 발행분인지 |
| `pipeline_ds_input_stale_days` | silver_to_ds_input | 이번에 다시 내려준 날짜 수. 평소 두셋 |
| `pipeline_gold_issues` | gold_issue_feed | 발행 대상 이슈 수 |
| `pipeline_gold_articles` | gold_issue_feed | 발행 대상 기사 수 |
| `pipeline_gold_ds2_matched_rows` | gold_issue_feed | 관점 값이 붙은 기사 수 |
| `pipeline_gold_window` | gold_issue_feed | 마지막으로 읽은 DS 창. `window` 라벨에 날짜 |

### 뒤처진 날짜는 0 이 정상이 아니다

silver 가 갱신된 날짜는 파일보다 새로워지므로 매번 뒤처진 것으로 잡혀 다시 내려간다.
15분마다 실시간 기사가 들어오니 오늘과 어제가 늘 잡히고, **평소 두세 날짜가 정상이다.**
0 은 silver 가 아예 안 바뀐 때뿐이다.

값이 갑자기 커지면 둘 중 하나다. 내려주기가 밀렸거나, RSS 가 옛 기사를 무더기로 줘서
오래된 날짜의 silver 가 갱신됐거나. 실측으로 2026-09-11 에 6월 1일과 9월 1일이 함께
잡힌 적이 있고 한 번 내려준 뒤로는 안 잡혔다.

### 적재 지연을 이렇게 재는 이유

갱신한 파티션에서 발행 시각의 최대값을 구해 실행 시각과 뺀다. `crawled_at` 으로는 못 잰다.
실시간분의 `crawled_at` 은 적재일 자정으로 근사한 값이어서 정확한 반영 시각이 없다
(계약 문서 `data/docs/contracts/de-to-ds-article-json.md` 참고).

전 구간 신선도 목표(S15P21E105-73)를 이 값으로 판정한다.

## 잡이 죽지 않는다

지표 계산과 전송은 `jobs/metrics.py` 의 `push()` 안에서 모두 감싸여 있다. Pushgateway 가
꺼져 있든 ssh 가 막히든 형식이 틀렸든 경고만 남기고 잡은 계속 간다. 모니터링 실패가
파이프라인을 멈추면 안 된다.

## 설정

`infra/.env` 에 한 줄이다.

```
PUSHGATEWAY_SSH=ubuntu@j15e105.p.ssafy.io
```

키 경로(`/opt/airflow/.ssh/b.pem`)와 컨테이너 이름(`news-pushgateway`)은 기본값이라 적지
않는다. 키는 백업 잡과 같은 것을 쓴다.

비어 있으면 아무것도 보내지 않는다. 로컬 개발에서 잡이 그대로 돌아야 한다.

`PUSHGATEWAY` 에 주소를 넣으면 ssh 없이 그 주소로 바로 보낸다. A 에 임시 Pushgateway 를
띄워 시험할 때 쓴다.

## B 서버에 추가한 것 (2026-09-10 적용)

BE 스택은 `/home/ubuntu/news-platform/` 에 있고 **git 리포가 아니다.** 서버에만 있어서
우리 변경이 BE 배포에 덮일 일은 없지만, 반대로 기록이 남지 않는다. 그래서 여기 적는다.
적용 전 두 파일을 `*.bak.<시각>` 으로 복사해 뒀다.

`deploy/docker-compose.infra.yml` 에 서비스 하나를 더했다.

```yaml
  pushgateway:
    image: prom/pushgateway:latest
    container_name: news-pushgateway
    restart: unless-stopped
    mem_limit: 64m
    networks:
      - news-net
```

`ports` 가 없다. 호스트에서는 닿지 않고 도커 네트워크 안에서만 보인다.

`deploy/prometheus.yml` 에 스크랩 대상을 더했다.

```yaml
  - job_name: 'de-pipeline'
    honor_labels: true
    static_configs:
      - targets: ['pushgateway:9091']
```

`honor_labels: true` 가 필요하다. 없으면 Prometheus 가 `job` 과 `instance` 를 자기 값으로
덮어써서 어느 잡이 보낸 값인지 구분이 사라진다.

### 되돌리기

두 파일에서 위 블록을 지우고 아래를 실행한다.

```bash
cd /home/ubuntu/news-platform
docker compose -f deploy/docker-compose.infra.yml rm -sf pushgateway
docker restart news-prometheus
```

Prometheus 재시작은 몇 초이고 서비스가 아니라 모니터링만 멈춘다.

## 대시보드

`infra/grafana/de-pipeline-dashboard.json` 을 Grafana 에서 가져오기 한다. Dashboards →
New → Import → Upload JSON file. 패널 일곱 개가 뜬다.

리포에 두는 이유는 화면 변경이 MR 에 남기 때문이다. 손으로 만든 대시보드는 컨테이너가
지워지면 사라진다. 패널을 고쳤으면 Grafana 에서 JSON 을 내보내 이 파일을 갱신한다.

## 지표를 더하는 방법

잡에서 이미 센 값이면 세 줄이다.

```python
import metrics

metrics.push("잡이름", lambda: [
    metrics.line("이름", 값),
    metrics.line("이름", 값, {"라벨": "값"}),
])
```

`push` 는 같은 `instance` 의 옛 지표를 전부 교체한다. 한 잡에서 두 번 부르면 뒤엣것만
남으므로 한 번에 모아 보낸다. 목록 대신 함수를 넘기면 값을 세는 도중 터져도 잡은 계속 간다.

라벨 값은 글자와 숫자, 공백, 마침표, 밑줄, 하이픈만 남고 나머지는 지워진다. 언론사 이름을
라벨로 쓰는데 따옴표나 줄바꿈이 섞이면 Prometheus 형식이 깨지기 때문이다.

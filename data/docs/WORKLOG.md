# 작업 기록 (DS1)

> 날짜별로 "무엇을 했고, 무엇을 결정했고, 다음에 뭘 할지"를 남긴다. 문제 해결 과정은 [TROUBLESHOOTING.md](TROUBLESHOOTING.md), 티켓별 상세는 [tickets/](tickets/).

---

## 2026-08-27

### 한 일
- **BE 문서(Kafka 수집 구조 · 공통 기사 JSON · API 스펙) 검토** → DS1 설계 문서와 대조
  - 설계 문서의 전제 "BE가 DB에 저장 → DS가 DB 읽기"가 실제와 다름. 실제: BE → Kafka `news.article.realtime.v1` → DE(HDFS). DS 입력은 공통 기사 JSON.
  - `published_at`은 **발행 시각**(RFC 3339 UTC)으로 확정. 크롤링 시각 필드는 없음.
  - API 응답 필드에서 DS1 산출물을 역산: `issueId`(안정적이어야 함), `pressCount`, `articleCount`, `score`(화제성 — 설계 문서에 없던 항목), 이슈 단위 `category`, `firstReportedAt/lastReportedAt`.
  - 상세는 [tickets/S15P21E105-99.md](tickets/S15P21E105-99.md) "BE 문서에서 확인한 것" 절.
- **프로젝트 골격 생성**: `src/hannun` 패키지(src 레이아웃), pyproject, venv(Python 3.14), pytest.
- **S15P21E105-99 공통 기사 JSON 입력 변환·Gold 저장 구현**
  - `schema.py` pydantic 검증 / `reader.py` JSON·JSONL·디렉토리 읽기 / `gold.py` parquet 파티션 저장소 / `pipeline.py` / `cli.py`
  - 샘플 데이터 10건(정상 5 + 배치 내 중복 1 + 리젝트 4) 생성 스크립트, 테스트 21개 통과.
  - CLI 실행 결과: records=10, valid=6, rejected=4, duplicates_in_batch=1, written=5, id_mismatch=1

- **코드 스타일 제정** — 이 저장소에 맞춰 `CODE_STYLE.md` 를 처음부터 씀 (이전 프로젝트 규칙은 참고만). ingest 모듈 전체를 그 규칙으로 다시 씀.
  - 처음 짠 코드에서 걸린 것: 모든 함수의 반환 타입, `Optional`/`from __future__`, 불릿·표가 든 docstring, 길이가 제각각인 구분선, 로그의 `%` 서식, 컬럼마다 붙은 설명 주석, 스크립트의 `sys.path` 조작.
  - 앞 단계를 위해 미리 정한 것: 임계값은 설정 dataclass 로 받기, 원본 컬럼 보존·파생 컬럼 추가, 난수 seed 고정과 파라미터 기록, 건별 문제는 예외 대신 리젝트, TODO 에 티켓 번호.
  - flake8(E9,F63,F7,F82,E501 / 110자) 검사 추가. 테스트 21개 그대로 통과.
- **팀 저장소 연동** — `lab.ssafy.com/s15-bigdata-dist-sub1/S15P21E105`. 모노레포(루트에 `back/ data/ front/ infra/`)라 우리 코드를 전부 `data/` 아래로 이동. 브랜치 `data/feat/S15P21E105-99-json-gold`(원격에 `data/dev` 기준으로 이미 있었음).
  - 커밋·MR 규칙을 `docs/GIT_CONVENTION.md`로 정함. BE가 이미 쓰는 `type: 제목 (지라키)` 형식과 같게 맞춤. 루트 README의 지라 연동 규칙(브랜치명에 키 → 진행 중, MR에 `Closes 키` → 완료) 반영.
  - 커밋 작성자를 다른 팀원 계정으로 잘못 넣어 푸시했다가 `jedabin` 으로 전부 정정 ([TS-006](TROUBLESHOOTING.md#ts-006)).
- **서비스명 확정 → 패키지 이름 변경** — 임시명 Alzza 대신 서비스명 '한눈'이 정해져 패키지를 `alzza` → `hannun`으로 바꿈(`git mv`로 이력 유지). 명령은 `hannun-ingest`. 로컬 폴더 `Alzza/`는 저장소 루트라 그대로.

### 결정
| 결정 | 이유 |
|---|---|
| 패키지 영문명 `hannun` | '한눈'은 식별자로 못 쓰고, 국어의 로마자 표기법(한=han, 눈=nun)을 따르면 사람마다 다르게 적을 여지가 없음 |
| 우리 데이터 폴더 `data/samples`·`data/gold` → `samples/`·`gold/` | 모노레포 파트 디렉토리 `data/`와 이름이 겹쳐 `data/data/...`가 됨 ([TS-005](TROUBLESHOOTING.md#ts-005)) |
| 전처리(보일러플레이트 제거 등)는 DS1 소유 | 팀 결정. BE 문서의 "DE 실시간 전처리" 범위는 DE와 확인 필요 |
| Gold = "검증·타입 정규화·중복 제거가 끝난 기사 테이블", 원문 `content` 보존 | 전처리는 티켓 100. Gold를 두 번 만들지 않기 위해 원문을 여기 두고 정제 컬럼은 나중에 추가 |
| 저장 포맷 parquet, `published_date`(UTC) 파티션, 파티션당 파일 1개 | STEP 1·3이 시간 윈도우로 읽으므로 날짜 파티션이 자연스러움. HDFS 확정 전까지 로컬 |
| `article_id` 기준 멱등, 기본 `on_conflict=keep` | 같은 파일 재투입 시 결과 불변. 재크롤링 반영은 `--on-conflict replace`로 명시적으로 |
| `published_at` 타임존 없으면 리젝트, 오프셋 있으면 UTC 변환 | 발행 시각이 윈도우 기준. 모호한 값을 받으면 이슈가 잘못 묶임 |
| `article_id`가 BE 해시 규칙과 달라도 리젝트하지 않고 `article_id_verified=False` 기록 | BE가 URL 정규화를 할 수도 있음. 먼저 실측 |
| 이슈 ID 관리는 B안(알고리즘 번호 ↔ 서비스 ID 분리·승계) **MVP 필수**로 격상 | API가 `issueId`를 커서 페이지네이션 키로 사용. 재계산마다 바뀌면 무한스크롤·공유 링크가 깨짐 |

### 다음
- [ ] DE와 확인: HDFS 경로/포맷, DS가 읽는 방식, "실시간 전처리"의 범위
- [ ] BE와 확인: `content`에 HTML 잔존 여부, `article_id` 해시 시 URL 정규화 여부, 일 수집량, GPU
- [ ] PM에 질문: 단독 특종(-1이지만 살린 기사)·격리 기사를 화면에 보여줄 것인가 → STEP 4 범위 결정
- [ ] DS → BE 출력 계약 문서 (issue 테이블 컬럼·score 산식·전달 방식)
- [ ] S15P21E105-100 본문 전처리 규칙 — 실제 기사 샘플 확보가 선행

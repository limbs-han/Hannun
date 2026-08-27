# DS1 — 중복 제거 · 임베딩 · 이슈 군집화

한눈 뉴스 파이프라인에서 기사를 이슈로 묶는 부분을 맡는다. 파이썬 패키지 이름은 `hannun`.
이 디렉토리(`data/ds1/`)가 파이썬 프로젝트 루트다.

```
DE 공통 기사 JSON ──┐
                   ▼
STEP 0  ingest      검증 → Gold(parquet)                          S15P21E105-99  ✔
        preprocess  보일러플레이트 제거·정규화                       S15P21E105-100
STEP 1  dedup       SHA-256 → MinHash/LSH → TF-IDF → Union-Find    S15P21E105-10
STEP 2  embedding   ko-sroberta (제목+리드)                          S15P21E105-11
STEP 3  clustering  UMAP + HDBSCAN + 이슈 ID 승계                    S15P21E105-89/90/97
STEP 4  quality     노이즈 구제 · 어그로 판정 · 화제성 점수            S15P21E105-93/91
                   │
                   ▼
        이슈 테이블(parquet) ── DS2 관점 대조, BE 서빙 DB 가 읽음
```

## 디렉토리

```
src/hannun/ingest/   STEP 0 — schema.py(검증) reader.py(파일 읽기) gold.py(저장소) pipeline.py cli.py
scripts/             보조 스크립트 (샘플 데이터 생성 등)
tests/               pytest
samples/             커밋되는 샘플 입력
gold/                생성물 (gitignore) — articles/published_date=YYYY-MM-DD/articles.parquet, rejects/*.jsonl
docs/WORKLOG.md      날짜별 작업 기록
docs/TROUBLESHOOTING.md  문제 → 원인 → 해결
docs/tickets/        지라 티켓별 해석·결정·미결
CODE_STYLE.md        코드 규칙
```

## 시작하기

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\make_sample_data.py     # 샘플 입력 생성
.\.venv\Scripts\python.exe -m pytest tests/ -v

# 공통 기사 JSON → Gold
.\.venv\Scripts\hannun-ingest.exe --input samples\articles_sample.jsonl --gold-root gold -v
```

Gold 읽기:

```python
from hannun.ingest import GoldStore
df = GoldStore("gold").read(start_date="2026-08-20", end_date="2026-08-21")
```

## 검사

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
.\.venv\Scripts\python.exe -m flake8 . --select=E9,F63,F7,F82,E501 --max-line-length=110 --exclude=.venv,build
```

코드 규칙은 [CODE_STYLE.md](CODE_STYLE.md), git 규칙은 파트 공통 [../docs/GIT_CONVENTION.md](../docs/GIT_CONVENTION.md).

## 문서 규칙

- 작업하면 `docs/WORKLOG.md`에 날짜별로 한 줄 이상 남긴다.
- 막혔다가 해결한 건 `docs/TROUBLESHOOTING.md`에 증상 / 원인 / 해결 / 배운 것 순서로.
- 티켓 시작 시 `docs/tickets/<키>.md`에 해석·입출력·결정·미결을 적고, 끝나면 갱신한다.
- 다른 파트가 읽어야 하는 것(출력 컬럼, 파일 위치)은 여기 말고 `../docs/contracts/`에 쓴다.

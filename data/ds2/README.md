# DS2 Enrichment Dummy Module

DS1에서 전달되는 이슈 데이터를 받아  
DS2 출력 형태로 변환하는 더미 모듈입니다.

현재는 실제 중분류·소분류 알고리즘을 적용하지 않고,
DS1 → DS2 입출력 구조와 스키마 검증만 수행합니다.

## 현재 상태

- DS1 샘플 JSON 입력
- DS1 입력 스키마 검증
- DS2 더미 출력 생성
- DS2 출력 스키마 검증
- 자동 테스트 3개 작성
- `stance`는 현재 `neutral`
- `stance_confidence`는 현재 `null`

## 실행 방법

프로젝트 루트에서 실행합니다.

```bash
python -X utf8 data/ds2/enrich_dummy.py
```

DS1 샘플 데이터의 첫 번째 이슈를 읽어
DS2 더미 출력 결과를 터미널에 출력합니다.

## 테스트 방법

프로젝트 루트에서 실행합니다.

```bash
python -X utf8 data/ds2/tests/test_enrich_dummy.py
```

정상 실행 시:

```text
Ran 3 tests in ...
OK
```

현재 테스트는 정상 입력 처리, 필수 필드 누락,
`stance_confidence` 범위 오류를 확인합니다.

## 참고

현재 `event_name`, `fact_summary`, `stance`,
`viewpoint_analysis` 등은 실제 분석 결과가 아닌 더미값입니다.

향후 실제 중분류·소분류 알고리즘 결과를
현재 출력 구조에 연결할 예정입니다.
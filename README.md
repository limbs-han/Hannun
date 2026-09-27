# 한눈 (S15P21E105)

뉴스를 **이슈로 묶고**, 이슈 안에서 **언론사별 관점(긍정·중립·부정)** 과 **공통 사실**을 한눈에 보여주는 서비스.
13개 언론사 RSS를 15분마다 수집해 자동으로 묶고, 매시간 다시 정리한다.

서비스: https://j15e105.p.ssafy.io

## 어떻게 돌아가나

```
RSS 13사 ─▶ Kafka ─▶ HDFS (원본→정제) ─▶ 이슈 군집·관점 분석 ─▶ Kafka ─▶ MySQL ─▶ 화면
            [DE]       [DE]               [DS1·DS2]            [DE]     [BE]    [FE]
```

서버 두 대. **A**(`j15e105a`)는 수집·저장·분석, **B**(`j15e105`)는 서비스·DB·모니터링·배포.

## 폴더

| 폴더 | 담당 | 시작할 때 볼 것 |
|---|---|---|
| `front/` | FE | `front/README.md` |
| `back/` | BE | `back/README.md`, `back/deploy/` |
| `data/de/` | DE | `data/de/infra/README.md`, `data/docs/ec2-a-access.md` |
| `data/ds/` | DS1·DS2 | `data/ds/README.md`, `data/ds/docs/ds1/EC2_RUNBOOK.md` |
| `data/docs/` | 데이터 파트 공통 | 브랜치·커밋 규칙, 파트 간 데이터 계약 |
| `infra/` | 전체 | `Jenkinsfile` — `develop` 머지 시 자동 배포 |
| `exec/` | 전체 | **포팅 매뉴얼** — 처음부터 다시 올리는 법, 외부 서비스, DB 덤프, 시연 순서 |

## 처음 클론했다면

1. 자기 파트 폴더의 README부터
2. 서버에 올려야 하면 `exec/01_빌드_및_배포.md`
3. 브랜치는 자기 파트 dev(`front/dev`·`back/dev`·`data/dev`)에서 따고 거기로 MR. 이름·커밋·MR 규칙은 `data/docs/GIT_CONVENTION.md`

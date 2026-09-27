# 포팅 매뉴얼 (S15P21E105 · 한눈)

SSAFY 15기 특화 프로젝트 산출물. GitLab 소스를 클론한 뒤 빌드·배포할 수 있게 정리했다.
기준일 2026-09-23. 모든 버전과 경로는 리포 파일 또는 운영 서버에서 실측한 값이다.
확인하지 못한 항목은 `[담당자 확인]`으로 남겼다.

| 파일 | 내용 (사무국 안내 항목) |
|---|---|
| [01_빌드_및_배포.md](01_빌드_및_배포.md) | 1. 제품·버전 / 빌드 환경변수 / 배포 특이사항 / 설정·계정 파일 목록 |
| [02_외부_서비스.md](02_외부_서비스.md) | 2. 외부 서비스 가입·활용 정보 |
| [03_DB_덤프.md](03_DB_덤프.md) | 3. DB 덤프 생성 방법과 파일 위치 (`db/`) |
| [04_시연_시나리오.md](04_시연_시나리오.md) | 4. 화면별·클릭별 시연 순서 |

## 전체 구조 한 장

```
                    ┌──────────── EC2 B  j15e105.p.ssafy.io (서비스) ─────────────┐
 사용자 ── HTTPS ──▶ nginx 1.24 ─┬─ /        정적 Vue 빌드 (/var/www/news-front)     │
                    │           └─ /api/    ─▶ Spring Boot ×2 (blue|green, 8080~8083) │
                    │                              │ JPA          │ Kafka 소비·발행     │
                    │                           MySQL 8.0      Kafka 4.2.1 ×3 (KRaft)  │
                    │                           Redis 7        Prometheus·Grafana·Pushgateway
                    │  Jenkins 2.568 (:8089, nginx :9443) ── develop 머지 → infra/Jenkinsfile
                    └───────────────────────────────────────────────────────────────┘
                                   ▲ news.article.raw            │ news.clustering.completed
                                   │ (크롤러 발행)                ▼ (DE 발행)
                    ┌──────────── EC2 A  j15e105a.p.ssafy.io (데이터) ───────────────┐
                    │ Airflow 2.10.4 ─ 크롤러(RSS 13사) ─ Spark 3.5.4 ─ HDFS 3.4.1     │
                    │   bronze → silver(Iceberg 1.9.1) → ds_input                     │
                    │ DS 체인 (hannun-ds 컨테이너) : 중복제거·임베딩·군집·관점 → ds_output│
                    │   gold_issue_feed → Kafka 발행                                  │
                    │ Pinpoint(web·collector·hbase) — BE 앱 에이전트가 여기로 트레이스 │
                    └───────────────────────────────────────────────────────────────┘
```

리포 구조: `front/`(FE) · `back/`(BE) · `data/de/`(DE) · `data/ds/`(DS1·DS2) · `infra/`(Jenkinsfile).
파트별 dev 브랜치 `front/dev` · `back/dev` · `data/dev` → `develop` → `master`.

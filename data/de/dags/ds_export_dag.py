"""DS 입력 내려주기 DAG (DS 연동).

silver 를 DS 가 읽는 로컬 JSONL 로 풀어준다. 03:00 새벽 정비가 끝난 뒤인 04:00 KST 에
돌려, 파일 합치기와 silver 갱신이 안정된 상태를 내보낸다.

최근 3일을 다시 내리는 이유: 지난 날짜 파티션에도 기사가 뒤늦게 추가된다 (RSS 가 며칠 전
기사를 준다). 같은 날짜를 다시 써도 안전하고 하루치가 수십 MB 라 비용이 작다.

DS 단계(hannun-ingest 이후)는 이 DAG 뒤에 붙일 자리다 — stance·enrichment 의 명령어와
실행 환경 격리 방식이 정해지면 태스크로 이어 붙인다.
"""

from datetime import datetime

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

# Spark 드라이버가 airflow 컨테이너 안에서 돌아 메모리가 6GB 로 한정된다. 두 잡이 겹치면
# 상한에 닿고, silver 를 덮어쓰는 중에 읽는 사고도 난다. 자리 하나짜리 대기줄에 세워
# 한 번에 하나만 돌게 한다 (대기줄 만들기는 infra/README 참고)
SPARK_POOL = "spark_local"

KST = pendulum.timezone("Asia/Seoul")

with DAG(
    dag_id="ds_export",
    start_date=datetime(2026, 9, 8, tzinfo=KST),
    schedule="0 4 * * *",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["ds"],
) as dag:
    BashOperator(
        task_id="silver_to_ds_input",
        pool=SPARK_POOL,
        # 날짜 계산은 잡이 한국 날짜로 직접 한다 — Airflow 템플릿으로 시간대를 넘기면 하루 밀린다
        bash_command=(
            "spark-submit --master 'local[*]' --driver-memory 2g "
            "/opt/airflow/jobs/silver_to_ds_input.py --recent 3"
        ),
    )

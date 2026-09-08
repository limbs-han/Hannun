"""새벽 정비 DAG — bronze 파일 합치기와 B 서버 백업 (S15P21E105-74).

15분 배치가 남긴 하루 200여 개 파일을 1개로 합치고, 그 결과를 B 서버로 백업한다.
합치기가 실패하면 백업하지 않는다 — 온전하지 않은 상태를 백업해 두면 복구가 더 어렵다.
시각은 KST 다 (compose 의 AIRFLOW__CORE__DEFAULT_TIMEZONE).
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
    dag_id="nightly_maintenance",
    start_date=datetime(2026, 9, 8, tzinfo=KST),
    schedule="0 3 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["bronze", "backup"],
) as dag:
    # 어제 파티션이 대상이다. 잡·스크립트가 기본값으로 어제를 쓰므로 날짜를 넘기지 않는다
    compact = BashOperator(
        task_id="compact_bronze",
        pool=SPARK_POOL,
        bash_command=(
            "spark-submit --master 'local[*]' --driver-memory 2g "
            "/opt/airflow/jobs/compact_bronze.py"
        ),
    )
    backup = BashOperator(
        task_id="backup_to_b",
        bash_command="python /opt/airflow/jobs/backup_to_b.py",
    )
    compact >> backup

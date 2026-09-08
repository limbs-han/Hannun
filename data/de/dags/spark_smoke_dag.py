"""Airflow→Spark→HDFS 전 구간 검증용 수동 트리거 DAG.

실전 DAG(15분 배치 S15P21E105-73, 적재 잡 -66)은 별도 이슈에서 작성한다.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

# Spark 드라이버가 airflow 컨테이너 안에서 돌아 메모리가 6GB 로 한정된다. 두 잡이 겹치면
# 상한에 닿고, silver 를 덮어쓰는 중에 읽는 사고도 난다. 자리 하나짜리 대기줄에 세워
# 한 번에 하나만 돌게 한다 (대기줄 만들기는 infra/README 참고)
SPARK_POOL = "spark_local"

with DAG(
    dag_id="spark_smoke",
    start_date=datetime(2026, 8, 1),
    schedule=None,  # 수동 트리거 전용
    catchup=False,
    is_paused_upon_creation=False,  # 기본 paused 면 트리거해도 queued 에 머묾
    tags=["smoke"],
) as dag:
    BashOperator(
        task_id="hdfs_roundtrip",
        pool=SPARK_POOL,
        bash_command="spark-submit --master 'local[*]' /opt/airflow/jobs/hdfs_smoke.py",
    )

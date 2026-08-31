"""Airflow→Spark→HDFS 전 구간 검증용 수동 트리거 DAG.

실전 DAG(15분 배치 S15P21E105-73, 적재 잡 -66)은 별도 이슈에서 작성한다.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

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
        bash_command="spark-submit --master 'local[*]' /opt/airflow/jobs/hdfs_smoke.py",
    )

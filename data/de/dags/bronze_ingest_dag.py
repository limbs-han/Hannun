"""Kafka → HDFS bronze 15분 적재 DAG (S15P21E105-66).

전 구간 신선도 목표(S15P21E105-73)의 적재 구간을 담당한다.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="bronze_ingest",
    start_date=datetime(2026, 9, 1),
    schedule="*/15 * * * *",
    catchup=False,
    max_active_runs=1,  # 체크포인트 동시 접근 금지 — 이전 실행이 밀리면 다음은 대기
    is_paused_upon_creation=False,
    tags=["bronze"],
) as dag:
    BashOperator(
        task_id="kafka_to_bronze",
        bash_command=(
            "spark-submit --master 'local[*]' "
            "--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4 "
            "/opt/airflow/jobs/kafka_to_bronze.py"
        ),
    )

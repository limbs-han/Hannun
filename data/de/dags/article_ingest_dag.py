"""Kafka → HDFS bronze → silver → DS 입력 15분 DAG (S15P21E105-66, -68, -118).

전 구간 신선도 목표(S15P21E105-73)의 적재·정형화 구간을 담당한다. bronze 적재가
끝나면 이어서 오늘·어제 적재분을 silver 에 반영하고, 갱신된 silver 를 DS 입력으로
내린다 (한 DAG 라 동시 실행이 없다).

내려주기가 여기 붙은 이유: silver 가 갱신된 직후여야 헛일이 없다. 따로 15분 DAG 를
두면 대기줄을 다투다가 silver 갱신 전에 내려가는 일이 생긴다.

이름이 bronze_ingest 였다가 bronze 만 다루지 않게 되어 바꿨다. 실시간분만 담당하고,
과거 데이터 재구축은 bronze_to_silver.py --full 수동 실행이다.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

# Spark 드라이버가 airflow 컨테이너 안에서 돌아 메모리가 6GB 로 한정된다. 두 잡이 겹치면
# 상한에 닿고, silver 를 덮어쓰는 중에 읽는 사고도 난다. 자리 하나짜리 대기줄에 세워
# 한 번에 하나만 돌게 한다 (대기줄 만들기는 infra/README 참고)
SPARK_POOL = "spark_local"

with DAG(
    dag_id="article_ingest",
    start_date=datetime(2026, 9, 1),
    schedule="*/15 * * * *",
    catchup=False,
    max_active_runs=1,  # 체크포인트 동시 접근 금지 — 이전 실행이 밀리면 다음은 대기
    is_paused_upon_creation=False,
    tags=["bronze", "silver"],
) as dag:
    kafka_to_bronze = BashOperator(
        task_id="kafka_to_bronze",
        pool=SPARK_POOL,
        bash_command=(
            "spark-submit --master 'local[*]' "
            "--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.4 "
            "/opt/airflow/jobs/kafka_to_bronze.py"
        ),
    )
    bronze_to_silver = BashOperator(
        task_id="bronze_to_silver",
        pool=SPARK_POOL,
        bash_command=(
            "spark-submit --master 'local[*]' --driver-memory 3g "
            "/opt/airflow/jobs/bronze_to_silver.py"
        ),
    )
    # silver 가 갱신된 직후 DS 입력을 내린다. 하루 한 번에서 15분마다로 옮겼다
    # (S15P21E105-118) — DS 가 15분 배정 루프를 붙일 수 있게 하는 조건이다.
    # 하루 한 파일 불변식은 그대로고, os.replace 로 원자적으로 갈아치우므로 DS 가
    # 읽는 중에 덮어도 열려 있던 파일은 온전하다
    silver_to_ds_input = BashOperator(
        task_id="silver_to_ds_input",
        pool=SPARK_POOL,
        bash_command=(
            "spark-submit --master 'local[*]' --driver-memory 2g "
            "/opt/airflow/jobs/silver_to_ds_input.py --sync"
        ),
    )

    kafka_to_bronze >> bronze_to_silver >> silver_to_ds_input

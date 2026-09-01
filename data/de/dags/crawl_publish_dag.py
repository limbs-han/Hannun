"""기사 수집→Kafka 발행 15분 DAG (S15P21E105-73).

생성 직후에는 일시정지 상태다 — 백필 송신이 끝난 뒤 UI 토글로 켠다.
켜면 15분마다 언론사 RSS·본문 요청이 실제로 나간다.
"""

from datetime import datetime

from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="crawl_publish",
    start_date=datetime(2026, 9, 1),
    schedule="*/15 * * * *",
    catchup=False,
    max_active_runs=1,  # seen.sqlite 동시 접근 금지 + 수집 예절
    tags=["crawl"],
) as dag:
    BashOperator(
        task_id="crawl_publish",
        # python -m 은 현재 폴더를 임포트 경로에 올리므로 /opt/airflow 로 이동해
        # 마운트된 crawler 패키지를 찾는다
        bash_command=(
            "cd /opt/airflow && "
            "python -m crawler.pipeline /opt/airflow/state/seen.sqlite"
        ),
    )

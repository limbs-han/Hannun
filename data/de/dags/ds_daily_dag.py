"""DS 사슬과 gold 이슈 피드 DAG (S15P21E105-69, -118).

DS 사슬(ds_chain DAG)을 켜고 그 산출물을 gold 이슈 피드로 합친다.

하루 한 번이다. 사슬이 9분 걸리고 이슈 번호를 매번 다시 배정해서 자주 돌릴 수 없다.
15분마다 돌리면 번호가 계속 바뀌어 DS2 가 따라오지 못한다.

DS 입력 내려주기는 article_ingest DAG 가 15분마다 한다(S15P21E105-118). silver 가 갱신된
직후에 내려가므로 이 DAG 가 시작할 때 입력은 이미 최신이다. 옛 ds_export DAG 가 셋을 다
갖고 있었고, 그 파일은 꺼진 채 남아 있다.
"""

from datetime import datetime, timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

# Spark 드라이버가 airflow 컨테이너 안에서 돌아 메모리가 6GB 로 한정된다. 두 잡이 겹치면
# 상한에 닿는다. 자리 하나짜리 대기줄에 세워 한 번에 하나만 돌게 한다
SPARK_POOL = "spark_local"

KST = pendulum.timezone("Asia/Seoul")

with DAG(
    dag_id="ds_daily",
    start_date=datetime(2026, 9, 10, tzinfo=KST),
    schedule="0 4 * * *",  # 03:00 새벽 정비가 끝난 뒤
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["ds", "gold"],
) as dag:
    # 사슬은 DS 소유 DAG 에 있다. 여기서 켜고 끝날 때까지 기다린다 — 순서는 이 DAG 하나에
    # 드러나고, 사슬 내용이 바뀌어도 이 파일은 열지 않는다.
    # reset_dag_run: 이 DAG 를 다시 돌릴 때 같은 날짜의 사슬 실행이 남아 있으면 트리거가
    # 거부된다. 지우고 다시 만들게 해 재실행이 막히지 않게 한다
    chain = TriggerDagRunOperator(
        task_id="ds_chain",
        trigger_dag_id="ds_chain",
        wait_for_completion=True,
        poke_interval=60,
        reset_dag_run=True,
        execution_timeout=timedelta(hours=2),
    )

    # DS 산출물 세 표를 BE 가 받는 모양으로 합쳐 gold 에 쌓는다. 창을 주지 않으면 방금
    # 사슬이 만든 가장 늦은 창을 쓴다 (S15P21E105-69)
    gold = BashOperator(
        task_id="gold_issue_feed",
        pool=SPARK_POOL,
        bash_command=(
            "spark-submit --master 'local[*]' --driver-memory 2g "
            "/opt/airflow/jobs/gold_issue_feed.py"
        ),
    )

    # 발행(publish_clustering)은 아직 붙이지 않는다. DS2 관점 라벨이 비어 있어 BE 필수
    # 필드를 채우지 못하고, 운영 토픽으로 보내기 전에 건수를 확인받는 규칙이 있다.
    # 첫 발행을 손으로 한 뒤 여기에 이어 붙인다 (S15P21E105-69)
    chain >> gold

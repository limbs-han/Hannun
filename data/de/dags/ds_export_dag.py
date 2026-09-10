"""DS 입력 내려주기 DAG (DS 연동).

silver 를 DS 가 읽는 로컬 JSONL 로 풀어준다. 03:00 새벽 정비가 끝난 뒤인 04:00 KST 에
돌려, 파일 합치기와 silver 갱신이 안정된 상태를 내보낸다.

내려주는 날짜는 고정된 최근 며칠이 아니라 silver 가 파일보다 새로운 날짜 전부다. RSS 가
몇 달 전 기사를 뒤늦게 주면 그 옛 날짜의 silver 가 갱신되는데, 창을 며칠로 고정하면 그
기사는 DS 에게 영구히 가지 않는다.

내려주기가 끝나면 DS 사슬(ds_chain DAG)을 켜고, 그 산출물을 gold 이슈 피드로 합친다.
04:30 고정(cron)보다 안전한 이유: 내려주기가 늦어져도 옛 입력을 읽는 일이 없다.
"""

from datetime import datetime, timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

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
    export = BashOperator(
        task_id="silver_to_ds_input",
        pool=SPARK_POOL,
        bash_command=(
            "spark-submit --master 'local[*]' --driver-memory 2g "
            "/opt/airflow/jobs/silver_to_ds_input.py --sync"
        ),
    )

    # 사슬은 DS 소유 DAG(ds_chain)에 있다. 여기서 켜고 끝날 때까지 기다린다 — 순서는
    # 이 DAG 하나에 드러나고, 사슬 내용이 바뀌어도 이 파일은 열지 않는다.
    # reset_dag_run: 이 DAG 를 다시 돌릴 때 같은 날짜의 사슬 실행이 남아 있으면
    # 트리거가 거부된다. 지우고 다시 만들게 해 재실행이 막히지 않게 한다
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
    export >> chain >> gold

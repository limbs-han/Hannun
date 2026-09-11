"""gold 이슈 피드 DAG (S15P21E105-69).

DS 사슬 산출물을 BE 가 받는 모양으로 합쳐 gold 에 쌓는다.

**사슬 트리거를 뺐다 (2026-09-11).** ds_chain 이 스스로 15분마다 돌게 바뀌어
(S15P21E105-102) 여기서 또 부르면 중복이다. reset_dag_run 도 함께 뺐다 — 같은 시각의
15분 실행을 지우고 다시 만들 위험이 있었다.

**돌 시각은 아직 정하지 못했다.** 사슬 실행이 15~17분인데 주기가 15분이라 끝난 다음 초에
다음 실행이 시작된다. 쉬는 틈이 없어 gold 가 끼어들면 사슬이 덮어쓰는 중인 parquet 를
읽는다. 창은 window_start 하나를 계속 덮으므로 한 창 뒤처져 읽는 방법도 없다.

DS 쪽에서 둘 중 하나가 정해지면 그때 스케줄을 붙인다.

- 사슬 주기를 20분 이상으로 늘려 틈을 만든다
- 사슬이 산출물을 임시 폴더에 쓴 뒤 이름을 바꿔 읽는 쪽이 언제나 온전한 것을 본다

그때까지는 꺼진 채 두고 손으로 돌린다. DS 입력 내려주기는 article_ingest DAG 가 15분마다
한다(S15P21E105-118).
"""

from datetime import datetime

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

# Spark 드라이버가 airflow 컨테이너 안에서 돌아 메모리가 6GB 로 한정된다. 두 잡이 겹치면
# 상한에 닿는다. 자리 하나짜리 대기줄에 세워 한 번에 하나만 돌게 한다
SPARK_POOL = "spark_local"

KST = pendulum.timezone("Asia/Seoul")

with DAG(
    dag_id="ds_daily",
    start_date=datetime(2026, 9, 10, tzinfo=KST),
    schedule=None,  # 돌 시각 미정 — 위 docstring 참고
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,  # 사슬이 쉬는 틈이 정해질 때까지 꺼 둔다
    tags=["ds", "gold"],
) as dag:
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
    # 태스크가 하나뿐이라 잇는 줄이 없다

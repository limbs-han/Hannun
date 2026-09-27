"""gold 이슈 피드 DAG — 매시 :27 :42 :57 (S15P21E105-69).

DS 사슬 산출물을 BE 가 받는 모양으로 합쳐 gold 에 쌓는다. DS2 관점 결과도 여기서 붙는다.

**시각을 이렇게 고른 이유.** DS 쪽이 하이브리드 주기다(S15P21E105-102). ds_chain 이
매시 :05 에 전체 재군집을 하고 :18 쯤 끝나며, ds_assign 이 :20 :35 :50 에 새 기사를 기존
이슈에 붙이고 2~3분 걸린다. 둘 다 끝에 DS2 내보내기까지 돌아 ds_output 이 15분마다
갱신된다. gold 는 각 배정이 끝난 뒤, 다음 배정 전에 돌아야 쓰는 중인 parquet 를 읽지
않는다. 배정이 flock 으로 최대 4분 기다릴 수 있어 :25 는 빡빡하고 :27 이면 여유가 있다.

**시간표로 붙인 것은 타협이다.** 정석은 배정 DAG 끝에서 이 DAG 를 트리거하는 이어받기다.
DS 가 주기를 실측으로 조정하는 중이라(15분 → 매시 → 하이브리드) 지금 묶으면 양쪽이 같이
흔들린다. DS 주기가 확정되면 트리거로 바꾼다.

사슬 트리거는 2026-09-11 에 뺐다. ds_chain 이 스스로 돌게 되어 중복이었다.
DS 입력 내려주기는 article_ingest DAG 가 15분마다 한다(S15P21E105-118).
"""

from datetime import datetime, timedelta

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
    schedule="27,42,57 * * * *",  # 각 배정 뒤, 다음 배정 전
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["ds", "gold"],
) as dag:
    # DS 산출물 세 표를 BE 가 받는 모양으로 합쳐 gold 에 쌓는다. 창을 주지 않으면 방금
    # 사슬이 만든 가장 늦은 창을 쓴다 (S15P21E105-69)
    gold = BashOperator(
        task_id="gold_issue_feed",
        pool=SPARK_POOL,
        # 실측 29초. 길어져 다음 배정(:35)과 겹치기 전에 끊는다. 덮어쓰기는 커밋 전
        # 중단이면 옛 파티션이 그대로라 안전하다
        execution_timeout=timedelta(minutes=5),
        bash_command=(
            "spark-submit --master 'local[*]' --driver-memory 2g "
            "/opt/airflow/jobs/gold_issue_feed.py"
        ),
    )

    # gold 표를 BE 토픽으로 발행한다. DS2 관점 라벨이 채워져(2026-09-18 확인) 필수 필드
    # 점검을 통과하므로 목업 옵션 없이 보낸다.
    #
    # **기본값은 시험 실행이다.** 머지만으로 운영 토픽에 자동 발행이 시작되면 안 된다.
    # 건수를 확인받은 뒤 .env 에 PUBLISH_MODE=send 를 넣고 컨테이너를 다시 만들어 켠다.
    # 되돌리기는 그 줄을 지우는 것이다.
    #
    # 대기줄에 세우지 않는다 — Spark 를 쓰지 않고 WebHDFS 로 읽어 가볍다.
    # 날짜는 gold 파티션과 같아야 하므로 한국 날짜를 준다 (gold 잡도 한국 날짜로 쓴다)
    publish = BashOperator(
        task_id="publish_clustering",
        # 이슈 411개를 초당 50건으로 보내면 9초다. 늦어지면 다음 배정 전에 끊는다
        execution_timeout=timedelta(minutes=5),
        bash_command=(
            "python /opt/airflow/jobs/publish_clustering.py "
            "$(TZ=Asia/Seoul date +%F) --${PUBLISH_MODE:-dry-run}"
        ),
    )

    gold >> publish

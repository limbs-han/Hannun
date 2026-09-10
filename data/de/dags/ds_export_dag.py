"""DS 입력 내려주기 DAG (DS 연동).

silver 를 DS 가 읽는 로컬 JSONL 로 풀어준다. 03:00 새벽 정비가 끝난 뒤인 04:00 KST 에
돌려, 파일 합치기와 silver 갱신이 안정된 상태를 내보낸다.

내려주는 날짜는 고정된 최근 며칠이 아니라 silver 가 파일보다 새로운 날짜 전부다. RSS 가
몇 달 전 기사를 뒤늦게 주면 그 옛 날짜의 silver 가 갱신되는데, 창을 며칠로 고정하면 그
기사는 DS 에게 영구히 가지 않는다.

DS 일일 체인(S15P21E105-101)이 뒤에 붙어 있다 — 실행 환경이 도커 이미지(hannun-ds)로
확정돼 내려주기 완료 직후 이어 돌린다. 04:30 고정(cron)보다 안전한 이유: 내려주기가
늦어져도 옛 입력을 읽는 일이 없다.
"""

from datetime import datetime, timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

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

    # DS 일일 체인 — 호스트에 ssh 로 들어가 hannun-ds 컨테이너를 돌린다.
    # docker.sock 마운트 대신 ssh 인 이유: 소켓은 사실상 서버 관리자 권한이라
    # (compose 의 UI 포트 주석) ubuntu 권한으로 한정하고, backup_to_b 와 같은
    # 검증된 키 패턴(uid 50000 마운트)을 재사용한다. flock 은 cron 폴백과의
    # 동시 기동 방지 — 체인 자체는 멱등이라 겹쳐도 데이터는 안전하다.
    chain = BashOperator(
        task_id="hannun_daily_chain",
        retries=1,
        retry_delay=timedelta(minutes=20),
        execution_timeout=timedelta(hours=2),
        bash_command=(
            "ssh -i /opt/airflow/.ssh/hannun.pem"
            " -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
            " ubuntu@host.docker.internal"
            " 'set -o pipefail; flock -n /tmp/hannun_chain.lock"
            " docker run --rm -u 1000:1000"
            " -v $HOME/gold:/data/gold -v $HOME/ds_input:/data/ds_input"
            " -v $HOME/.cache/huggingface:/data/hf_cache hannun-ds"
            " 2>&1 | tee -a $HOME/hannun_chain.log'"
        ),
    )

    export >> chain

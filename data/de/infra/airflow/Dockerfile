# Airflow + Spark(local) + 크롤러 실행 이미지.
# Spark 클러스터를 따로 두지 않는다 — DAG 태스크가 spark-submit --master local[*] 로
# 이 컨테이너 안에서 드라이버를 돌리고, HDFS 에는 compose 네트워크로 접속한다.
FROM apache/airflow:2.10.4

# Spark 실행에 JVM 필수
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

USER airflow
# 크롤러 의존성(requirements.txt) + Spark. 빌드 컨텍스트는 data/de
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt pyspark==3.5.4

# 크롤러 상태(seen.sqlite) 자리. 이미지에 airflow 소유로 만들어 둬야
# 이름 있는 볼륨이 첫 마운트에서 소유권을 이어받아 쓰기가 된다
RUN mkdir /opt/airflow/state

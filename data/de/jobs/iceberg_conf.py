"""Iceberg 카탈로그 설정 (S15P21E105-126).

전역 spark-defaults.conf 에 넣지 않는다. `spark.sql.extensions` 가 켜져 있는데 Iceberg
jar 이 classpath 에 없으면 SparkSession 생성 자체가 실패해서, 아직 Iceberg 를 쓰지 않는
잡까지 한꺼번에 죽는다. 쓰는 잡만 이 함수를 부르고 그 잡의 spark-submit 에만
`--packages` 를 준다.

카탈로그 이름은 `ice`, 창고는 `/lake/iceberg` 다. 옛 파케이(`/lake/silver/news`)를
그대로 두고 옆에 짓기 위해 경로를 나눈다. 하둡 카탈로그는 테이블 위치가 곧 정체성이라
나중에 옮길 수 없으므로, 처음부터 최종 자리인 `/lake/iceberg/<층>/<종류>` 로 둔다.

  spark-submit --master local[*] \
    --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.9.1 \
    jobs/iceberg_smoke.py
"""

import os

CATALOG = os.environ.get("ICEBERG_CATALOG", "ice")
WAREHOUSE = os.environ.get("ICEBERG_WAREHOUSE", "hdfs://namenode:8020/lake/iceberg")

EXTENSIONS = "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions"


def configure(builder):
    """SparkSession.builder 에 Iceberg 카탈로그를 붙인다."""
    return (
        builder
        .config("spark.sql.extensions", EXTENSIONS)
        .config(f"spark.sql.catalog.{CATALOG}", "org.apache.iceberg.spark.SparkCatalog")
        .config(f"spark.sql.catalog.{CATALOG}.type", "hadoop")
        .config(f"spark.sql.catalog.{CATALOG}.warehouse", WAREHOUSE)
    )

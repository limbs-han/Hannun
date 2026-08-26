-- mysqld_exporter용 모니터링 전용 계정
-- 주의: MySQL 컨테이너가 "빈 데이터 디렉터리"로 최초 기동될 때만 자동 실행됨(docker-entrypoint-initdb.d).
-- 이미 떠 있는 volume에는 적용 안 되므로, 기존 컨테이너에는 docker exec로 동일 SQL을 한 번 수동 실행해야 함.
CREATE USER IF NOT EXISTS 'exporter'@'%' IDENTIFIED BY 'exporterpass' WITH MAX_USER_CONNECTIONS 3;
GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'exporter'@'%';
FLUSH PRIVILEGES;

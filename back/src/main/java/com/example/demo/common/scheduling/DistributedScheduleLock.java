package com.example.demo.common.scheduling;

import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.Duration;

// 앱을 여러 인스턴스로 띄우면 @Scheduled는 인스턴스마다 각자 따로 실행됨(스프링 스케줄러는 인스턴스 로컬이라
// 서로의 존재를 모름). 같은 작업이 여러 번 겹쳐 돌면 안 되는 크론(예: 감쇠처럼 "정확히 주기당 한 번"이 의미
// 있는 작업)은 이 락으로 감싸서, 그 tick에 딱 한 인스턴스만 실제로 실행하게 함.
// SETNX(존재 안 할 때만 SET) + TTL 하나로 충분 — TTL이 "락 못 풀고 죽었을 때" 대비 안전장치 역할까지 함.
@Component
public class DistributedScheduleLock {

    private static final String KEY_PREFIX = "schedule-lock:";
    private static final String LOCKED = "1";

    private final StringRedisTemplate redisTemplate;

    public DistributedScheduleLock(StringRedisTemplate redisTemplate) {
        this.redisTemplate = redisTemplate;
    }

    /**
     * 이번 tick에 이 인스턴스가 jobName을 실행해도 되면 true(락 획득 성공), 다른 인스턴스가 이미 실행 중이면 false.
     * ttl은 그 작업이 걸릴 수 있는 최대 시간보다 넉넉하게 잡아서, 정상 종료 여부와 상관없이 다음 tick 전에는 풀리게 함.
     */
    public boolean tryAcquire(String jobName, Duration ttl) {
        Boolean acquired = redisTemplate.opsForValue().setIfAbsent(KEY_PREFIX + jobName, LOCKED, ttl);
        return Boolean.TRUE.equals(acquired);
    }
}

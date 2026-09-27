package com.example.demo.issue.service;

import com.example.demo.common.scheduling.DistributedScheduleLock;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;

@Slf4j
@Component
public class SearchPopularityAggregator {

    private static final String KEY = "search:popular";

    // 15분마다 ×0.9 감쇠 -> 한 번 검색되고 더 안 나오면 대략 1시간 45분~2시간 뒤 PRUNE_THRESHOLD 밑으로 떨어져서 제거됨.
    private static final double DECAY_FACTOR = 0.9;
    private static final double PRUNE_THRESHOLD = 0.5;

    private static final String DECAY_SCRIPT = """
            local entries = redis.call('ZRANGE', KEYS[1], 0, -1, 'WITHSCORES')
            local removed = 0
            for i = 1, #entries, 2 do
                local member = entries[i]
                local score = tonumber(entries[i + 1]) * tonumber(ARGV[1])
                if score < tonumber(ARGV[2]) then
                    redis.call('ZREM', KEYS[1], member)
                    removed = removed + 1
                else
                    redis.call('ZADD', KEYS[1], score, member)
                end
            end
            return removed
            """;

    private static final Duration LOCK_TTL = Duration.ofMinutes(5);

    private final StringRedisTemplate redisTemplate;
    private final DefaultRedisScript<Long> decayScript;
    private final DistributedScheduleLock scheduleLock;

    public SearchPopularityAggregator(StringRedisTemplate redisTemplate, DistributedScheduleLock scheduleLock) {
        this.redisTemplate = redisTemplate;
        this.scheduleLock = scheduleLock;
        this.decayScript = new DefaultRedisScript<>(DECAY_SCRIPT, Long.class);
    }

    public void increment(String keyword) {
        redisTemplate.opsForZSet().incrementScore(KEY, keyword, 1);
    }

    public List<String> getPopularKeywords(int size) {
        Set<String> top = redisTemplate.opsForZSet().reverseRange(KEY, 0, size - 1);
        return top == null ? List.of() : new ArrayList<>(top);
    }

    @Scheduled(cron = "0 */15 * * * *")
    public void decay() {
        if (!scheduleLock.tryAcquire("searchPopularityDecay", LOCK_TTL)) {
            return;
        }
        Long removed = redisTemplate.execute(decayScript, List.of(KEY),
                String.valueOf(DECAY_FACTOR), String.valueOf(PRUNE_THRESHOLD));
        log.info("인기 검색어 감쇠 실행: {}개 제거", removed);
    }
}

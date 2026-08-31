package com.example.demo.common.cache;

import com.example.demo.issue.dto.IssueDetailResponse;
import com.example.demo.issue.dto.IssueFeedResponse;
import com.example.demo.issue.service.IssueQueryService;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.BatchStrategies;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.cache.RedisCacheWriter;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.JacksonJsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;
import org.springframework.data.redis.serializer.StringRedisSerializer;
import tools.jackson.databind.ObjectMapper;

import java.time.Duration;

@Configuration
@EnableCaching
public class RedisCacheConfig {

    private static final Duration DEFAULT_TTL = Duration.ofMinutes(18);
    private static final int SCAN_BATCH_SIZE = 100;

    // TODO: sync=true(스탬피드 방지)는 나중에 locking writer(RedisCacheWriter.lockingRedisCacheWriter)로 같이 적용 예정.
    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory connectionFactory, ObjectMapper objectMapper) {
        RedisCacheWriter writer = RedisCacheWriter.create(connectionFactory,
                configurer -> configurer.batchStrategy(BatchStrategies.scan(SCAN_BATCH_SIZE)).collectStatistics());
        return RedisCacheManager.builder(writer)
                .withCacheConfiguration(IssueQueryService.ISSUE_FEED_CACHE, cacheConfig(objectMapper, IssueFeedResponse.class))
                .withCacheConfiguration(IssueQueryService.ISSUE_DETAIL_CACHE, cacheConfig(objectMapper, IssueDetailResponse.class))
                .build();
    }

    private <T> RedisCacheConfiguration cacheConfig(ObjectMapper objectMapper, Class<T> type) {
        return RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(DEFAULT_TTL)
                .disableCachingNullValues()
                .serializeKeysWith(RedisSerializationContext.SerializationPair.fromSerializer(new StringRedisSerializer()))
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(
                        new JacksonJsonRedisSerializer<>(objectMapper, type)));
    }
}

package com.example.demo.issue.service;

import com.example.demo.article.repository.ArticleClusterAggregate;
import com.example.demo.article.service.ArticleQueryService;
import com.example.demo.common.scheduling.DistributedScheduleLock;
import com.example.demo.issue.domain.Issue;
import com.example.demo.issue.repository.IssueRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Caching;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;

@Slf4j
@Service
@Transactional
@RequiredArgsConstructor
public class IssueCommandService {

    private static final Duration ACTIVE_WINDOW = Duration.ofDays(2);
    private static final Duration LOCK_TTL = Duration.ofMinutes(5);

    private final IssueRepository issueRepository;
    private final ArticleQueryService articleQueryService;
    private final DistributedScheduleLock scheduleLock;

    // 컨슈머가 관점그룹/기사 배정 작업을 하기 전에 먼저 호출 — 오래된 메시지면 그 작업 자체를 스킵시키기 위함.
    // clusterId가 아예 처음이면(신규 이슈) 비교 대상이 없으니 항상 통과.
    public boolean isNewerThanStored(Long clusterId, OffsetDateTime clusteredAt) {
        return issueRepository.findById(clusterId)
                .map(issue -> !issue.isStale(clusteredAt))
                .orElse(true);
    }

    @Caching(evict = {
            @CacheEvict(cacheNames = IssueQueryService.ISSUE_FEED_CACHE, allEntries = true),
            @CacheEvict(cacheNames = IssueQueryService.ISSUE_DETAIL_CACHE, key = "#clusterId + ':positive:0'"),
            @CacheEvict(cacheNames = IssueQueryService.ISSUE_DETAIL_CACHE, key = "#clusterId + ':neutral:0'"),
            @CacheEvict(cacheNames = IssueQueryService.ISSUE_DETAIL_CACHE, key = "#clusterId + ':negative:0'")
    })
    public void applyClusteringResult(Long clusterId, String category, String factSummary,
                                       List<String> commonFactsBriefing, OffsetDateTime clusteredAt) {
        ArticleClusterAggregate aggregate = articleQueryService.aggregateByClusterId(clusterId);
        if (aggregate.articleCount() == null || aggregate.articleCount() == 0) {
            // 클러스터가 참조하는 링크가 전부 우리 DB에 없는 경우(백필 누락분 등) - 재시도해도 똑같이
            // 실패하는 영구적인 상황이라 DLQ로 보낼 이유가 없음. 그냥 이 이슈 생성/갱신만 건너뜀.
            log.warn("clusterId={} 이벤트가 참조하는 article이 우리 DB에 하나도 없어서 건너뜀", clusterId);
            return;
        }

        int articleCount = aggregate.articleCount().intValue();
        int pressCount = aggregate.pressCount().intValue();

        Optional<Issue> existing = issueRepository.findById(clusterId);
        if (existing.isPresent()) {
            if (existing.get().isStale(clusteredAt)) {
                log.info("오래된 클러스터링 결과라 무시: clusterId={}, clusteredAt={}", clusterId, clusteredAt);
                return;
            }
            existing.get().updateAggregates(category, factSummary, commonFactsBriefing, pressCount, articleCount,
                    aggregate.firstReportedAt(), aggregate.lastReportedAt(), clusteredAt);
            return;
        }

        issueRepository.save(new Issue(clusterId, category, factSummary, commonFactsBriefing,
                pressCount, articleCount, aggregate.firstReportedAt(), aggregate.lastReportedAt(), clusteredAt));
    }

    @Scheduled(cron = "0 */15 * * * *")
    @CacheEvict(cacheNames = IssueQueryService.ISSUE_FEED_CACHE, allEntries = true)
    public void refreshTrendingScores() {
        if (!scheduleLock.tryAcquire("refreshTrendingScores", LOCK_TTL)) {
            return;
        }
        OffsetDateTime now = OffsetDateTime.now();
        int updated = issueRepository.recalculateScores(now, now.minus(ACTIVE_WINDOW));
        log.info("트렌딩 점수 재계산: {}건", updated);
    }

}

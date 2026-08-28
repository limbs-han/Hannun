package com.example.demo.issue.service;

import com.example.demo.article.repository.ArticleClusterAggregate;
import com.example.demo.article.service.ArticleQueryService;
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
import java.util.Optional;

@Slf4j
@Service
@Transactional
@RequiredArgsConstructor
public class IssueCommandService {

    private static final Duration ACTIVE_WINDOW = Duration.ofDays(2);

    private final IssueRepository issueRepository;
    private final ArticleQueryService articleQueryService;

    @Caching(evict = {
            @CacheEvict(cacheNames = IssueQueryService.ISSUE_FEED_CACHE, allEntries = true),
            @CacheEvict(cacheNames = IssueQueryService.ISSUE_DETAIL_CACHE, key = "#clusterId + ':positive:0'"),
            @CacheEvict(cacheNames = IssueQueryService.ISSUE_DETAIL_CACHE, key = "#clusterId + ':neutral:0'"),
            @CacheEvict(cacheNames = IssueQueryService.ISSUE_DETAIL_CACHE, key = "#clusterId + ':negative:0'")
    })
    public void applyClusteringResult(Long clusterId, String category, String factSummary) {
        ArticleClusterAggregate aggregate = articleQueryService.aggregateByClusterId(clusterId);
        if (aggregate.articleCount() == null || aggregate.articleCount() == 0) {
            throw new IllegalStateException(
                    "clusterId=%d 이벤트를 처리하려는데 반영된 Article이 없음".formatted(clusterId));
        }

        int articleCount = aggregate.articleCount().intValue();
        int pressCount = aggregate.pressCount().intValue();

        Optional<Issue> existing = issueRepository.findById(clusterId);
        if (existing.isPresent()) {
            existing.get().updateAggregates(category, factSummary, pressCount, articleCount,
                    aggregate.firstReportedAt(), aggregate.lastReportedAt());
            return;
        }

        issueRepository.save(new Issue(clusterId, category, factSummary,
                pressCount, articleCount, aggregate.firstReportedAt(), aggregate.lastReportedAt()));
    }

    @Scheduled(cron = "0 */15 * * * *")
    @CacheEvict(cacheNames = IssueQueryService.ISSUE_FEED_CACHE, allEntries = true)
    public void refreshTrendingScores() {
        OffsetDateTime now = OffsetDateTime.now();
        int updated = issueRepository.recalculateScores(now, now.minus(ACTIVE_WINDOW));
        log.info("트렌딩 점수 재계산: {}건", updated);
    }

}

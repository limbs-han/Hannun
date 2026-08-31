package com.example.demo.issue.service.strategy;

import com.example.demo.issue.domain.Issue;
import com.example.demo.issue.repository.IssueRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.OffsetDateTime;
import java.util.List;

@Component
@RequiredArgsConstructor
public class TrendingIssueFeedStrategy implements IssueFeedStrategy {

    private static final Duration ACTIVE_WINDOW = Duration.ofDays(2);

    private final IssueRepository issueRepository;

    @Override
    public String sortKey() {
        return "trending";
    }

    @Override
    public List<Issue> fetchRows(String category, String cursorValue, Long cursorId, int limit) {
        Long cursorScore = parseCursorScore(cursorValue);
        OffsetDateTime activeSince = OffsetDateTime.now().minus(ACTIVE_WINDOW);
        return issueRepository.findTrendingFeed(activeSince, category, cursorScore, cursorId, limit + 1);
    }

    @Override
    public Object extractCursorValue(Issue issue) {
        return issue.getScore();
    }

    private Long parseCursorScore(String cursorValue) {
        if (cursorValue == null) {
            return null;
        }
        return Long.valueOf(cursorValue);
    }
}

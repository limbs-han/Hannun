package com.example.demo.issue.service.strategy;

import com.example.demo.issue.domain.Issue;
import com.example.demo.issue.repository.IssueRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.time.OffsetDateTime;
import java.util.List;

@Component
@RequiredArgsConstructor
public class LatestIssueFeedStrategy implements IssueFeedStrategy {

    private final IssueRepository issueRepository;

    @Override
    public String sortKey() {
        return "latest";
    }

    @Override
    public List<Issue> fetchRows(String category, String cursorValue, Long cursorId, int limit) {
        OffsetDateTime cursorLastReportedAt = parseCursorLastReportedAt(cursorValue);
        return issueRepository.findLatestFeed(category, cursorLastReportedAt, cursorId, limit + 1);
    }

    @Override
    public Object extractCursorValue(Issue issue) {
        return issue.getLastReportedAt();
    }

    private OffsetDateTime parseCursorLastReportedAt(String cursorValue) {
        if (cursorValue == null) {
            return null;
        }
        return OffsetDateTime.parse(cursorValue);
    }
}

package com.example.demo.issue.service.strategy;

import com.example.demo.issue.domain.Issue;

import java.util.List;

public interface IssueFeedStrategy {

    String sortKey();

    List<Issue> fetchRows(String category, String cursorValue, Long cursorId, int limit);

    Object extractCursorValue(Issue issue);
}

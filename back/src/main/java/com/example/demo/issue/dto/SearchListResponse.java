package com.example.demo.issue.dto;

import java.util.List;

public record SearchListResponse(
        String resultType,
        String keyword,
        List<SearchItem> items,
        Double nextCursorValue,
        Long nextCursorId,
        boolean hasNext
) {
    public record SearchItem(
            Long issueId,
            String category,
            String factSummary,
            Integer articleCount,
            Integer pressCount
    ) {
    }
}

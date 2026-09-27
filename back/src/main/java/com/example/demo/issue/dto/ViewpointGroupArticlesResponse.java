package com.example.demo.issue.dto;

import com.example.demo.issue.dto.IssueDetailResponse.ArticlePreview;

import java.time.OffsetDateTime;
import java.util.List;

public record ViewpointGroupArticlesResponse(
        List<ArticlePreview> items,
        OffsetDateTime nextCursorPublished,
        Long nextCursorArticleId,
        boolean hasNext
) {
}

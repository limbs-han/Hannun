package com.example.demo.issue.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.OffsetDateTime;
import java.util.List;

public record IssueDetailResponse(
        Long issueId,
        String category,
        OffsetDateTime firstReportedAt,
        OffsetDateTime lastReportedAt,
        Integer pressCount,
        Integer articleCount,
        String factSummary,
        List<String> commonFactsBriefing,
        StanceRatio stanceRatio,
        // 요청으로 받은 stance 그대로. 프론트가 탭 활성 표시에 씀.
        String selectedStance,
        List<ViewpointGroupSummary> viewpointGroups,
        ViewpointGroupPage viewpointGroupPage
) {
    public record StanceRatio(double positive, double neutral, double negative) {
    }

    public record ViewpointGroupSummary(
            Long groupId,
            String label,
            String stance,
            Integer articleCount,
            Integer pressCount,
            List<ArticlePreview> previewArticles,
            int remainingCount
    ) {
    }

    public record ArticlePreview(
            Long articleId,
            String company,
            String title,
            String link,
            OffsetDateTime published,
            String category,
            String categoryStr,
            String reporter,
            String thumbnailUrl
    ) {
    }

    public record ViewpointGroupPage(int page, int size, long totalCount, int totalPages) {
    }
}

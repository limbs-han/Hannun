package com.example.demo.article.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.time.OffsetDateTime;
import java.util.List;

public record ClusteringCompletedMessage(
        Long clusterId,
        String category,
        String factSummary,
        List<String> commonFactsBriefing,
        OffsetDateTime clusteredAt,
        List<ArticleAssignment> articles
) {
    public record ArticleAssignment(
            String link,
            String viewpointGroupLabel,
            String stance
    ) {
    }
}

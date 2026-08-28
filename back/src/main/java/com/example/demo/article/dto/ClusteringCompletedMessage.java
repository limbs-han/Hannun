package com.example.demo.article.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.List;

public record ClusteringCompletedMessage(
        Long clusterId,
        String category,
        String factSummary,
        List<ArticleAssignment> articles
) {
    public record ArticleAssignment(
            Long articleId,
            String viewpointGroupLabel,
            String stance
    ) {
    }
}

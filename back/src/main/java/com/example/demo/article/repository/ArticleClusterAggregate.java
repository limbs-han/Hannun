package com.example.demo.article.repository;

import java.time.OffsetDateTime;

public record ArticleClusterAggregate(
        Long articleCount,
        Long pressCount,
        OffsetDateTime firstReportedAt,
        OffsetDateTime lastReportedAt
) {
}

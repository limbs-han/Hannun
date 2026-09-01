package com.example.demo.article.dto;

import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

import java.time.OffsetDateTime;

// snake_case(category_str, thumbnail_url) + 표준 ISO-8601. 이 형식으로 확정됨.
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ArticleIngestMessage(
        String company,
        String title,
        String link,
        OffsetDateTime published,
        String category,
        String categoryStr,
        String reporter,
        String thumbnailUrl,
        String article
) {
}

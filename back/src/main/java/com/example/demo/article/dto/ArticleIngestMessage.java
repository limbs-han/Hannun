package com.example.demo.article.dto;

import java.time.OffsetDateTime;

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

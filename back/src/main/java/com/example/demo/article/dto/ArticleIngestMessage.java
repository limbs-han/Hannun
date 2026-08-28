package com.example.demo.article.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.time.OffsetDateTime;

@JsonIgnoreProperties(ignoreUnknown = true)
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

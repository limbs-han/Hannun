package com.example.demo.article.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.time.OffsetDateTime;

// 실제로는 camelCase + 표준 ISO-8601(타임존 포함)로 옴 - snake_case/커스텀 날짜 파싱은
// 크롤러 쪽 오발송이었다고 확인돼서 되돌림.
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

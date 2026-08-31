package com.example.demo.article.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonDeserialize;
import tools.jackson.databind.annotation.JsonNaming;

import java.time.OffsetDateTime;

// 크롤러가 snake_case로 보냄(category_str, thumbnail_url 등) -> 필드명 전체를 snake_case로 매핑.
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
@JsonIgnoreProperties(ignoreUnknown = true)
public record ArticleIngestMessage(
        String company,
        String title,
        String link,
        @JsonDeserialize(using = KstDateTimeDeserializer.class) OffsetDateTime published,
        String category,
        String categoryStr,
        String reporter,
        String thumbnailUrl,
        String article
) {
}

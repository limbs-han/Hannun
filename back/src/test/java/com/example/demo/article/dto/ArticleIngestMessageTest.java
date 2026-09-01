package com.example.demo.article.dto;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.time.OffsetDateTime;

import static org.assertj.core.api.Assertions.assertThat;

class ArticleIngestMessageTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    // 실제로 크롤러가 보내는 형식 그대로: camelCase + 표준 ISO-8601(타임존 포함)
    @Test
    void 크롤러가_보내는_실제_형식을_파싱한다() {
        String json = """
                {
                  "company": "세계일보",
                  "title": "테스트 기사",
                  "link": "https://test.example.com/1",
                  "published": "2025-04-21T23:59:37+09:00",
                  "category": "연예일반",
                  "categoryStr": "연예일반",
                  "reporter": null,
                  "thumbnailUrl": null
                }
                """;

        ArticleIngestMessage message = objectMapper.readValue(json, ArticleIngestMessage.class);

        assertThat(message.categoryStr()).isEqualTo("연예일반");
        assertThat(message.published()).isEqualTo(OffsetDateTime.parse("2025-04-21T23:59:37+09:00"));
    }
}

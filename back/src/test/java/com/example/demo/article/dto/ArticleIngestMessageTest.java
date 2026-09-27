package com.example.demo.article.dto;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.time.OffsetDateTime;

import static org.assertj.core.api.Assertions.assertThat;

class ArticleIngestMessageTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    // 실제로 크롤러가 보내는 형식 그대로: snake_case + 표준 ISO-8601(타임존 포함)
    @Test
    void 크롤러가_보내는_실제_형식을_파싱한다() {
        String json = """
                {
                  "company": "MBN",
                  "title": "[날씨] 새해 첫날 큰 추위 없어…동해안 대기 건조",
                  "link": "https://www.mbn.co.kr/news/life/5084855?page=1&date=20250101",
                  "published": "2025-01-01T19:48:00+09:00",
                  "category": "생활/건강",
                  "category_str": "뉴스 > 생활/건강",
                  "reporter": "정예은",
                  "thumbnail_url": null
                }
                """;

        ArticleIngestMessage message = objectMapper.readValue(json, ArticleIngestMessage.class);

        assertThat(message.company()).isEqualTo("MBN");
        assertThat(message.categoryStr()).isEqualTo("뉴스 > 생활/건강");
        assertThat(message.thumbnailUrl()).isNull();
        assertThat(message.published()).isEqualTo(OffsetDateTime.parse("2025-01-01T19:48:00+09:00"));
    }
}

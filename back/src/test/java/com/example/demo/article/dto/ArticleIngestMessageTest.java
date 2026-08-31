package com.example.demo.article.dto;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;

class ArticleIngestMessageTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    // 크롤러가 실제로 보내는 형식 그대로: snake_case 필드명 + "yyyy-MM-dd HH:mm" published(초/타임존 없음)
    @Test
    void 크롤러가_보내는_실제_형식을_파싱한다() {
        String json = """
                {
                  "company": "테스트일보",
                  "title": "테스트 기사",
                  "link": "https://test.example.com/1",
                  "published": "2026-08-20 12:00",
                  "category": "정치",
                  "category_str": "정치>경제정책",
                  "reporter": "테스트기자",
                  "thumbnail_url": "https://test.example.com/thumb.jpg",
                  "article": "본문"
                }
                """;

        ArticleIngestMessage message = objectMapper.readValue(json, ArticleIngestMessage.class);

        assertThat(message.categoryStr()).isEqualTo("정치>경제정책");
        assertThat(message.thumbnailUrl()).isEqualTo("https://test.example.com/thumb.jpg");
        assertThat(message.published()).isEqualTo(OffsetDateTime.of(2026, 8, 20, 12, 0, 0, 0, ZoneOffset.ofHours(9)));
    }
}

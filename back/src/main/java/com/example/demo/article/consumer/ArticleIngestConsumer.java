package com.example.demo.article.consumer;

import com.example.demo.article.dto.ArticleCreateRequest;
import com.example.demo.article.dto.ArticleIngestMessage;
import com.example.demo.article.service.ArticleCommandService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Component
@RequiredArgsConstructor
public class ArticleIngestConsumer {

    private final ArticleCommandService articleCommandService;
    private final ObjectMapper objectMapper;

    // concurrency는 이 리스너만 개별 지정 - 글로벌로 주면 clustering-completed 리스너까지 같이 늘어나서
    // HikariCP 풀을 나눠 쓰게 됨(그쪽은 MySQL을 더 무겁게 씀).
    // 1차 실험값 = 2 (파티션 3개 그대로, 단계적으로 올려가며 측정 예정: 2 -> 3 -> ...)
    @KafkaListener(topics = "${news.kafka.topic.article-ingest}", groupId = "news-write-service", concurrency = "2")
    public void consume(String payload, Acknowledgment acknowledgment) throws Exception {
        ArticleIngestMessage message = objectMapper.readValue(payload, ArticleIngestMessage.class);

        articleCommandService.save(new ArticleCreateRequest(
                message.company(),
                message.title(),
                message.link(),
                message.published(),
                message.category(),
                message.categoryStr(),
                message.reporter(),
                message.thumbnailUrl()
        ));

        acknowledgment.acknowledge();
    }
}

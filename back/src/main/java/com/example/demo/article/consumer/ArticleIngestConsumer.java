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

    @KafkaListener(topics = "${news.kafka.topic.article-ingest}", groupId = "news-write-service")
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

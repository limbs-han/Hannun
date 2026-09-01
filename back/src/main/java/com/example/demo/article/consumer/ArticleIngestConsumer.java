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

import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class ArticleIngestConsumer {

    private final ArticleCommandService articleCommandService;
    private final ObjectMapper objectMapper;

    @KafkaListener(topics = "${news.kafka.topic.article-ingest}", groupId = "news-write-service", concurrency = "3",
            containerFactory = "batchListenerContainerFactory")
    public void consume(List<String> payloads, Acknowledgment acknowledgment) throws Exception {
        List<ArticleCreateRequest> requests = payloads.stream()
                .map(this::toRequest)
                .toList();

        articleCommandService.saveAll(requests);

        acknowledgment.acknowledge();
    }

    private ArticleCreateRequest toRequest(String payload) {
        ArticleIngestMessage message = objectMapper.readValue(payload, ArticleIngestMessage.class);
        return new ArticleCreateRequest(
                message.company(),
                message.title(),
                message.link(),
                message.published(),
                message.category(),
                message.categoryStr(),
                message.reporter(),
                message.thumbnailUrl()
        );
    }
}

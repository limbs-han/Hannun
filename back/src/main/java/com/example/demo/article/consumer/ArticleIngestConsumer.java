package com.example.demo.article.consumer;

import com.example.demo.article.dto.ArticleCreateRequest;
import com.example.demo.article.dto.ArticleIngestMessage;
import com.example.demo.article.service.ArticleCommandService;
import io.micrometer.core.annotation.Timed;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.listener.BatchListenerFailedException;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class ArticleIngestConsumer {

    private final ArticleCommandService articleCommandService;
    private final ObjectMapper objectMapper;

    @Timed(value = "message.processing.duration", extraTags = {"consumer", "article-ingest"},
            description = "배치 1건(JSON 파싱 + DB 저장) 전체 처리 시간")
    @KafkaListener(topics = "${news.kafka.topic.article-ingest}", groupId = "news-write-service", concurrency = "3",
            containerFactory = "batchListenerContainerFactory")
    public void consume(List<String> payloads, Acknowledgment acknowledgment) throws Exception {
        // 파싱은 순서대로 하나씩 시도 - 중간에 하나(i번째)가 깨져있으면, 그 앞까지는 이미
        // 파싱 성공한 거니까 먼저 저장부터 하고 BatchListenerFailedException(i)를 던진다.
        // 그러면 Spring Kafka가 i번째 이전은 커밋(다시 안 보냄), i번째부터만 재시도 -> 결국
        // 그 1건만 DLQ로 격리하고 나머지(뒤에 있던 정상 메시지들 포함)는 다음 재시도에서 정상 처리됨.
        // saveAll()이 upsert라 재시도로 앞부분이 다시 들어와도 중복 저장 걱정 없음.
        List<ArticleCreateRequest> requests = new ArrayList<>();
        for (int i = 0; i < payloads.size(); i++) {
            try {
                requests.add(toRequest(payloads.get(i)));
            } catch (Exception e) {
                log.warn("메시지 파싱 실패, 이 1건만 격리하고 나머지는 계속 처리: index={}", i, e);
                articleCommandService.saveAll(requests);
                throw new BatchListenerFailedException("메시지 파싱 실패(index=" + i + ")", e, i);
            }
        }

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

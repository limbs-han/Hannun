package com.example.demo.issue.service;

import com.example.demo.issue.dto.SearchExecutedMessage;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Component
public class SearchEventPublisher {

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;
    private final String topic;

    public SearchEventPublisher(KafkaTemplate<String, String> kafkaTemplate,
                                 ObjectMapper objectMapper,
                                 @Value("${news.kafka.topic.search-executed}") String topic) {
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
        this.topic = topic;
    }

    // 검색 응답 경로를 막지 않도록 fire-and-forget. 실패해도 검색 자체는 정상 응답되고, 실패 사실만 로그로 남김.
    public void publishSearchExecuted(String keyword) {
        SearchExecutedMessage message = new SearchExecutedMessage(keyword);

        String payload;
        try {
            payload = objectMapper.writeValueAsString(message);
        } catch (Exception e) {
            log.warn("검색 이벤트 직렬화 실패: keyword={}", keyword, e);
            return;
        }

        kafkaTemplate.send(topic, keyword, payload).whenComplete((result, ex) -> {
            if (ex != null) {
                log.warn("검색 이벤트 발행 실패: keyword={}", keyword, ex);
            }
        });
    }
}

package com.example.demo.issue.consumer;

import com.example.demo.issue.dto.SearchExecutedMessage;
import com.example.demo.issue.service.SearchPopularityAggregator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

@Slf4j
@Component
@RequiredArgsConstructor
public class SearchPopularityConsumer {

    private final SearchPopularityAggregator searchPopularityAggregator;
    private final ObjectMapper objectMapper;

    @KafkaListener(topics = "${news.kafka.topic.search-executed}", groupId = "news-write-service")
    public void consume(String payload, Acknowledgment acknowledgment) throws Exception {
        SearchExecutedMessage message = objectMapper.readValue(payload, SearchExecutedMessage.class);

        searchPopularityAggregator.increment(message.keyword());

        acknowledgment.acknowledge();
    }
}

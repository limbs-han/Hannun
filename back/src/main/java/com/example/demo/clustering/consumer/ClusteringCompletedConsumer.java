package com.example.demo.clustering.consumer;

import com.example.demo.article.dto.ClusteringCompletedMessage;
import com.example.demo.article.dto.ClusteringCompletedMessage.ArticleAssignment;
import com.example.demo.article.service.ArticleCommandService;
import com.example.demo.issue.service.IssueCommandService;
import com.example.demo.viewpointgroup.domain.ViewpointGroup;
import com.example.demo.viewpointgroup.service.ViewpointGroupCommandService;
import io.micrometer.core.annotation.Timed;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Component
@RequiredArgsConstructor
public class ClusteringCompletedConsumer {

    private static final int CHUNK_SIZE = 500;

    private final ArticleCommandService articleCommandService;
    private final ViewpointGroupCommandService viewpointGroupCommandService;
    private final IssueCommandService issueCommandService;
    private final ObjectMapper objectMapper;

    @Timed(value = "message.processing.duration", extraTags = {"consumer", "clustering-completed"},
            description = "클러스터링 결과 메시지 1건 전체 처리 시간")
    @KafkaListener(topics = "${news.kafka.topic.clustering-completed}", groupId = "news-write-service")
    public void consume(String payload, Acknowledgment acknowledgment) throws Exception {
        ClusteringCompletedMessage message = objectMapper.readValue(payload, ClusteringCompletedMessage.class);

        // 오래된(이미 저장된 것보다 과거 시점의) 클러스터링 결과면 관점그룹/기사 배정 작업 자체를 안 함 —
        // 파티션이 여러 개라 도착 순서가 뒤집힐 수 있고, DLQ 재처리로 옛날 메시지가 나중에 다시 들어올 수도 있음.
        if (!issueCommandService.isNewerThanStored(message.clusterId(), message.clusteredAt())) {
            log.info("오래된 클러스터링 메시지라 무시: clusterId={}, clusteredAt={}", message.clusterId(), message.clusteredAt());
            acknowledgment.acknowledge();
            return;
        }

        List<ArticleAssignment> assignments = message.articles();

        if (assignments != null) {
            Set<Long> touchedGroupIds = new LinkedHashSet<>();

            for (int i = 0; i < assignments.size(); i += CHUNK_SIZE) {
                List<ArticleAssignment> chunk = assignments.subList(i, Math.min(i + CHUNK_SIZE, assignments.size()));

                Map<String, ViewpointGroup> groupsByLabel =
                        viewpointGroupCommandService.resolveGroups(message.clusterId(), chunk);
                groupsByLabel.values().forEach(group -> touchedGroupIds.add(group.getId()));

                Map<String, Long> groupIdsByLabel = groupsByLabel.entrySet().stream()
                        .collect(Collectors.toMap(Map.Entry::getKey, entry -> entry.getValue().getId()));
                articleCommandService.updateClusterAssignments(message.clusterId(), chunk, groupIdsByLabel);
            }

            viewpointGroupCommandService.refreshAggregates(touchedGroupIds);
        }

        issueCommandService.applyClusteringResult(message.clusterId(), message.category(), message.factSummary(),
                message.clusteredAt());

        acknowledgment.acknowledge();
    }
}

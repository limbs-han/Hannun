package com.example.demo.clustering.consumer;

import com.example.demo.article.dto.ClusteringCompletedMessage;
import com.example.demo.article.dto.ClusteringCompletedMessage.ArticleAssignment;
import com.example.demo.article.service.ArticleCommandService;
import com.example.demo.issue.service.IssueCommandService;
import com.example.demo.viewpointgroup.domain.ViewpointGroup;
import com.example.demo.viewpointgroup.service.ViewpointGroupCommandService;
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

    @KafkaListener(topics = "${news.kafka.topic.clustering-completed}", groupId = "news-write-service")
    public void consume(String payload, Acknowledgment acknowledgment) throws Exception {
        ClusteringCompletedMessage message = objectMapper.readValue(payload, ClusteringCompletedMessage.class);
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

        issueCommandService.applyClusteringResult(message.clusterId(), message.category(), message.factSummary());

        acknowledgment.acknowledge();
    }
}

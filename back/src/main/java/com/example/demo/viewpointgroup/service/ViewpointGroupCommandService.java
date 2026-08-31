package com.example.demo.viewpointgroup.service;

import com.example.demo.article.dto.ClusteringCompletedMessage.ArticleAssignment;
import com.example.demo.article.repository.ViewpointGroupCounts;
import com.example.demo.article.service.ArticleQueryService;
import com.example.demo.viewpointgroup.domain.ViewpointGroup;
import com.example.demo.viewpointgroup.repository.ViewpointGroupRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

@Service
@Transactional
@RequiredArgsConstructor
public class ViewpointGroupCommandService {

    private final ViewpointGroupRepository viewpointGroupRepository;
    private final ArticleQueryService articleQueryService;

    public Map<String, ViewpointGroup> resolveGroups(Long clusterId, List<ArticleAssignment> assignments) {
        Map<String, String> stanceByLabel = new LinkedHashMap<>();
        for (ArticleAssignment assignment : assignments) {
            stanceByLabel.putIfAbsent(assignment.viewpointGroupLabel(), assignment.stance());
        }

        Map<String, ViewpointGroup> groupsByLabel = new LinkedHashMap<>();
        for (Map.Entry<String, String> entry : stanceByLabel.entrySet()) {
            String label = entry.getKey();
            Optional<ViewpointGroup> existing = viewpointGroupRepository.findByClusterIdAndLabel(clusterId, label);
            if (existing.isPresent()) {
                groupsByLabel.put(label, existing.get());
                continue;
            }

            ViewpointGroup group = viewpointGroupRepository.save(new ViewpointGroup(clusterId, label, entry.getValue()));
            groupsByLabel.put(label, group);
        }
        return groupsByLabel;
    }

    public void refreshAggregates(Set<Long> viewpointGroupIds) {
        if (viewpointGroupIds == null || viewpointGroupIds.isEmpty()) {
            return;
        }

        List<ViewpointGroup> groups = viewpointGroupRepository.findAllById(viewpointGroupIds);
        for (ViewpointGroup group : groups) {
            ViewpointGroupCounts counts = articleQueryService.countsByViewpointGroupId(group.getId());
            group.updateAggregates(counts.articleCount().intValue(), counts.pressCount().intValue());
        }
    }
}

package com.example.demo.viewpointgroup.service;

import com.example.demo.viewpointgroup.domain.ViewpointGroup;
import com.example.demo.viewpointgroup.exception.ViewpointGroupNotFoundException;
import com.example.demo.viewpointgroup.repository.StanceSum;
import com.example.demo.viewpointgroup.repository.ViewpointGroupRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@RequiredArgsConstructor
public class ViewpointGroupQueryService {

    private final ViewpointGroupRepository viewpointGroupRepository;

    @Transactional(readOnly = true)
    public List<StanceSum> sumArticleCountByStance(Long clusterId) {
        return viewpointGroupRepository.sumArticleCountByStance(clusterId);
    }

    @Transactional(readOnly = true)
    public Page<ViewpointGroup> findByClusterIdAndStance(Long clusterId, String stance, Pageable pageable) {
        return viewpointGroupRepository.findByClusterIdAndStanceOrderByArticleCountDesc(clusterId, stance, pageable);
    }

    @Transactional(readOnly = true)
    public ViewpointGroup getById(Long groupId) {
        return viewpointGroupRepository.findById(groupId)
                .orElseThrow(() -> new ViewpointGroupNotFoundException(groupId));
    }
}

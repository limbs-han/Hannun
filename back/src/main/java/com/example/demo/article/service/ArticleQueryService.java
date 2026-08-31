package com.example.demo.article.service;

import com.example.demo.article.domain.Article;
import com.example.demo.article.repository.ArticleClusterAggregate;
import com.example.demo.article.repository.ArticleRepository;
import com.example.demo.article.repository.ViewpointGroupCounts;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ArticleQueryService {

    private final ArticleRepository articleRepository;

    public ArticleClusterAggregate aggregateByClusterId(Long clusterId) {
        return articleRepository.aggregateByClusterId(clusterId);
    }

    public List<Article> findTop3ByViewpointGroupId(Long viewpointGroupId) {
        return articleRepository.findTop3ByViewpointGroupIdOrderByPublishedDesc(viewpointGroupId);
    }

    public ViewpointGroupCounts countsByViewpointGroupId(Long viewpointGroupId) {
        return articleRepository.countsByViewpointGroupId(viewpointGroupId);
    }

    public List<Article> findByViewpointGroupIdWithCursor(Long viewpointGroupId, OffsetDateTime cursorPublished,
                                                            Long cursorArticleId, int limit) {
        return articleRepository.findByViewpointGroupIdWithCursor(viewpointGroupId, cursorPublished, cursorArticleId, limit);
    }
}

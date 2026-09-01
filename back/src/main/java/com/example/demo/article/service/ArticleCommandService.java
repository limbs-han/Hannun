package com.example.demo.article.service;

import com.example.demo.article.domain.Article;
import com.example.demo.article.dto.ArticleCreateRequest;
import com.example.demo.article.dto.ClusteringCompletedMessage.ArticleAssignment;
import com.example.demo.article.repository.ArticleRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ArticleCommandService {

    private final ArticleRepository articleRepository;

    // 중복체크 SELECT + INSERT를 트랜잭션 하나로 묶어서 커밋 왕복을 1번으로 줄임(메시지 1건당 트랜잭션 1개는 그대로 유지).
    @Transactional
    public Article save(ArticleCreateRequest request) {
        Optional<Article> existing = articleRepository.findByLink(request.link());
        if (existing.isPresent()) {
            return existing.get();
        }

        Article article = new Article(request.company(), request.title(), request.link(), request.published(),
                request.category(), request.categoryStr(), request.reporter(), request.thumbnailUrl());
        return articleRepository.save(article);
    }

    @Transactional
    public void updateClusterAssignments(Long clusterId, List<ArticleAssignment> assignments,
                                          Map<String, Long> groupIdsByLabel) {
        if (assignments == null || assignments.isEmpty()) {
            return;
        }

        Map<String, ArticleAssignment> assignmentByLink = assignments.stream()
                .collect(Collectors.toMap(ArticleAssignment::link, Function.identity()));

        List<Article> articles = articleRepository.findAllByLinkIn(assignmentByLink.keySet());
        for (Article article : articles) {
            ArticleAssignment assignment = assignmentByLink.get(article.getLink());
            article.applyClusterAssignment(clusterId, groupIdsByLabel.get(assignment.viewpointGroupLabel()));
        }
    }
}

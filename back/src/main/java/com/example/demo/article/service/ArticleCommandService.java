package com.example.demo.article.service;

import com.example.demo.article.domain.Article;
import com.example.demo.article.dto.ArticleCreateRequest;
import com.example.demo.article.dto.ClusteringCompletedMessage.ArticleAssignment;
import com.example.demo.article.repository.ArticleRepository;
import io.micrometer.core.annotation.Timed;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ArticleCommandService {

    private final ArticleRepository articleRepository;
    private final JdbcTemplate jdbcTemplate;

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

    @Timed(value = "db.write.duration", extraTags = {"operation", "article-bulk-upsert"},
            description = "article 벌크 upsert 쿼리 실행 시간(JSON 파싱 등 다른 구간 제외, DB 왕복만)")
    public void saveAll(List<ArticleCreateRequest> requests) {
        if (requests.isEmpty()) {
            return;
        }

        String valuesPlaceholder = "(?, ?, ?, ?, ?, ?, ?, ?, ?)";
        String valuesClause = requests.stream().map(r -> valuesPlaceholder).collect(Collectors.joining(", "));
        String sql = "INSERT INTO article "
                + "(company, title, link, published, category, category_str, reporter, thumbnail_url, created_at) "
                + "VALUES " + valuesClause + " "
                + "ON DUPLICATE KEY UPDATE link = link";

        OffsetDateTime now = OffsetDateTime.now();
        List<Object> args = new ArrayList<>();
        for (ArticleCreateRequest request : requests) {
            args.add(request.company());
            args.add(request.title());
            args.add(request.link());
            args.add(request.published());
            args.add(request.category());
            args.add(request.categoryStr());
            args.add(request.reporter());
            args.add(request.thumbnailUrl());
            args.add(now);
        }

        jdbcTemplate.update(sql, args.toArray());
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

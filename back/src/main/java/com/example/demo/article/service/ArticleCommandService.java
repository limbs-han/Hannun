package com.example.demo.article.service;

import com.example.demo.article.domain.Article;
import com.example.demo.article.dto.ArticleCreateRequest;
import com.example.demo.article.dto.ClusteringCompletedMessage.ArticleAssignment;
import com.example.demo.article.repository.ArticleRepository;
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

    /**
     * 배치 컨슈머용 벌크 upsert. link가 이미 있으면 "ON DUPLICATE KEY UPDATE link = link"로
     * 아무것도 안 바꾸고 그냥 넘어감(중복은 실패가 아니라 no-op) - JPA(IDENTITY 전략이라
     * Hibernate가 배치 insert를 지원 안 함)를 우회해서 JdbcTemplate으로 멀티로우 INSERT
     * 한 문장을 날린다. 이 문장은 하나의 트랜잭션/문장이라 all-or-nothing이고,
     * (링크 중복이 아닌) 진짜 DB 오류가 나면 배치 전체가 실패해서 그대로 Kafka 재시도로 넘어간다.
     */
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
        List<Object> args = new ArrayList<>(requests.size() * 9);
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

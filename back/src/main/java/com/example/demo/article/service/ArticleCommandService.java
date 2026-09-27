package com.example.demo.article.service;

import com.example.demo.article.domain.Article;
import com.example.demo.article.dto.ArticleCreateRequest;
import com.example.demo.article.dto.ClusteringCompletedMessage.ArticleAssignment;
import com.example.demo.article.repository.ArticleRepository;
import io.micrometer.core.annotation.Timed;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class ArticleCommandService {

    private final ArticleRepository articleRepository;

    // saveAll()(article-ingest 배치 전용)만 별도 풀을 씀 - 다른 곳(articleRepository 등)은 그대로 기본 풀 사용.
    @Qualifier("articleIngestJdbcTemplate")
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

    // 기사가 재클러스터링으로 다른 클러스터/관점그룹으로 옮겨갈 때, 옮겨가기 전 소속(clusterId/
    // viewpointGroupId)을 같이 돌려줌 - 옛날 클러스터/관점그룹은 이 메시지만으론 갱신 대상이 아니라서
    // (이 메시지는 새 clusterId 기준으로만 옴) 별도로 카운트 재계산을 걸어주지 않으면 기사가 다 빠져나가도
    // article_count가 예전 값 그대로 박제됨(피드에 "기사 있다"고 뜨는데 실제론 0건인 버그의 원인).
    public record ReassignmentResult(Set<Long> previousClusterIds, Set<Long> previousViewpointGroupIds) {
        public static ReassignmentResult empty() {
            return new ReassignmentResult(Set.of(), Set.of());
        }
    }

    @Transactional
    public ReassignmentResult updateClusterAssignments(Long clusterId, List<ArticleAssignment> assignments,
                                                         Map<String, Long> groupIdsByLabel) {
        if (assignments == null || assignments.isEmpty()) {
            return ReassignmentResult.empty();
        }

        Map<String, ArticleAssignment> assignmentByLink = assignments.stream()
                .collect(Collectors.toMap(ArticleAssignment::link, Function.identity()));

        List<Article> articles = articleRepository.findAllByLinkIn(assignmentByLink.keySet());
        Set<Long> previousClusterIds = new LinkedHashSet<>();
        Set<Long> previousViewpointGroupIds = new LinkedHashSet<>();
        for (Article article : articles) {
            Long previousClusterId = article.getClusterId();
            Long previousViewpointGroupId = article.getViewpointGroupId();
            if (previousClusterId != null && !previousClusterId.equals(clusterId)) {
                previousClusterIds.add(previousClusterId);
            }
            if (previousViewpointGroupId != null) {
                previousViewpointGroupIds.add(previousViewpointGroupId);
            }

            ArticleAssignment assignment = assignmentByLink.get(article.getLink());
            article.applyClusterAssignment(clusterId, groupIdsByLabel.get(assignment.viewpointGroupLabel()));
        }
        return new ReassignmentResult(previousClusterIds, previousViewpointGroupIds);
    }
}

package com.example.demo.article.repository;

import com.example.demo.article.domain.Article;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.List;
import java.util.Optional;

@Repository
public interface ArticleRepository extends JpaRepository<Article, Long> {
    Optional<Article> findByLink(String link);

    List<Article> findAllByLinkIn(Collection<String> links);

    @Query("select new com.example.demo.article.repository.ArticleClusterAggregate(" +
            "count(a), count(distinct a.company), min(a.published), max(a.published)) " +
            "from Article a where a.clusterId = :clusterId")
    ArticleClusterAggregate aggregateByClusterId(@Param("clusterId") Long clusterId);

    List<Article> findTop3ByViewpointGroupIdOrderByPublishedDesc(Long viewpointGroupId);

    @Query("select new com.example.demo.article.repository.ViewpointGroupCounts(" +
            "count(a), count(distinct a.company)) from Article a where a.viewpointGroupId = :viewpointGroupId")
    ViewpointGroupCounts countsByViewpointGroupId(@Param("viewpointGroupId") Long viewpointGroupId);

    /** 관점그룹 내 기사 더보기 — 커서(published+id) 페이지네이션. idx_article_viewpoint_group_published 그대로 재사용. */
    @Query(value = "select * from article " +
            "where viewpoint_group_id = :viewpointGroupId " +
            "and (:cursorPublished is null or published < :cursorPublished " +
            "     or (published = :cursorPublished and id < :cursorArticleId)) " +
            "order by published desc, id desc " +
            "limit :limit",
            nativeQuery = true)
    List<Article> findByViewpointGroupIdWithCursor(@Param("viewpointGroupId") Long viewpointGroupId,
                                                     @Param("cursorPublished") OffsetDateTime cursorPublished,
                                                     @Param("cursorArticleId") Long cursorArticleId,
                                                     @Param("limit") int limit);
}

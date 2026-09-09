package com.example.demo.issue.repository;

import com.example.demo.issue.domain.Issue;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.List;

@Repository
public interface IssueRepository extends JpaRepository<Issue, Long> {

    @Modifying
    @Query(value = "update issue set score = round(article_count / power(timestampdiff(hour, first_reported_at, :now) + 2, 1.5)) " +
            "where last_reported_at > :activeSince", nativeQuery = true)
    int recalculateScores(@Param("now") OffsetDateTime now, @Param("activeSince") OffsetDateTime activeSince);

    @Query(value = "select * from issue " +
            "where last_reported_at > :activeSince " +
            "and article_count > 0 " +
            "and (:category is null or category = :category) " +
            "and (:cursorScore is null or score < :cursorScore or (score = :cursorScore and cluster_id < :cursorId)) " +
            "order by score desc, cluster_id desc " +
            "limit :limit",
            nativeQuery = true)
    List<Issue> findTrendingFeed(@Param("activeSince") OffsetDateTime activeSince,
                                  @Param("category") String category,
                                  @Param("cursorScore") Long cursorScore,
                                  @Param("cursorId") Long cursorId,
                                  @Param("limit") int limit);

    @Query(value = "select * from issue " +
            "where article_count > 0 " +
            "and (:category is null or category = :category) " +
            "and (:cursorLastReportedAt is null or last_reported_at < :cursorLastReportedAt " +
            "     or (last_reported_at = :cursorLastReportedAt and cluster_id < :cursorId)) " +
            "order by last_reported_at desc, cluster_id desc " +
            "limit :limit",
            nativeQuery = true)
    List<Issue> findLatestFeed(@Param("category") String category,
                                @Param("cursorLastReportedAt") OffsetDateTime cursorLastReportedAt,
                                @Param("cursorId") Long cursorId,
                                @Param("limit") int limit);

    // relevance는 SELECT 별칭이라 WHERE에서 못 씀 -> HAVING으로 커서 비교(MySQL은 HAVING에서 별칭 참조 허용).
    // article_count는 WHERE에서 걸러도 되는 실제 컬럼(별칭 아님) - 재클러스터링으로 기사가 다 빠져나가
    // 0건이 된 옛날 이슈가 검색 결과에 뜨는 것 방지.
    @Query(value = "select cluster_id as clusterId, category, fact_summary as factSummary, " +
            "article_count as articleCount, press_count as pressCount, " +
            "MATCH(fact_summary) AGAINST(:keyword IN NATURAL LANGUAGE MODE) as relevance " +
            "from issue " +
            "where MATCH(fact_summary) AGAINST(:keyword IN NATURAL LANGUAGE MODE) " +
            "and article_count > 0 " +
            "and (:category is null or category = :category) " +
            "having (:cursorValue is null or relevance < :cursorValue " +
            "        or (relevance = :cursorValue and cluster_id < :cursorId)) " +
            "order by relevance desc, cluster_id desc " +
            "limit :limit",
            nativeQuery = true)
    List<IssueSearchRow> searchByKeyword(@Param("keyword") String keyword,
                                          @Param("category") String category,
                                          @Param("cursorValue") Double cursorValue,
                                          @Param("cursorId") Long cursorId,
                                          @Param("limit") int limit);
}

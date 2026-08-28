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
            "where (:category is null or category = :category) " +
            "and (:cursorLastReportedAt is null or last_reported_at < :cursorLastReportedAt " +
            "     or (last_reported_at = :cursorLastReportedAt and cluster_id < :cursorId)) " +
            "order by last_reported_at desc, cluster_id desc " +
            "limit :limit",
            nativeQuery = true)
    List<Issue> findLatestFeed(@Param("category") String category,
                                @Param("cursorLastReportedAt") OffsetDateTime cursorLastReportedAt,
                                @Param("cursorId") Long cursorId,
                                @Param("limit") int limit);
}

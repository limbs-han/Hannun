package com.example.demo.issue.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.OffsetDateTime;

@Entity
@Table(name = "issue", indexes = {
        @Index(name = "idx_issue_score_cluster", columnList = "score, cluster_id"),
        @Index(name = "idx_issue_last_reported_cluster", columnList = "last_reported_at, cluster_id")
})
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Issue {

    @Id
    private Long clusterId;

    @Column(length = 100)
    private String category;

    @Column(columnDefinition = "TEXT")
    private String factSummary;

    @Column(nullable = false)
    private Integer pressCount = 0;

    @Column(nullable = false)
    private Integer articleCount = 0;

    private Long score;

    @Column(nullable = false)
    private OffsetDateTime firstReportedAt;

    @Column(nullable = false)
    private OffsetDateTime lastReportedAt;

    @Column(nullable = false)
    private OffsetDateTime createdAt;

    public Issue(Long clusterId, String category, String factSummary, int pressCount, int articleCount,
                 OffsetDateTime firstReportedAt, OffsetDateTime lastReportedAt) {
        this.clusterId = clusterId;
        this.category = category;
        this.factSummary = factSummary;
        this.pressCount = pressCount;
        this.articleCount = articleCount;
        this.firstReportedAt = firstReportedAt;
        this.lastReportedAt = lastReportedAt;
        this.createdAt = OffsetDateTime.now();
    }

    public void updateAggregates(String category, String factSummary, int pressCount, int articleCount,
                                  OffsetDateTime firstReportedAt, OffsetDateTime lastReportedAt) {
        this.category = category;
        this.factSummary = factSummary;
        this.pressCount = pressCount;
        this.articleCount = articleCount;
        this.firstReportedAt = firstReportedAt;
        this.lastReportedAt = lastReportedAt;
    }
}

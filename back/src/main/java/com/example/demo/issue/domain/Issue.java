package com.example.demo.issue.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.OffsetDateTime;
import java.util.List;

// fact_summary에 FULLTEXT 인덱스(idx_issue_fact_summary_ft, ngram 파서)가 DB에 수동으로 걸려있음 —
// JPA @Index는 FULLTEXT/파서를 표현 못 해서 ddl-auto가 못 만들어줌. 마이그레이션 도구 도입 전까지는 수동 관리.
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

    // 스탠스와 무관하게 다들 동의하는 사실 나열(상세/피드 응답 공용). 별도 테이블(issue_common_facts_briefing)로
    // 분리 - 문장 개수가 적어서 N+1 영향은 크지 않다고 보고 단순한 쪽 선택. @OrderColumn으로 순서 보장.
    @ElementCollection
    @CollectionTable(name = "issue_common_facts_briefing", joinColumns = @JoinColumn(name = "issue_id"))
    @OrderColumn(name = "sort_order")
    @Column(name = "fact", columnDefinition = "TEXT")
    private List<String> commonFactsBriefing;

    @Column(nullable = false)
    private Integer pressCount = 0;

    @Column(nullable = false)
    private Integer articleCount = 0;

    private Long score;

    @Column(nullable = false)
    private OffsetDateTime firstReportedAt;

    @Column(nullable = false)
    private OffsetDateTime lastReportedAt;

    // DE가 같은 clusterId를 다시 클러스터링해서 보낼 수 있음(파티션이 여러 개라 도착 순서가 뒤집힐 수 있고,
    // DLQ 재처리 등으로 더 오래된 메시지가 나중에 들어올 수도 있음) -> 메시지 자체의 "언제 계산됐는지" 시각과
    // 비교해서, 이미 저장된 것보다 오래된 결과면 무시함(last-write-wins by clusteredAt, 도착 순서로 안 믿음).
    @Column(nullable = false)
    private OffsetDateTime clusteredAt;

    @Column(nullable = false)
    private OffsetDateTime createdAt;

    public Issue(Long clusterId, String category, String factSummary, List<String> commonFactsBriefing,
                 int pressCount, int articleCount,
                 OffsetDateTime firstReportedAt, OffsetDateTime lastReportedAt, OffsetDateTime clusteredAt) {
        this.clusterId = clusterId;
        this.category = category;
        this.factSummary = factSummary;
        this.commonFactsBriefing = commonFactsBriefing;
        this.pressCount = pressCount;
        this.articleCount = articleCount;
        this.firstReportedAt = firstReportedAt;
        this.lastReportedAt = lastReportedAt;
        this.clusteredAt = clusteredAt;
        this.createdAt = OffsetDateTime.now();
    }

    public boolean isStale(OffsetDateTime incomingClusteredAt) {
        return incomingClusteredAt.isBefore(this.clusteredAt);
    }

    public void updateAggregates(String category, String factSummary, List<String> commonFactsBriefing,
                                  int pressCount, int articleCount,
                                  OffsetDateTime firstReportedAt, OffsetDateTime lastReportedAt,
                                  OffsetDateTime clusteredAt) {
        this.category = category;
        this.factSummary = factSummary;
        this.commonFactsBriefing = commonFactsBriefing;
        this.pressCount = pressCount;
        this.articleCount = articleCount;
        this.firstReportedAt = firstReportedAt;
        this.lastReportedAt = lastReportedAt;
        this.clusteredAt = clusteredAt;
    }

    // 재클러스터링으로 기사가 다른 클러스터로 옮겨가서 이 이슈의 실제 기사 수가 바뀐 경우 전용 -
    // clusteredAt/category/factSummary는 이 이슈에 대한 새 클러스터링 결과가 아니므로 안 건드림
    // (isStale 비교 기준도 그대로 유지). firstReportedAt/lastReportedAt은 null이면(기사 0건이 됨)
    // NOT NULL 컬럼이라 덮어쓰지 않고 예전 값 유지 - 어차피 articleCount=0이면 피드에서 안 보임.
    public void refreshCounts(int pressCount, int articleCount,
                               OffsetDateTime firstReportedAt, OffsetDateTime lastReportedAt) {
        this.pressCount = pressCount;
        this.articleCount = articleCount;
        if (firstReportedAt != null) {
            this.firstReportedAt = firstReportedAt;
        }
        if (lastReportedAt != null) {
            this.lastReportedAt = lastReportedAt;
        }
    }
}

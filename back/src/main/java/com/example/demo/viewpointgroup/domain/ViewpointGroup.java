package com.example.demo.viewpointgroup.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.OffsetDateTime;

@Entity
@Table(name = "viewpoint_group",
        uniqueConstraints = @UniqueConstraint(name = "uk_viewpoint_group_cluster_label", columnNames = {"cluster_id", "label"}),
        indexes = @Index(name = "idx_viewpoint_group_cluster_count", columnList = "cluster_id, article_count"))
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ViewpointGroup {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "cluster_id", nullable = false)
    private Long clusterId;

    @Column(nullable = false, length = 200)
    private String label;

    @Column(length = 20)
    private String stance;

    @Column(nullable = false)
    private Integer articleCount = 0;

    @Column(nullable = false)
    private Integer pressCount = 0;

    @Column(nullable = false)
    private OffsetDateTime createdAt;

    public ViewpointGroup(Long clusterId, String label, String stance) {
        this.clusterId = clusterId;
        this.label = label;
        this.stance = stance;
        this.createdAt = OffsetDateTime.now();
    }

    public void updateAggregates(int articleCount, int pressCount) {
        this.articleCount = articleCount;
        this.pressCount = pressCount;
    }
}

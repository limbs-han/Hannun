package com.example.demo.article.domain;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.OffsetDateTime;

@Entity
@Table(name = "article",
        uniqueConstraints = @UniqueConstraint(name = "uk_article_link", columnNames = "link"),
        indexes = {
                @Index(name = "idx_article_cluster_id", columnList = "cluster_id"),
                @Index(name = "idx_article_viewpoint_group_published", columnList = "viewpoint_group_id, published")
        })
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Article {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 100)
    private String company;

    @Column(nullable = false, length = 500)
    private String title;

    @Column(nullable = false, unique = true, length = 1000, columnDefinition = "VARCHAR(1000) CHARACTER SET ascii")
    private String link;

    @Column(nullable = false)
    private OffsetDateTime published;

    @Column(length = 100)
    private String category;

    @Column(name = "category_str", length = 100)
    private String categoryStr;

    @Column(length = 100)
    private String reporter;

    @Column(name = "thumbnail_url", length = 1000)
    private String thumbnailUrl;

    @Column(name = "cluster_id")
    private Long clusterId;

    @Column(name = "viewpoint_group_id")
    private Long viewpointGroupId;

    @Column(nullable = false)
    private OffsetDateTime createdAt;

    public Article(String company, String title, String link, OffsetDateTime published,
                    String category, String categoryStr, String reporter, String thumbnailUrl) {
        this.company = company;
        this.title = title;
        this.link = link;
        this.published = published;
        this.category = category;
        this.categoryStr = categoryStr;
        this.reporter = reporter;
        this.thumbnailUrl = thumbnailUrl;
        this.createdAt = OffsetDateTime.now();
    }

    public void applyClusterAssignment(Long clusterId, Long viewpointGroupId) {
        this.clusterId = clusterId;
        this.viewpointGroupId = viewpointGroupId;
    }
}

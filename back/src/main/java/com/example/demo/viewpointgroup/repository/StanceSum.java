package com.example.demo.viewpointgroup.repository;

/** 특정 clusterId 안에서 stance별 articleCount 합계 (전체 그룹을 안 불러오고 집계만). */
public record StanceSum(String stance, Long totalArticleCount) {
}

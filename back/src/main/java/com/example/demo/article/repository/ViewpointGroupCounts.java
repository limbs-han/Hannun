package com.example.demo.article.repository;

/** 특정 ViewpointGroup에 속한 article 집계 (개수, distinct 언론사 수). */
public record ViewpointGroupCounts(Long articleCount, Long pressCount) {
}

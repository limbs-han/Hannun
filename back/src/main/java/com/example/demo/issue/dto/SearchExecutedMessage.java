package com.example.demo.issue.dto;

// 검색 실행(첫 페이지) 시 발행되는 이벤트. SEARCH_SCROLL(다음 페이지 로드)은 인기 검색어 집계 대상이 아니라서 발행하지 않음.
public record SearchExecutedMessage(
        String keyword
) {
}

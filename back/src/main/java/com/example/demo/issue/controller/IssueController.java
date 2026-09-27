package com.example.demo.issue.controller;

import com.example.demo.issue.dto.IssueDetailResponse;
import com.example.demo.issue.dto.IssueFeedResponse;
import com.example.demo.issue.dto.ViewpointGroupArticlesResponse;
import com.example.demo.issue.service.IssueQueryService;
import jakarta.validation.constraints.Min;
import lombok.RequiredArgsConstructor;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;

@RestController
@RequestMapping("/api/issues")
@RequiredArgsConstructor
@Validated
public class IssueController {

    private static final int DEFAULT_SIZE = 10;
    private static final ZoneOffset KST = ZoneOffset.of("+09:00");

    private final IssueQueryService issueQueryService;

    @GetMapping
    public IssueFeedResponse getFeed(
            @RequestParam String category,
            @RequestParam(defaultValue = "trending") String sort,
            @RequestParam(required = false) String cursorValue,
            @RequestParam(required = false) Long cursorId
    ) {
        return issueQueryService.getFeed(category, sort, cursorValue, cursorId, DEFAULT_SIZE);
    }

    // 날짜 범위 검색. from/to는 달력에서 고르는 날짜(연-월-일)만 받고, 하루 전체(00:00:00~23:59:59.999)로
    // 변환해서 그 날짜에 걸쳐있던 이슈를 다 포함시킴. sort는 이 기간 안에서의 정렬 기준(latest/trending).
    @GetMapping("/date-range")
    public IssueFeedResponse getFeedByDateRange(
            @RequestParam String category,
            @RequestParam(defaultValue = "trending") String sort,
            @RequestParam LocalDate from,
            @RequestParam LocalDate to,
            @RequestParam(required = false) String cursorValue,
            @RequestParam(required = false) Long cursorId
    ) {
        OffsetDateTime fromInclusive = from.atStartOfDay(KST).toOffsetDateTime();
        OffsetDateTime toInclusive = to.plusDays(1).atStartOfDay(KST).toOffsetDateTime().minusNanos(1);
        return issueQueryService.getFeedByDateRange(category, sort, fromInclusive, toInclusive, cursorValue, cursorId, DEFAULT_SIZE);
    }

    @GetMapping("/{issueId}")
    public IssueDetailResponse getDetail(
            @PathVariable Long issueId,
            @RequestParam String stance,
            @RequestParam(defaultValue = "0") @Min(0) int page
    ) {
        return issueQueryService.getDetail(issueId, stance, page, DEFAULT_SIZE);
    }

    @GetMapping("/{issueId}/viewpoint-groups/{groupId}/articles")
    public ViewpointGroupArticlesResponse getViewpointGroupArticles(
            @PathVariable Long issueId,
            @PathVariable Long groupId,
            @RequestParam(required = false) OffsetDateTime cursorPublished,
            @RequestParam(required = false) Long cursorArticleId
    ) {
        return issueQueryService.getViewpointGroupArticles(issueId, groupId, cursorPublished, cursorArticleId, DEFAULT_SIZE);
    }
}

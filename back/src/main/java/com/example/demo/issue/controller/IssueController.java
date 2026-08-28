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

import java.time.OffsetDateTime;

@RestController
@RequestMapping("/api/issues")
@RequiredArgsConstructor
@Validated
public class IssueController {

    private static final int DEFAULT_SIZE = 10;

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

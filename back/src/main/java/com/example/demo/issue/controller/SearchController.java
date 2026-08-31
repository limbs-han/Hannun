package com.example.demo.issue.controller;

import com.example.demo.issue.dto.SearchListResponse;
import com.example.demo.issue.dto.SearchSuggestionsResponse;
import com.example.demo.issue.service.IssueQueryService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/search")
@RequiredArgsConstructor
public class SearchController {

    private static final int DEFAULT_SIZE = 10;
    private static final int SUGGESTIONS_SIZE = 10;

    private final IssueQueryService issueQueryService;

    @GetMapping
    public SearchListResponse search(
            @RequestParam String keyword,
            @RequestParam(required = false) String category,
            @RequestParam(required = false) Double cursorValue,
            @RequestParam(required = false) Long cursorId
    ) {
        return issueQueryService.search(keyword, category, cursorValue, cursorId, DEFAULT_SIZE);
    }

    @GetMapping("/suggestions")
    public SearchSuggestionsResponse suggestions() {
        return issueQueryService.getSearchSuggestions(SUGGESTIONS_SIZE);
    }
}

package com.example.demo.issue.dto;

import java.util.List;

public record SearchSuggestionsResponse(
        List<String> popularKeywords
) {
}

package com.example.demo.issue.service.strategy;

import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Component
public class IssueFeedStrategyResolver {

    private final Map<String, IssueFeedStrategy> strategiesBySortKey;

    public IssueFeedStrategyResolver(List<IssueFeedStrategy> strategies) {
        this.strategiesBySortKey = strategies.stream()
                .collect(Collectors.toMap(IssueFeedStrategy::sortKey, Function.identity()));
    }

    public IssueFeedStrategy resolve(String sort) {
        IssueFeedStrategy strategy = strategiesBySortKey.get(sort);
        if (strategy == null) {
            throw new IllegalArgumentException("지원하지 않는 sort 값: " + sort);
        }
        return strategy;
    }
}

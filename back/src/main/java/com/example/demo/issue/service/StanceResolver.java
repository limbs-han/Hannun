package com.example.demo.issue.service;

import com.example.demo.issue.dto.IssueDetailResponse.StanceRatio;
import com.example.demo.viewpointgroup.repository.StanceSum;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Component
public class StanceResolver {

    private static final String STANCE_POSITIVE = "positive";
    private static final String STANCE_NEUTRAL = "neutral";
    private static final String STANCE_NEGATIVE = "negative";
    private static final Set<String> VALID_STANCES = Set.of(STANCE_POSITIVE, STANCE_NEUTRAL, STANCE_NEGATIVE);

    public StanceRatio calculateRatio(List<StanceSum> sums) {
        Map<String, Long> totalByStance = sums.stream()
                .collect(Collectors.toMap(StanceSum::stance, StanceSum::totalArticleCount));

        long positive = totalByStance.getOrDefault(STANCE_POSITIVE, 0L);
        long neutral = totalByStance.getOrDefault(STANCE_NEUTRAL, 0L);
        long negative = totalByStance.getOrDefault(STANCE_NEGATIVE, 0L);
        long total = positive + neutral + negative;

        if (total == 0) {
            return new StanceRatio(0, 0, 0);
        }
        return new StanceRatio((double) positive / total, (double) neutral / total, (double) negative / total);
    }

    public void validate(String stance) {
        if (!VALID_STANCES.contains(stance)) {
            throw new IllegalArgumentException("지원하지 않는 stance 값: " + stance);
        }
    }
}

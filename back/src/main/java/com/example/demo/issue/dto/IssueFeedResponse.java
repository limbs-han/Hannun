package com.example.demo.issue.dto;

import java.util.List;

/**
 * nextCursorValue는 sort에 따라 실제 타입이 다르다 (trending=점수/숫자, latest=시각/문자열).
 * 응답 JSON은 어차피 그 값을 그대로 보여주면 되고, 클라이언트도 다음 요청에 그대로 되돌려주기만 하면 되는
 * 값이라 Object로 두고 Jackson이 실제 타입대로 직렬화하게 둔다.
 */
public record IssueFeedResponse(
        List<IssueSummary> items,
        Object nextCursorValue,
        Long nextCursorId,
        boolean hasNext
) {
    public record IssueSummary(
            Long issueId,
            String category,
            Integer pressCount,
            Integer articleCount,
            Long score,
            String factSummary
    ) {
    }
}

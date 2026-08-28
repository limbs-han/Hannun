package com.example.demo.common.pagination;

import java.util.List;

public record CursorPage<T>(List<T> items, boolean hasNext) {

    public static <T> CursorPage<T> of(List<T> rows, int limit) {
        boolean hasNext = rows.size() > limit;
        List<T> items = rows;
        if (hasNext) {
            items = rows.subList(0, limit);
        }
        return new CursorPage<>(items, hasNext);
    }

    public T last() {
        return items.get(items.size() - 1);
    }
}

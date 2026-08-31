package com.example.demo.issue.repository;

public interface IssueSearchRow {
    Long getClusterId();

    String getCategory();

    String getFactSummary();

    Integer getArticleCount();

    Integer getPressCount();

    Double getRelevance();
}

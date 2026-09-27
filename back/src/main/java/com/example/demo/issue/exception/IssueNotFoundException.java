package com.example.demo.issue.exception;

public class IssueNotFoundException extends RuntimeException {

    public IssueNotFoundException(Long clusterId) {
        super("이슈를 찾을 수 없습니다: " + clusterId);
    }
}

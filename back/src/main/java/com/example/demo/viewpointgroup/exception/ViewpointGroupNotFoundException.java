package com.example.demo.viewpointgroup.exception;

public class ViewpointGroupNotFoundException extends RuntimeException {

    public ViewpointGroupNotFoundException(Long groupId) {
        super("관점 그룹을 찾을 수 없습니다: " + groupId);
    }
}

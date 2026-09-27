package com.example.demo.common.exception;

import com.example.demo.issue.exception.IssueNotFoundException;
import com.example.demo.viewpointgroup.exception.ViewpointGroupNotFoundException;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.time.format.DateTimeParseException;

/**
 * 모든 @RestController에 공통 적용되는 예외 처리.
 * - 클라이언트가 잘못된 값을 보낸 경우(파싱 실패 등) -> 400, 원인은 서버 로그에만 남기고 응답엔 상세 노출 안 함
 * - 그 외 예상 못 한 예외 -> 500, 스택트레이스는 로그로만
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler({IllegalArgumentException.class, DateTimeParseException.class, MethodArgumentTypeMismatchException.class,
            ConstraintViolationException.class, MissingServletRequestParameterException.class})
    public ResponseEntity<ErrorResponse> handleBadRequest(Exception e) {
        log.warn("잘못된 요청: {}", e.getMessage());
        return ResponseEntity.badRequest().body(new ErrorResponse(400, "요청 값이 올바르지 않습니다."));
    }

    @ExceptionHandler(IssueNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(IssueNotFoundException e) {
        return ResponseEntity.status(404).body(new ErrorResponse(404, e.getMessage()));
    }

    @ExceptionHandler(ViewpointGroupNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(ViewpointGroupNotFoundException e) {
        return ResponseEntity.status(404).body(new ErrorResponse(404, e.getMessage()));
    }

    // favicon.ico, robots.txt 등 없는 정적 리소스를 봇/스캐너가 찔러볼 때 스프링이 던지는 예외.
    // catch-all(Exception.class)에 걸리면 500으로 잘못 찍히고 error 레벨 로그도 스팸돼서 별도 분리.
    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ErrorResponse> handleNoResourceFound(NoResourceFoundException e) {
        return ResponseEntity.status(404).body(new ErrorResponse(404, "요청한 리소스를 찾을 수 없습니다."));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception e) {
        log.error("예상하지 못한 오류", e);
        return ResponseEntity.internalServerError().body(new ErrorResponse(500, "일시적인 오류가 발생했습니다."));
    }
}

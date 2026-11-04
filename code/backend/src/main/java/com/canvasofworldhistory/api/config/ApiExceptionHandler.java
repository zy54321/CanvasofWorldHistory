package com.canvasofworldhistory.api.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;

import java.sql.SQLException;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 统一错误响应。
 *
 * 数据库约束是最终裁判，这里只把 JDBC SQLSTATE 翻译成可读的 HTTP 语义，避免把 500 抛给前端：
 *   23505 唯一冲突            → 409
 *   23503 外键不存在/仍被引用 → 400 / 409
 *   23514 CHECK 违反          → 400
 *   23502 NOT NULL 违反       → 400
 *   22P02 文本格式非法        → 400
 *
 * 只依赖 java.sql.SQLException（JDBC 标准），不直接引用 PostgreSQL 驱动类——
 * 驱动在 pom 里是 runtime scope，编译期不可见，也不该让 API 层耦合具体驱动。
 */
@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    private static final Pattern CONSTRAINT =
            Pattern.compile("constraint\\s+\"([^\"]+)\"", Pattern.CASE_INSENSITIVE);
    private static final Pattern COLUMN =
            Pattern.compile("column\\s+\"([^\"]+)\"", Pattern.CASE_INSENSITIVE);

    @ExceptionHandler(WriteForbiddenException.class)
    public ResponseEntity<Map<String, Object>> handleWriteForbidden(WriteForbiddenException ex) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", HttpStatus.FORBIDDEN.value());
        m.put("error", "WRITE_FORBIDDEN");
        m.put("message", ex.getMessage());
        m.put("database", ex.getDatabase());
        m.put("allowedDatabases", ex.getAllowedDatabases());
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .contentType(MediaType.APPLICATION_JSON).body(m);
    }

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<Map<String, Object>> handleStatus(ResponseStatusException ex) {
        HttpStatus status = HttpStatus.resolve(ex.getStatusCode().value());
        if (status == null) {
            status = HttpStatus.INTERNAL_SERVER_ERROR;
        }
        String msg = ex.getReason() == null ? status.getReasonPhrase() : ex.getReason();
        return body(status, msg, null);
    }

    @ExceptionHandler(DataAccessException.class)
    public ResponseEntity<Map<String, Object>> handleData(DataAccessException ex) {
        SQLException sql = findSql(ex);
        if (sql != null) {
            String state = sql.getSQLState();
            String raw = sql.getMessage() == null ? "" : sql.getMessage();
            String constraint = firstGroup(CONSTRAINT, raw);

            if ("23505".equals(state)) {
                return body(HttpStatus.CONFLICT,
                        "违反唯一约束" + suffix(constraint)
                                + "：同一主体下不允许重复的同类记录（如同一人物同类型同语言的重名）",
                        constraint);
            }
            if ("23503".equals(state)) {
                boolean stillReferenced = raw.contains("is still referenced")
                        || raw.contains("still referenced");
                return body(stillReferenced ? HttpStatus.CONFLICT : HttpStatus.BAD_REQUEST,
                        stillReferenced
                                ? "该对象仍被其他记录引用，不允许删除" + suffix(constraint)
                                : "引用的对象不存在" + suffix(constraint),
                        constraint);
            }
            if ("23514".equals(state)) {
                return body(HttpStatus.BAD_REQUEST,
                        "违反数据校验规则" + suffix(constraint)
                                + "：请检查年份与精度是否成对、区间起止是否倒挂、必填是否非空",
                        constraint);
            }
            if ("23502".equals(state)) {
                return body(HttpStatus.BAD_REQUEST,
                        "必填字段缺失" + suffix(firstGroup(COLUMN, raw)), constraint);
            }
            if ("22P02".equals(state)) {
                return body(HttpStatus.BAD_REQUEST, "字段格式非法：" + raw, constraint);
            }
        }
        log.warn("未归类的数据访问异常", ex);
        return body(HttpStatus.INTERNAL_SERVER_ERROR, "数据库操作失败", null);
    }

    @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class)
    public ResponseEntity<Map<String, Object>> handleUnreadable(Exception ex) {
        return body(HttpStatus.BAD_REQUEST, "请求体不是合法 JSON，或字段类型不匹配", null);
    }

    @ExceptionHandler(org.springframework.web.method.annotation.MethodArgumentTypeMismatchException.class)
    public ResponseEntity<Map<String, Object>> handleTypeMismatch(Exception ex) {
        return body(HttpStatus.BAD_REQUEST, "参数类型不正确：" + ex.getMessage(), null);
    }

    private static String suffix(String constraint) {
        return constraint == null ? "" : "（" + constraint + "）";
    }

    private static String firstGroup(Pattern p, String s) {
        Matcher m = p.matcher(s);
        return m.find() ? m.group(1) : null;
    }

    private static ResponseEntity<Map<String, Object>> body(HttpStatus status, String message,
                                                            String constraint) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("status", status.value());
        m.put("error", status.getReasonPhrase());
        m.put("message", message);
        if (constraint != null) {
            m.put("constraint", constraint);
        }
        return ResponseEntity.status(status).contentType(MediaType.APPLICATION_JSON).body(m);
    }

    private static SQLException findSql(Throwable t) {
        Throwable cur = t;
        int guard = 0;
        while (cur != null && guard++ < 12) {
            if (cur instanceof SQLException s) {
                return s;
            }
            cur = cur.getCause();
        }
        return null;
    }
}

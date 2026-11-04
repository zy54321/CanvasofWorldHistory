package com.canvasofworldhistory.api.config;

import java.util.List;

/** 未获写入许可时的业务异常，由 ApiExceptionHandler 统一翻译成 403。 */
public class WriteForbiddenException extends RuntimeException {

    private final String database;
    private final List<String> allowedDatabases;

    public WriteForbiddenException(String message, String database, List<String> allowedDatabases) {
        super(message);
        this.database = database;
        this.allowedDatabases = allowedDatabases;
    }

    public String getDatabase() {
        return database;
    }

    public List<String> getAllowedDatabases() {
        return allowedDatabases;
    }
}

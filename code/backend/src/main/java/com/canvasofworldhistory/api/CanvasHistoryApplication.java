package com.canvasofworldhistory.api;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 世界历史时空画布 · 只读查询 API。
 *
 * 阶段四 M1 只做「读」：不改 Migration、不改表结构、不写业务表。
 * Flyway 在 application.yml 中被显式关闭 —— 迁移的唯一入口是 ops/flyway.sh，
 * 后端启动不得成为 DDL 入口。
 */
@SpringBootApplication
public class CanvasHistoryApplication {
    public static void main(String[] args) {
        SpringApplication.run(CanvasHistoryApplication.class, args);
    }
}

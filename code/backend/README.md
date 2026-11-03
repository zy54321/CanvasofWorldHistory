# backend —— Spring Boot 服务（阶段四开始施工）

本目录当前只放数据库迁移脚本的版本化目录，应用工程在阶段四建立。

## 已确定的目录结构（依据 `02_系统架构设计.md` §5）

```text
backend/
  pom.xml                                  # 阶段四建立
  src/main/java/com/canvasofhistory/
    CanvasOfHistoryApplication.java
    modules/
      place/{api,application,domain,infrastructure}/
      person/…
      event/…
      source/…
      dataimport/…
    shared/{config,exception,persistence}/
  src/main/resources/
    application.yml                        # 阶段四建立（数据源从环境变量读取）
    db/migration/                          # Flyway 版本化 SQL，唯一 DDL 入口
      V1__enable_extensions.sql            # 已执行：PostGIS 扩展，移除 tiger/topology
      V2__core_data_model.sql              # 已执行：九张表 + 约束 + 索引（CORE §5.1–§5.9）
      V3__derived_views.sql                # 已执行：三个派生视图（CORE §5.10）
      V4__…                                # 阶段四：人物、事件及关联（独立迁移，不改 V2）
```

## 迁移执行方式

阶段二用 Docker 里的 Flyway CLI 执行（`ops/flyway.sh`），阶段四接入 Spring Boot 后由
Flyway 自动接管同一目录，**不需要重写任何脚本**。后端只需：

```yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: false   # 禁止基线绕过
  datasource:
    url: jdbc:postgresql://db:5432/${POSTGRES_DB}
    username: ${POSTGRES_USER}
    password: ${POSTGRES_PASSWORD}
```

注意：迁移文件的 checksum 已在 `flyway_schema_history` 中记录，**已执行过的文件不得再修改**，
后续变更一律新增 V4、V5…

## 约定

- 数据库 schema 只通过 Flyway 迁移变更，禁止手工改表。
- 数据源地址、账号、密码来自环境变量（`SPRING_DATASOURCE_*`），由 `docker-compose.yml` 注入。
- 模块间只通过 application/service 接口交互，不跨模块直接用对方 Repository。

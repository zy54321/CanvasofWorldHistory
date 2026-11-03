-- V1：PostGIS 基础设施扩展
-- 归属：数据库初始化阶段的第 1 个版本，早于任何业务表 DDL（业务表从 V2 开始）。
-- 执行方式：由后端 Spring Boot 启动时的 Flyway 自动执行（阶段四接入），
--           本阶段仅入库版本化文件，不手工执行 DDL。
--
-- 设计依据：02_系统架构设计 §6（PostgreSQL + PostGIS，WGS84/EPSG:4326，版本化 Migration）

CREATE EXTENSION IF NOT EXISTS postgis;

-- 精简：本项目不做美国地址地理编码、不做拓扑网络编辑。
-- postgis/postgis 镜像默认预装这两个扩展并附带 40+ 张无关表，会干扰
-- 阶段二「表/字段/约束逐项核对」的核对面，故在此显式移除。
DROP EXTENSION IF EXISTS postgis_tiger_geocoder;
DROP EXTENSION IF EXISTS postgis_topology;

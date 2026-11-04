package com.canvasofworldhistory.api.config;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 数据库写入闸门。
 *
 * <p>设计要点（为什么不是一个 {@code ALLOW_WRITE=true} 全局开关）：
 * <ul>
 *   <li><b>以实际连接的库名为准</b>：启动时向数据库查 {@code current_database()}，
 *       而不是看端口、看配置文件里写的库名——端口可以随便映射，配置可以写错。</li>
 *   <li><b>白名单精确匹配</b>：只有 {@code app.write.allowed-databases} 里逐字列出的库名才允许写。
 *       默认空 = 全库禁写（fail-closed）。</li>
 *   <li><b>不支持通配</b>：出现 {@code *} 之类的通配值视为配置错误并整体拒绝，
 *       避免「为了省事写个星号」把保护废掉。</li>
 *   <li><b>取不到库名也拒绝</b>：任何异常都按不允许写入处理。</li>
 * </ul>
 *
 * <p>正式库 {@code canvas_history} 默认不在白名单内，因此 8088 实例天然只读；
 * 测试库 {@code canvas_history_m2check} 需要显式用
 * {@code DB_WRITE_ALLOWED_DATABASES=canvas_history_m2check} 启动才会放开写入。
 */
@Component
public class WriteGuard {

    private static final Logger log = LoggerFactory.getLogger(WriteGuard.class);

    private final JdbcTemplate jdbc;
    private final List<String> allowedDatabases;
    private final List<String> configProblems;

    /** 启动时解析到的实际库名；解析失败保持 null，任何写入都会被拒。 */
    private volatile String databaseName;

    public WriteGuard(JdbcTemplate jdbc,
                      @Value("${app.write.allowed-databases:}") String allowedCsv) {
        this.jdbc = jdbc;

        List<String> allowed = new ArrayList<>();
        List<String> problems = new ArrayList<>();
        for (String raw : allowedCsv.split(",")) {
            String v = raw.trim();
            if (v.isEmpty()) {
                continue;
            }
            if (v.contains("*") || v.contains("%")) {
                problems.add("白名单不接受通配值: " + v);
                continue;
            }
            allowed.add(v);
        }
        this.allowedDatabases = Collections.unmodifiableList(allowed);
        this.configProblems = Collections.unmodifiableList(problems);
    }

    @PostConstruct
    void detect() {
        resolveDatabaseName();
        if (!configProblems.isEmpty()) {
            log.error("写保护配置有误，已按 fail-closed 处理：{}", configProblems);
        }
        if (isWriteAllowed()) {
            log.warn("写保护：数据库 {} 在白名单内 —— 本实例【允许写入】", databaseName);
        } else {
            log.info("写保护：数据库 {} 不在白名单 {} 内 —— 本实例【禁止写入】（GET 不受影响）",
                    databaseName, allowedDatabases);
        }
    }

    /** 解析实际库名，失败则置 null（= 禁止写入）。 */
    private void resolveDatabaseName() {
        try {
            this.databaseName = jdbc.queryForObject("select current_database()", String.class);
        } catch (Exception ex) {
            this.databaseName = null;
            log.warn("写保护：无法识别当前数据库（{}），按禁止写入处理", ex.toString());
        }
    }

    /**
     * 每次判定都以「实际库名 ∈ 白名单」为准。
     *
     * <p>若启动时数据库尚未就绪导致库名解析失败，这里会再尝试一次（只在为 null 时重试，
     * 成功即缓存）；仍然失败则继续按禁止写入处理 —— 失败方向永远是「更保守」。
     */
    public boolean isWriteAllowed() {
        if (databaseName == null) {
            resolveDatabaseName();
        }
        String current = databaseName;
        if (current == null) {
            return false;
        }
        return configProblems.isEmpty() && allowedDatabases.contains(current);
    }

    public String getDatabaseName() {
        return databaseName;
    }

    public List<String> getAllowedDatabases() {
        return allowedDatabases;
    }

    public List<String> getConfigProblems() {
        return configProblems;
    }

    /** 给拒绝响应/诊断接口用的说明文本。 */
    public String describeDenial() {
        if (databaseName == null) {
            return "无法识别当前连接的数据库，写操作已被拒绝";
        }
        if (!configProblems.isEmpty()) {
            return "写保护配置有误（" + String.join("; ", configProblems) + "），写操作已被拒绝";
        }
        return "数据库 " + databaseName + " 不在写入白名单内，写操作已被拒绝（只读实例）";
    }
}

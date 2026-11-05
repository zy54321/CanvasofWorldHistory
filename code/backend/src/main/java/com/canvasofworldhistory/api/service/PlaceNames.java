package com.canvasofworldhistory.api.service;

import java.util.Locale;
import java.util.Set;

/**
 * 地点名称的「读取侧」判定：占位名识别 + 名称质量互斥分类 + 展示名。
 *
 * 为什么放在读取侧：`historical_place.canonical_name` 与 `source_record` 是原始证据，
 * 不许为了展示去改数据（P0 审计 3,920 条占位名，其中 64 条有可用别名）。
 * 所以这里只做**计算**，任何写路径都不调用它。
 *
 * 分类只有四种，互斥且穷尽：
 *   VALID        规范名称本身是有效地名
 *   ALIAS_ONLY   规范名称缺失或占位，但存在有效别名/历史名称
 *   PLACEHOLDER  规范名称是占位标题，且没有任何有效别名
 *   NO_NAME      规范名称缺失（空/纯空格），且没有任何有效别名
 *
 * PLACEHOLDER 与 NO_NAME 拆开是为了让「源里写了 Untitled」和「源里什么都没写」
 * 在运营上可区分：前者通常还有补救线索（Pleiades 的 name 行），后者只能等人工补录。
 */
public final class PlaceNames {

    private PlaceNames() {
    }

    /** 源里的占位标题。大小写不敏感匹配，见 {@link #isPlaceholder(String)}。 */
    public static final Set<String> PLACEHOLDER_NAMES = Set.of(
            "untitled", "unnamed place", "unnamed", "unknown", "unknown place",
            "n/a", "?", "-", "(unknown)", "no name");

    /**
     * SQL 版占位名清单（与 {@link #PLACEHOLDER_NAMES} 必须一致）。
     * 用小写 + trim 比较，避免 'Untitled'/'untitled'/'UNNAMED PLACE' 漏判。
     */
    public static final String PLACEHOLDER_SQL_LIST =
            "('untitled','unnamed place','unnamed','unknown','unknown place',"
                    + "'n/a','?','-','(unknown)','no name')";

    /** 规范名称是否属于占位标题（含空/纯空格）。 */
    public static boolean isPlaceholder(String canonicalName) {
        if (canonicalName == null) {
            return true;
        }
        String t = canonicalName.trim();
        if (t.isEmpty()) {
            return true;
        }
        return PLACEHOLDER_NAMES.contains(t.toLowerCase(Locale.ROOT));
    }

    /** 规范名称是否属于「完全缺失」（空 / 纯空格），与「写了占位词」区分开。 */
    public static boolean isBlank(String canonicalName) {
        return canonicalName == null || canonicalName.trim().isEmpty();
    }

    /** 名称质量分类码。 */
    public static String quality(String canonicalName, boolean hasUsableName) {
        if (!isPlaceholder(canonicalName)) {
            return "valid";
        }
        if (hasUsableName) {
            return "alias_only";
        }
        return isBlank(canonicalName) ? "no_name" : "placeholder";
    }

    /**
     * 展示名：只返回「可当地名用」的字符串，否则 null。
     *
     * 为什么占位名不能原样返回：`Untitled` / `Unnamed Place` 不是地名，
     * 直接显示会和真实地名混在一起（P0 审计 3,920 条）。原文并没有丢——
     * 调用方拿到的 canonicalName 永远是原值，界面用「未命名地点 · #id」占位。
     */
    public static String displayName(String canonicalName, String firstUsableName) {
        boolean hasAlt = firstUsableName != null && !firstUsableName.trim().isEmpty();
        if (!isPlaceholder(canonicalName)) {
            return canonicalName;
        }
        return hasAlt ? firstUsableName : null;
    }
}

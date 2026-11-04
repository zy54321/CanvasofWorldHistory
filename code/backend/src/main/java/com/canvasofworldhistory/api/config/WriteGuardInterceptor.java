package com.canvasofworldhistory.api.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.Set;

/**
 * 写保护拦截器：挂在 {@code /api/**} 上，对所有非安全方法统一设卡。
 *
 * <p>刻意在拦截器（而不是逐个 Controller 方法）里判断，这样<b>将来新增的写接口自动受保护</b>，
 * 不会因为某个新控制器忘了加注解就漏掉。
 *
 * <p>放行 GET / HEAD / OPTIONS：
 * <ul>
 *   <li>GET / HEAD 是只读，不受影响；</li>
 *   <li>OPTIONS 是 CORS 预检，必须放行，否则浏览器连错误响应都读不到。</li>
 * </ul>
 * 其余方法（POST / PUT / PATCH / DELETE，以及将来任何新增方法）一律要求写入许可。
 */
@Component
public class WriteGuardInterceptor implements HandlerInterceptor {

    private static final Set<String> SAFE_METHODS = Set.of("GET", "HEAD", "OPTIONS");

    private final WriteGuard guard;

    public WriteGuardInterceptor(WriteGuard guard) {
        this.guard = guard;
    }

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String method = request.getMethod();
        if (SAFE_METHODS.contains(method)) {
            return true;
        }
        if (guard.isWriteAllowed()) {
            return true;
        }
        throw new WriteForbiddenException(guard.describeDenial(),
                guard.getDatabaseName(), guard.getAllowedDatabases());
    }
}

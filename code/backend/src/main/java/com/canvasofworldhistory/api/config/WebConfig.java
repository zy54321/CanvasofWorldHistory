package com.canvasofworldhistory.api.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 只允许本机前端端口跨域访问，不对外开放。
 *
 * M2 收尾修正（原配置的两个实际缺陷）：
 *  1. allowedMethods 只有 GET —— M2 引入人物/事件/地点写接口后，浏览器带 Origin 的
 *     POST/PUT/DELETE 会被 CORS 直接拒成 403（表现为「保存失败但不显示原因」）。
 *  2. 端口写死 5180/5173 —— 联调时把前端指向测试库另起一个端口（如 5181）就被拒。
 *     改为只放行 127.0.0.1 / localhost 的任意端口，仍然仅限本机。
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final WriteGuardInterceptor writeGuardInterceptor;

    public WebConfig(WriteGuardInterceptor writeGuardInterceptor) {
        this.writeGuardInterceptor = writeGuardInterceptor;
    }

    /**
     * 写保护挂在整个 /api/** 上（含未来新增的写接口），GET/HEAD/OPTIONS 不受影响。
     * 详见 {@link WriteGuard}。
     */
    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(writeGuardInterceptor).addPathPatterns("/api/**");
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOriginPatterns("http://127.0.0.1:[*]", "http://localhost:[*]")
                .allowedMethods("GET", "POST", "PUT", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .maxAge(3600);
    }
}

# CDN 缓存

> 把内容推到离用户最近的节点，降低延迟，减轻源站压力。

---

## 1. 核心问题

用户分布全球，静态资源从源站加载慢。每次请求都回源，源站压力大。

CDN（Content Delivery Network）在网络边缘缓存内容，用户就近获取。但缓存策略配错会导致：内容更新了用户看到旧版，或者根本不缓存白白浪费。

---

## 2. Cache-Control 策略

```
# 静态资源（带哈希指纹）：长期缓存
Cache-Control: public, max-age=31536000, immutable
# 文件名如 app.a3f8b2c1.js，内容变了文件名就变

# HTML 入口文件：不缓存或短缓存
Cache-Control: no-cache  # 每次回源验证（ETag/Last-Modified）
# 或
Cache-Control: max-age=300  # 缓存 5 分钟

# API 响应：按业务决定
Cache-Control: private, max-age=60  # 用户特定数据，缓存 1 分钟
Cache-Control: public, max-age=3600  # 公开数据，缓存 1 小时
```

**核心原则**: 能加哈希的加哈希（长期缓存），不能加哈希的用 `no-cache`（验证缓存），API 按更新频率设 TTL。

---

## 3. CloudFront 配置

```yaml
# CloudFront Cache Policy（Terraform）
resource "aws_cloudfront_cache_policy" "static" {
  name        = "static-assets"
  default_ttl = 86400
  max_ttl     = 31536000
  min_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "all"
    }
  }
}

# 缓存失效
resource "null_resource" "invalidate" {
  triggers = { files_hash = filemd5("dist/manifest.json") }

  provisioner "local-exec" {
    command = "aws cloudfront create-invalidation --distribution-id $ID --paths '/index.html'"
  }
}
```

静态资源走 CloudFront，HTML 用 `/index.html` 失效策略。只失效入口文件，不批量失效所有资源。

---

## 4. Cloudflare 配置

```toml
# wrangler.toml 或 Page Rules
[[rules]]
  expression = "example.com/assets/*"
  cache_level = "aggressive"
  edge_ttl = 2592000  # 30 天

[[rules]]
  expression = "example.com/api/*"
  cache_level = "bypass"  # API 不缓存
```

Cloudflare 的优势：自带 WAF、DDoS 防护、Workers 可编程缓存逻辑。

---

## 5. 缓存失效策略

| 策略 | 实现 | 适合场景 |
|------|------|---------|
| 哈希指纹 | 文件名含 hash，内容变文件名变 | 静态资源 |
| 主动失效 | API 调用 CDN invalidation API | HTML、配置文件 |
| 版本化 | URL 带版本号 `/v2/style.css` | 版本发布 |
| TTL 过期 | Cache-Control 控制 | 低频更新内容 |

```bash
# 批量失效有成本（CloudFront $0.005/前 1000 个路径）
# ✅ 只失效关键路径
aws cloudfront create-invalidation --distribution-id EXX --paths "/index.html" "/manifest.json"

# ❌ 不要失效所有资源
aws cloudfront create-invalidation --distribution-id EXX --paths "/*"
```

---

## 6. Origin Shield

Origin Shield 是 CDN 和源站之间的额外缓存层。当多个边缘节点同时回源时，由 Origin Shield 统一回源，减少源站压力。

```
用户 → 边缘节点 → Origin Shield → 源站
```

适合场景：源站带宽有限、热点内容多、全球用户分布广。CloudFront 和 Cloudflare 都支持。

---

## 相关文档

- [[docs/caching/redis|Redis]] — 应用层缓存
- [[docs/caching/README|缓存规范首页]] — 缓存模式与策略
- [[docs/devops/docker|Docker]] — 容器化部署
- [[docs/security/owasp|OWASP]] — CDN 安全配置
- [[docs/api/rest|REST]] — API 响应缓存头设计

---

*本规范随 CDN 服务演进持续更新。最后更新: 2026-07-20*

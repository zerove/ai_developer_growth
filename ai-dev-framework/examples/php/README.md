# PHP 示例项目

> 配合 ai-dev-framework 使用的 PHP 项目模板

---

## 项目结构

```
.
├── src/
│   └── App.php
├── tests/
│   └── AppTest.php
├── composer.json
├── phpstan.neon
└── .php-cs-fixer.dist.php
```

---

## 质量门禁

```bash
# Lint
phpstan analyse src/ --level=max

# 测试
./vendor/bin/phpunit

# 格式检查
php-cs-fixer fix --dry-run src/
```

---

## composer.json

```json
{
    "name": "my/app",
    "require": {
        "php": ">=8.2"
    },
    "require-dev": {
        "phpunit/phpunit": "^11.0",
        "phpstan/phpstan": "^1.10",
        "friendsofphp/php-cs-fixer": "^3.0"
    },
    "autoload": {
        "psr-4": {
            "App\\": "src/"
        }
    }
}
```

---
title: Django Governance Rules
description: > 适用于 Django 项目的 AI Agent 开发规范。
category: 工具层
tags: ['AI', 'REST', 'API', 'Python', '测试']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# Django Governance Rules

> 适用于 Django 项目的 AI Agent 开发规范。

---

## 1. 项目结构

### 应用组织

```python
# ✅ 正确: 功能模块化
myproject/
├── apps/
│   ├── users/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── serializers.py
│   │   └── tests.py
│   └── posts/
├── config/
│   ├── settings/
│   └── urls.py
└── manage.py

# ❌ 禁止: 单一应用包含所有
myapp/
├── models.py  # 包含所有模型
├── views.py   # 包含所有视图
└── tests.py   # 包含所有测试
```

### 设置模块化

```python
# config/settings/base.py
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    # 第三方
    "rest_framework",
    # 本地
    "apps.users",
    "apps.posts",
]

# config/settings/production.py
from .base import *

DEBUG = False
ALLOWED_HOSTS = ["example.com"]
```

---

## 2. 模型规范

### 模型设计

```python
from django.db import models
from django.contrib.auth.models import AbstractUser


# ✅ 正确
class User(AbstractUser):
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email


class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
```

### 禁止行为

```python
# ❌ 禁止: 无 related_name
class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)  # 应添加 related_name


# ❌ 禁止: 无 __str__
class Post(models.Model):
    title = models.CharField(max_length=200)
    # 缺少 __str__ 方法
```

---

## 3. 视图规范

### DRF ViewSets

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import User
from .serializers import UserSerializer
from .permissions import IsOwnerOrReadOnly


# ✅ 正确
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsOwnerOrReadOnly]

    @action(detail=False, methods=["get"])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
```

### 函数视图 (简单场景)

```python
from django.http import JsonResponse
from django.views.decorators.http import require_GET


# ✅ 正确
@require_GET
def health_check(request):
    return JsonResponse({"status": "ok"})
```

---

## 4. 序列化器规范

### 序列化器设计

```python
from rest_framework import serializers
from .models import User, Post


# ✅ 正确
class PostSerializer(serializers.ModelSerializer):
    author = serializers.StringRelatedField()

    class Meta:
        model = Post
        fields = ["id", "title", "content", "author", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserSerializer(serializers.ModelSerializer):
    posts = PostSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "bio", "posts"]
        read_only_fields = ["id"]
```

### 验证

```python
class CreateUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
```

---

## 5. 中间件与装饰器

### 自定义中间件

```python
# ✅ 正确
class RequestLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        # 处理异常
        pass
```

### 认证装饰器

```python
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods


# ✅ 正确
@login_required
@require_http_methods(["GET", "POST"])
def my_view(request):
    pass
```

---

## 6. 测试规范

### 单元测试

```python
from django.test import TestCase
from .models import User


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(email="test@example.com", password="testpass123")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("testpass123"))
```

### API 测试

```python
from rest_framework.test import APITestCase
from rest_framework import status


class UserAPITest(APITestCase):
    def test_list_users(self):
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_user(self):
        data = {"email": "test@example.com", "password": "testpass123"}
        response = self.client.post("/api/users/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
```

---

## 7. 安全规范

### CSRF 防护

```python
# ✅ 正确: Django 默认启用 CSRF
# 确保模板中使用 {% csrf_token %}
<form method="post">
    {% csrf_token %}
    <!-- 表单内容 -->
</form>
```

### SQL 注入防护

```python
# ❌ 禁止: 原始 SQL
User.objects.raw(f"SELECT * FROM users WHERE id = {user_id}")

# ✅ 正确: 使用 ORM
User.objects.filter(id=user_id)
```

### 密钥管理

```python
# ❌ 禁止
SECRET_KEY = "YOUR_API_KEY_HERE"

# ✅ 正确
import os

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY not set")
```

---

## 8. 质量检查清单

### 代码质量

- [ ] Black 格式化通过
- [ ] Flake8 无错误
- [ ] isort 排序正确
- [ ] 无硬编码密钥
- [ ] 模型有 __str__ 方法

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用 TestCase 而非 unittest
- [ ] API 测试完整

### 安全

- [ ] CSRF 防护启用
- [ ] 使用 ORM 防止 SQL 注入
- [ ] 认证和权限正确配置

---

*本规范随 Django 生态演进持续更新。最后更新: 2026-07-17*

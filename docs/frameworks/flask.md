---
title: Flask Governance Rules
description: > 适用于 Flask 项目的 AI Agent 开发规范。
category: 工具层
tags: ['测试', 'AI', 'API', 'Python']
difficulty: 初级
reading_time: 10 分钟
updated: 2026-07-21
---

# Flask Governance Rules

> 适用于 Flask 项目的 AI Agent 开发规范。

---

## 1. 项目结构

### 应用工厂模式

```
project/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── extensions.py
│   ├── models/
│   ├── services/
│   ├── repositories/
│   ├── api/
│   │   ├── __init__.py
│   │   └── users.py
│   └── utils/
├── tests/
├── requirements.txt
└── README.md
```

### 应用工厂

```python
from flask import Flask
from .extensions import db, migrate

def create_app(config_class='config.Config'):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    register_extensions(app)
    register_blueprints(app)
    
    return app

def register_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)

def register_blueprints(app):
    from .api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
```

---

## 2. 路由规范

### Blueprint 组织

```python
from flask import Blueprint, request, jsonify
from .services import UserService

api_bp = Blueprint('api', __name__)

# ✅ 正确
@api_bp.route('/users', methods=['GET'])
def list_users():
    users = UserService.get_all()
    return jsonify([u.to_dict() for u in users])

@api_bp.route('/users/<string:id>', methods=['GET'])
def get_user(id):
    user = UserService.get_by_id(id)
    if not user:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(user.to_dict())
```

### 请求验证

```python
from flask import request
from marshmallow import Schema, fields, validate

class CreateUserSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1))
    email = fields.Email(required=True)

# ✅ 正确
@api_bp.route('/users', methods=['POST'])
def create_user():
    schema = CreateUserSchema()
    errors = schema.validate(request.json)
    if errors:
        return jsonify({'errors': errors}), 400
    
    data = schema.load(request.json)
    user = UserService.create(data)
    return jsonify(user.to_dict()), 201
```

---

## 3. 服务规范

### 服务设计

```python
from .repositories import UserRepository
from .exceptions import NotFoundError, ValidationError

class UserService:
    @staticmethod
    def get_all():
        return UserRepository.find_all()
    
    @staticmethod
    def get_by_id(id):
        user = UserRepository.find_by_id(id)
        if not user:
            raise NotFoundError('User', id)
        return user
    
    @staticmethod
    def create(data):
        existing = UserRepository.find_by_email(data['email'])
        if existing:
            raise ValidationError('Email already exists')
        
        return UserRepository.create(data)

# ❌ 禁止: 在路由中包含业务逻辑
@api_bp.route('/users', methods=['POST'])
def create_user():
    data = request.json
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Exists'}), 400
    
    user = User(**data)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201
```

---

## 4. 错误处理

### 自定义异常

```python
class AppError(Exception):
    def __init__(self, message, status_code=500):
        self.message = message
        self.status_code = status_code

class NotFoundError(AppError):
    def __init__(self, resource, id):
        super().__init__(f'{resource} with id {id} not found', 404)

class ValidationError(AppError):
    def __init__(self, message):
        super().__init__(message, 400)

# 错误处理器
@app.errorhandler(AppError)
def handle_app_error(error):
    return jsonify({'error': error.message}), error.status_code
```

---

## 5. 测试规范

### pytest

```python
import pytest
from app import create_app

@pytest.fixture
def app():
    app = create_app('config.TestingConfig')
    with app.app_context():
        yield app

@pytest.fixture
def client(app):
    return app.test_client()

def test_list_users(client):
    response = client.get('/api/users')
    assert response.status_code == 200
    assert isinstance(response.json, list)

def test_create_user(client):
    response = client.post('/api/users', json={
        'name': 'John',
        'email': 'john@example.com'
    })
    assert response.status_code == 201
    assert response.json['name'] == 'John'
```

### Mock

```python
from unittest.mock import patch, MagicMock

def test_get_user():
    with patch('app.services.user.UserRepository') as mock_repo:
        mock_repo.find_by_id.return_value = MagicMock(id='123')
        
        user = UserService.get_by_id('123')
        assert user.id == '123'
```

---

## 6. 安全规范

### 密钥管理

```python
# ❌ 禁止
SECRET_KEY = 'YOUR_API_KEY_HERE'

# ✅ 正确
import os
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError('SECRET_KEY not set')
```

### CSRF 防护

```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)

# 模板中使用 {{ csrf_token() }}
```

---

## 7. 质量检查清单

### 代码质量

- [ ] Black 格式化通过
- [ ] Flake8 无错误
- [ ] 使用 Blueprint 组织路由
- [ ] 业务逻辑在服务层
- [ ] 无硬编码密钥

### 测试质量

- [ ] 核心逻辑测试覆盖 > 80%
- [ ] 所有测试通过
- [ ] 使用测试客户端
- [ ] Mock 使用正确

### 安全

- [ ] CSRF 防护启用
- [ ] 输入验证完整
- [ ] 密钥管理正确

---

*本规范随 Flask 生态演进持续更新。最后更新: 2026-07-17*

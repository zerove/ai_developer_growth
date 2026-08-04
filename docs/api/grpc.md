---
title: gRPC Governance Rules
description: > 适用于 gRPC 项目的 AI Agent 开发规范。
category: 工具层
tags: ['测试', 'AI', 'Python']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# gRPC Governance Rules

> 适用于 gRPC 项目的 AI Agent 开发规范。

---

## 1. Proto 设计

### 服务定义

```protobuf
// ✅ 正确: 清晰的服务定义
syntax = "proto3";

package user.v1;

service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
  rpc ListUsers(ListUsersRequest) returns (ListUsersResponse);
  rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);
  rpc UpdateUser(UpdateUserRequest) returns (UpdateUserResponse);
  rpc DeleteUser(DeleteUserRequest) returns (DeleteUserResponse);
}

// ❌ 禁止: 不清晰的服务定义
service User {
  rpc Get(Req) returns (Res);  // 应明确名称
}
```

### 消息设计

```protobuf
// ✅ 正确: 使用消息类型
message User {
  string id = 1;
  string email = 2;
  string name = 3;
  google.protobuf.Timestamp created_at = 4;
}

message GetUserRequest {
  string id = 1;
}

message GetUserResponse {
  User user = 1;
}

// ❌ 禁止: 使用通用消息
message Request {
  string id = 1;
  string type = 2;
  bytes data = 3;
}
```

---

## 2. 版本控制

### 包版本

```protobuf
// ✅ 正确: 使用包版本
package user.v1;

service UserService {
  // v1 方法
}

// 新版本
package user.v2;

service UserService {
  // v2 方法
}
```

### 字段编号

```protobuf
// ✅ 正确: 使用保留字段号
message User {
  reserved 2, 15, 9 to 11;
  reserved "old_field";
  
  string id = 1;
  string name = 3;
}

// ❌ 禁止: 重用字段号
message User {
  string id = 1;
  string name = 2;  // 已删除
  string email = 2;  // 重用字段号，会导致兼容性问题
}
```

---

## 3. 错误处理

### 状态码使用

```python
# ✅ 正确: 使用合适的 gRPC 状态码
from grpc import StatusCode

async def get_user(self, request, context):
    user = await db.find_user(request.id)
    if not user:
        context.set_code(StatusCode.NOT_FOUND)
        context.set_details(f'User {request.id} not found')
        return GetUserResponse()
    
    return GetUserResponse(user=user)
```

### 错误详情

```python
# ✅ 正确: 使用 grpc-status-details-bin
from google.rpc import status_pb2, error_details_pb2

async def create_user(self, request, context):
    if not is_valid_email(request.email):
        status = status_pb2.Status(
            code=StatusCode.INVALID_ARGUMENT.value,
            message='Invalid email'
        )
        detail = error_details_pb2.BadRequest(
            field_violations=[
                error_details_pb2.BadRequest.FieldViolation(
                    field='email',
                    description='Invalid email format'
                )
            ]
        )
        context.abort_with_status(
            gRPCStatus(StatusCode.INVALID_ARGUMENT, 'Invalid email')
        )
```

---

## 4. 流式处理

### 服务端流式

```protobuf
// ✅ 正确: 服务端流式
rpc ListUsers(ListUsersRequest) returns (stream User);
```

```python
# ✅ 正确: 实现服务端流式
async def list_users(self, request, context):
    async for user in db.stream_users():
        if context.is_cancelled():
            break
        yield UserResponse(user=user)
```

### 客户端流式

```protobuf
// ✅ 正确: 客户端流式
rpc UploadUsers(stream User) returns (UploadUsersResponse);
```

### 双向流式

```protobuf
// ✅ 正确: 双向流式
rpc Chat(stream ChatMessage) returns (stream ChatMessage);
```

---

## 5. 拦截器

### 认证拦截器

```python
# ✅ 正确: 认证拦截器
class AuthInterceptor(grpc.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        # 验证 token
        token = extract_token(handler_call_details.invocation_metadata)
        if not verify_token(token):
            return grpc.unary_unary_rpc_method_handler(
                lambda req, ctx: context.abort(StatusCode.UNAUTHENTICATED, 'Invalid token')
            )
        
        return await continuation(handler_call_details)
```

### 日志拦截器

```python
# ✅ 正确: 日志拦截器
class LoggingInterceptor(grpc.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
        start_time = time.time()
        response = await continuation(handler_call_details)
        duration = time.time() - start_time
        
        logger.info(
            f'{handler_call_details.method} completed in {duration:.3f}s'
        )
        return response
```

---

## 6. 测试规范

### 单元测试

```python
import pytest
from grpc import aio

@pytest.mark.asyncio
async def test_get_user():
    server = aio.server()
    server.add_insecure_port('[::]:50051')
    UserServiceServicer.register(server)
    
    await server.start()
    
    async with aio.insecure_channel('localhost:50051') as channel:
        stub = UserServiceStub(channel)
        response = await stub.GetUser(GetUserRequest(id='123'))
        assert response.user.id == '123'
    
    await server.stop(None)
```

### 集成测试

```python
@pytest.mark.asyncio
async def test_create_user_flow():
    async with create_test_channel() as channel:
        stub = UserServiceStub(channel)
        
        # 创建用户
        create_response = await stub.CreateUser(
            CreateUserRequest(email='test@example.com', name='John')
        )
        user_id = create_response.user.id
        
        # 查询用户
        get_response = await stub.GetUser(GetUserRequest(id=user_id))
        assert get_response.user.email == 'test@example.com'
```

---

## 7. 性能优化

### 连接池

```python
# ✅ 正确: 使用连接池
import grpc
from grpc import aio

channel = aio.insecure_channel(
    'localhost:50051',
    options=[
        ('grpc.keepalive_time_ms', 10000),
        ('grpc.keepalive_timeout_ms', 5000),
        ('grpc.max_send_message_length', 50 * 1024 * 1024),
        ('grpc.max_receive_message_length', 50 * 1024 * 1024),
    ]
)
```

### 压缩

```python
# ✅ 正确: 启用压缩
channel = aio.insecure_channel(
    'localhost:50051',
    compression=grpc.Compression.Gzip
)
```

---

## 8. 质量检查清单

### Proto 设计

- [ ] 服务定义清晰
- [ ] 消息类型明确
- [ ] 版本控制正确
- [ ] 字段编号保留

### 错误处理

- [ ] 状态码正确
- [ ] 错误详情完整
- [ ] 重试策略配置

### 性能

- [ ] 连接池使用
- [ ] 压缩启用
- [ ] 超时配置
- [ ] 负载均衡

---

*本规范随 gRPC 生态演进持续更新。最后更新: 2026-07-17*

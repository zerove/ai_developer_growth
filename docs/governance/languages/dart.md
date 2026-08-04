---
title: Dart Governance Rules
description: > 适用于: Dart 项目 (Flutter, 后端服务)
category: 治理层
tags: ['测试', 'AI', 'API']
difficulty: 基础
reading_time: 10 分钟
updated: 2026-07-21
---

# Dart Governance Rules

> 适用于: Dart 项目 (Flutter, 后端服务)

---

## 1. 代码规范

### 格式化

```bash
# Dart formatter
dart format .

# 分析
dart analyze
```

### Linting

```yaml
# analysis_options.yaml
include: package:flutter_lints/flutter.yaml

linter:
  rules:
    - prefer_const_constructors
    - prefer_const_declarations
    - avoid_print
    - prefer_single_quotes
    - require_trailing_commas
    - avoid_unnecessary_containers
    - prefer_is_empty
    - prefer_is_not_empty
```

### 命名规范

```dart
// ✅ 正确
class UserProfile { }        // PascalCase (类名)
String userName = 'Alice';   // camelCase (变量/函数)
const int maxRetries = 3;    // camelCase (常量)
void getUserData() {}        // camelCase (函数)
static const apiUrl = '...'; // camelCase (静态常量)

// ❌ 禁止
class user_profile { }       // 应使用 PascalCase
String user_name = 'Alice';  // 应使用 camelCase
const int MAX_RETRIES = 3;   // 应使用 camelCase
```

---

## 2. 错误处理

### 异常处理

```dart
// ✅ 正确 - 使用 try/catch
Future<User> getUser(String id) async {
  try {
    final response = await http.get(Uri.parse('/users/$id'));
    if (response.statusCode == 200) {
      return User.fromJson(jsonDecode(response.body));
    } else {
      throw ServerException('Failed to load user');
    }
  } catch (e) {
    throw ServerException('Network error: $e');
  }
}

// ✅ 正确 - 自定义异常
class ServerException implements Exception {
  final String message;
  ServerException(this.message);
  
  @override
  String toString() => 'ServerException: $message';
}

// ❌ 禁止
Future<User> getUser(String id) async {
  final response = await http.get(Uri.parse('/users/$id'));
  return User.fromJson(jsonDecode(response.body)); // 未处理错误
}
```

### Result 类型

```dart
// ✅ 正确 - 使用 sealed class
sealed class Result<T> {}

class Success<T> extends Result<T> {
  final T data;
  Success(this.data);
}

class Failure<T> extends Result<T> {
  final Exception error;
  Failure(this.error);
}

// 使用
Result<User> result = await getUser(id);
switch (result) {
  case Success(:final data):
    print('User: ${data.name}');
  case Failure(:final error):
    print('Error: $error');
}
```

---

## 3. Flutter 特定

### Widget 设计

```dart
// ✅ 正确 - const 构造函数
class UserCard extends StatelessWidget {
  final String name;
  final String email;
  
  const UserCard({
    super.key,
    required this.name,
    required this.email,
  });
  
  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: [
          Text(name),
          Text(email),
        ],
      ),
    );
  }
}

// ✅ 正确 - 使用 const
const UserCard(
  name: 'Alice',
  email: 'alice@example.com',
);

// ❌ 禁止
UserCard(  // 缺少 const
  name: 'Alice',
  email: 'alice@example.com',
);
```

### 状态管理

```dart
// ✅ 正确 - 使用 Riverpod
final userProvider = StateNotifierProvider<UserNotifier, User?>(
  (ref) => UserNotifier(),
);

class UserNotifier extends StateNotifier<User?> {
  UserNotifier() : super(null);
  
  void updateUser(User user) {
    state = user;
  }
}

// ❌ 禁止 - 使用 Provider (新项目)
final userProvider = Provider<User?>((ref) => null);
```

---

## 4. 异步编程

### Future/Async

```dart
// ✅ 正确 - async/await
Future<User> fetchUser(String id) async {
  final response = await http.get(Uri.parse('/users/$id'));
  if (response.statusCode == 200) {
    return User.fromJson(jsonDecode(response.body));
  }
  throw Exception('Failed to load user');
}

// ✅ 正确 - 并行执行
Future<Dashboard> getDashboard() async {
  final results = await Future.wait([
    fetchUser(),
    fetchPosts(),
    fetchNotifications(),
  ]);
  return Dashboard(
    user: results[0],
    posts: results[1],
    notifications: results[2],
  );
}

// ❌ 禁止 - 顺序执行不必要的异步操作
Future<Dashboard> getDashboard() async {
  final user = await fetchUser();
  final posts = await fetchPosts(); // 可以并行
  final notifications = await fetchNotifications(); // 可以并行
  return Dashboard(user, posts, notifications);
}
```

---

## 5. 空安全

### 空安全

```dart
// ✅ 正确 - 使用可空类型
String? nullableName;
String nonNullName = 'Alice';

// ✅ 正确 - 空值检查
if (nullableName != null) {
  print(nullableName.length);
}

// ✅ 正确 - 使用 ?? 和 ?.
final name = nullableName ?? 'Unknown';
final length = nullableName?.length ?? 0;

// ❌ 禁止 - 使用 bang operator 过多
final length = nullableName!.length; // 可能抛出异常
```

---

## 6. 测试

```dart
// ✅ 正确 - 单元测试
void main() {
  group('UserService', () {
    test('should create user with valid data', () async {
      final service = UserService();
      final user = await service.createUser(name: 'Alice');
      expect(user.name, equals('Alice'));
      expect(user.id, isNotNull);
    });
    
    test('should throw on invalid email', () {
      final service = UserService();
      expect(
        () => service.createUser(email: 'invalid'),
        throwsA(isA<ValidationException>()),
      );
    });
  });
}

// ✅ 正确 - Widget 测试
testWidgets('UserCard should display user info', (tester) async {
  await tester.pumpWidget(
    MaterialApp(
      home: UserCard(
        name: 'Alice',
        email: 'alice@example.com',
      ),
    ),
  );
  
  expect(find.text('Alice'), findsOneWidget);
  expect(find.text('alice@example.com'), findsOneWidget);
});
```

---

## 7. 禁止行为

| 行为 | 原因 |
|------|------|
| 使用 `dynamic` | 尽量使用具体类型 |
| 使用 `print()` | 使用 logging 或 debugPrint |
| 忽略 lint 警告 | 所有警告都应该修复 |
| 使用 `var` (不确定类型) | 使用 `final` 或显式类型 |
| 在 Widget 中放业务逻辑 | 分离关注点 |

---

*最后更新: 2026-07-21*

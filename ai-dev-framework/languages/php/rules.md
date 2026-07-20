# PHP 语言规则

> 适用于 PHP 项目的 AI Agent 开发规则

---

## 代码风格

### 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件名 | PascalCase | `MyClass.php` |
| 方法名 | camelCase | `myMethod()` |
| 变量名 | camelCase | `$myVariable` |
| 类名 | PascalCase | `MyClass` |
| 接口 | PascalCase | `MyInterface` |
| 常量 | UPPER_SNAKE_CASE | `MAX_SIZE` |

### 导入顺序

```php
// 1. 标准库
use Exception;
use PDO;

// 2. 第三方库
use Monolog\Logger;
use Illuminate\Http\Request;

// 3. 本地模块
use App\Services\MyService;
```

---

## 错误处理

```php
// ✅ 正确
function myFunction(): string
{
    try {
        $result = doSomething();
        return $result;
    } catch (SpecificException $e) {
        throw new MyException("Failed: {$e->getMessage()}", 0, $e);
    }
}

// ❌ 错误
function myFunction(): ?string
{
    try {
        return doSomething();
    } catch (Exception $e) {
        return null;
    }
}
```

---

## 测试

```php
class MyFunctionTest extends TestCase
{
    public function testSuccess()
    {
        $this->assertEquals(3, myFunction(1, 2));
    }

    public function testError()
    {
        $this->expectException(MyException::class);
        myFunction(null, 2);
    }
}
```

---

*本规则适用于 PHP 项目的 AI Agent 开发。*

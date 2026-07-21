---
title: R Governance Rules
description: > 适用于: R 项目 (数据分析, 统计建模, 机器学习)
category: 治理层
tags: ['测试']
difficulty: 高级
reading_time: 10 分钟
updated: 2026-07-21
---

# R Governance Rules

> 适用于: R 项目 (数据分析, 统计建模, 机器学习)

---

## 1. 代码规范

### 格式化

```r
# 使用 styler 格式化
styler::style_file(".")

# 或使用 formatR
formatR::tidy_dir("R/")
```

### 命名规范

```r
# ✅ 正确 - 使用 snake_case
user_name <- "Alice"
get_user_data <- function() { }
max_retry_count <- 3

# ✅ 正确 - 使用 PascalCase (仅限类/构造函数)
setClass("User", representation(name = "character", age = "numeric"))

# ❌ 禁止
userName <- "Alice"      # 应使用 snake_case
GetUserData <- function() { }  # 函数应使用 snake_case
```

---

## 2. 错误处理

### 异常处理

```r
# ✅ 正确 - 使用 tryCatch
get_user <- function(id) {
  tryCatch({
    response <- httr::GET(paste0("/users/", id))
    if (httr::status_code(response) == 200) {
      return(jsonlite::fromJSON(httr::content(response, "text")))
    } else {
      stop("Server error: ", httr::status_code(response))
    }
  }, error = function(e) {
    message("Error: ", e$message)
    return(NULL)
  })
}

# ✅ 正确 - 自定义错误
custom_error <- function(message) {
  structure(
    class = c("custom_error", "error"),
    message = message
  )
}

# ❌ 禁止
get_user <- function(id) {
  response <- httr::GET(paste0("/users/", id))
  jsonlite::fromJSON(httr::content(response, "text"))  # 未处理错误
}
```

---

## 3. 函数式编程

### 向量化操作

```r
# ✅ 正确 - 使用向量化
result <- sqrt(1:100)
filtered <- df[df$age > 18, ]

# ✅ 正确 - 使用 apply 系列
means <- apply(data, 2, mean)
results <- lapply(data_list, function(x) x * 2)

# ❌ 禁止 - 使用 for 循环处理向量
result <- c()
for (i in 1:100) {
  result[i] <- sqrt(i)
}
```

### 管道操作

```r
# ✅ 正确 - 使用 |>
library(dplyr)

result <- data |>
  filter(age > 18) |>
  group_by(category) |>
  summarise(mean_value = mean(value))

# ✅ 正确 - 使用 %>%
result <- data %>%
  filter(age > 18) %>%
  group_by(category) %>%
  summarise(mean_value = mean(value))

# ❌ 禁止 - 嵌套函数
result <- summarise(group_by(filter(data, age > 18), category), mean_value = mean(value))
```

---

## 4. 数据操作

### Tidyverse

```r
# ✅ 正确 - 使用 dplyr
library(dplyr)

df <- data |>
  mutate(age_group = case_when(
    age < 18 ~ "minor",
    age < 65 ~ "adult",
    TRUE ~ "senior"
  )) |>
  group_by(age_group) |>
  summarise(
    count = n(),
    mean_age = mean(age)
  )

# ❌ 禁止 - 使用 base R 过多
df$age_group <- ifelse(df$age < 18, "minor", ifelse(df$age < 65, "adult", "senior"))
```

### 缺失值处理

```r
# ✅ 正确 - 显式处理 NA
df <- df |>
  filter(!is.na(value)) |>
  mutate(value = ifelse(is.na(value), mean(value, na.rm = TRUE), value))

# ✅ 正确 - 使用 tidyr
library(tidyr)
df <- df |>
  drop_na() |>
  fill(value, .direction = "down")
```

---

## 5. 可视化

### ggplot2

```r
# ✅ 正确 - 使用 ggplot2
library(ggplot2)

ggplot(data, aes(x = x, y = y, color = group)) +
  geom_point() +
  geom_smooth(method = "lm") +
  labs(
    title = "Relationship between X and Y",
    x = "X axis",
    y = "Y axis"
  ) +
  theme_minimal()

# ❌ 禁止 - 使用 base R 绑图
plot(data$x, data$y, col = data$group)
```

---

## 6. 测试

```r
# ✅ 正确 - 使用 testthat
library(testthat)

test_that("get_user returns user data", {
  user <- get_user(1)
  expect_type(user, "list")
  expect_true("name" %in% names(user))
  expect_equal(user$name, "Alice")
})

test_that("get_user handles errors", {
  expect_error(get_user(999), "not found")
})
```

---

## 7. 性能优化

### 并行计算

```r
# ✅ 正确 - 使用 parallel
library(parallel)

cl <- makeCluster(detectCores() - 1)
results <- parLapply(cl, data_list, function(x) {
  # 复杂计算
})
stopCluster(cl)

# ✅ 正确 - 使用 future
library(future)
plan(multisession)

results <- future.apply::future_lapply(data_list, function(x) {
  # 复杂计算
})
```

### 内存管理

```r
# ✅ 正确 - 及时释放内存
rm(large_object)
gc()

# ✅ 正确 - 使用 data.table 处理大数据
library(data.table)
dt <- as.data.table(large_df)
result <- dt[, .(mean_value = mean(value)), by = category]
```

---

## 8. 禁止行为

| 行为 | 原因 |
|------|------|
| 使用 `=` 赋值 | 使用 `<-` |
| 使用 `T`/`F` | 使用 `TRUE`/`FALSE` |
| 使用 `library()` 在函数中 | 在脚本顶部加载 |
| 忽略警告 | 处理或抑制警告 |
| 使用 `attach()` | 使用 `with()` 或显式引用 |
| 使用 `rm(list = ls())` | 不要清理全局环境 |

---

*最后更新: 2026-07-21*

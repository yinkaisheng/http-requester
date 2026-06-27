# Postman Collection 导入功能设计文档

## 概述

本 app 计划支持导入 **Postman Collection v2.0 / v2.1** JSON 格式的配置文件，
将 Postman 中保存的 API 请求集合转换为本 app 内部的 `HttpRequest` 对象，
方便用户从 Postman 迁移到本工具。

## 支持的 Postman Collection 格式

- **Collection v2.0**（`schema`: `https://schema.getpostman.com/json/collection/v2.0.0/collection.json`）
- **Collection v2.1**（`schema`: `https://schema.getpostman.com/json/collection/v2.1.0/collection.json`）

## 文件结构对照

### Postman Collection JSON 顶层结构

```json
{
  "info": {
    "name": "Collection Name",
    "description": "Collection Description",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Request Name",
      "request": { ... },
      "response": [ ... ]
    },
    {
      "name": "Folder Name",
      "item": [
        { "name": "Nested Request", "request": { ... } }
      ]
    }
  ]
}
```

### 字段映射规则

#### 1. 请求 URL

| Postman 字段 | 映射位置 | 说明 |
|---|---|---|
| `request.url.raw` | `HttpRequest.url` | 优先使用 `raw` 完整 URL |
| `request.url.protocol` + `host` + `port` + `path` + `query` | `HttpRequest.url` | 无 `raw` 时从组件拼接 |
| `request.url.query[].key` / `value` | 拼入 URL 查询字符串 | 仅 `disabled != true` 的参数 |
| `request.url.variable[].key` / `value` | 拼入 URL 查询字符串 | Postman URL 变量 |

#### 2. HTTP 方法

| Postman 字段 | 映射位置 |
|---|---|
| `request.method` | `HttpRequest.method`（默认 `GET`） |

#### 3. 请求头

| Postman 字段 | 映射位置 | 说明 |
|---|---|---|
| `request.header[].key` | `HeaderItem.key` | |
| `request.header[].value` | `HeaderItem.value` | |
| `request.header[].disabled` | `HeaderItem.enabled` | `true`→`enabled=false`，`false/缺失`→`enabled=true` |

#### 4. 请求体

根据 `request.body.mode` 的值分别处理：

##### mode = `raw`

| Postman 字段 | 映射位置 | 说明 |
|---|---|---|
| `request.body.raw` | `HttpRequest.body_text` | 原始文本 |
| `request.body.options.raw.language` | `BodyType` 推断 | `json`→`BodyType.JSON`；其他→通过 `detect_import_body_type()` 自动检测 |
| Content-Type 头 | `BodyType` 推断 | 含 `application/json`→`BodyType.JSON` |

##### mode = `urlencoded`

| Postman 字段 | 映射位置 |
|---|---|
| `request.body.urlencoded[].key` | `FormField.key` |
| `request.body.urlencoded[].value` | `FormField.value` |
| `request.body.urlencoded[].disabled` | 忽略此字段 |

映射为 `BodyType.FORM`，`form_fields` 列表。

##### mode = `formdata`

| Postman 字段 | 映射位置 | 说明 |
|---|---|---|
| `request.body.formdata[].key` | `FormField.key` | |
| `request.body.formdata[].value` | `FormField.value` | 文本字段的值 |
| `request.body.formdata[].type` | `FormField.is_file` | `"file"`→`is_file=true`；`"text"`→`is_file=false` |
| `request.body.formdata[].src` | `FormField.file_path` | 文件路径 |

映射为 `BodyType.FORM`，`form_fields` 列表。

##### mode = `file`

| Postman 字段 | 映射位置 |
|---|---|
| `request.body.src` | `HttpRequest.file_path` |

映射为 `BodyType.FILE`。

##### mode = `graphql`

| Postman 字段 | 映射位置 | 说明 |
|---|---|---|
| `request.body.query` | `body_text`（JSON 格式） | 拼装为 `{"query": "...", "variables": ...}` |
| `request.body.variables` | 同上 | |
| `request.body.raw` | `body_text` | 如有原始文本则直接使用 |

映射为 `BodyType.JSON`（若可解析）或 `BodyType.RAW`。

#### 5. 文件夹层级

Postman 的文件夹（包含 `item` 字段的节点）会被递归展开，
所有叶子节点的请求名会拼接文件夹路径作为显示名称：

```
父文件夹 / 子文件夹 / 请求名
```

该名称映射到 `HistoryRecord.name`。

## 配置文件的例子

以下是一个完整的 Postman Collection v2.1 示例文件，
覆盖了本 app 支持的大部分功能：

```json
{
  "info": {
    "name": "Example API",
    "description": "A sample Postman collection for testing import",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Get Users",
      "request": {
        "method": "GET",
        "header": [
          {
            "key": "Accept",
            "value": "application/json"
          },
          {
            "key": "Authorization",
            "value": "Bearer {{token}}",
            "disabled": false
          }
        ],
        "url": {
          "raw": "https://api.example.com/users?page=1&limit=20",
          "protocol": "https",
          "host": ["api", "example", "com"],
          "path": ["users"],
          "query": [
            { "key": "page", "value": "1" },
            { "key": "limit", "value": "20" }
          ]
        }
      }
    },
    {
      "name": "Create User",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/json"
          }
        ],
        "body": {
          "mode": "raw",
          "raw": "{\"name\":\"Alice\",\"email\":\"alice@example.com\"}",
          "options": {
            "raw": {
              "language": "json"
            }
          }
        },
        "url": {
          "raw": "https://api.example.com/users",
          "protocol": "https",
          "host": ["api", "example", "com"],
          "path": ["users"]
        }
      }
    },
    {
      "name": "Login",
      "request": {
        "method": "POST",
        "header": [
          {
            "key": "Content-Type",
            "value": "application/x-www-form-urlencoded"
          }
        ],
        "body": {
          "mode": "urlencoded",
          "urlencoded": [
            { "key": "username", "value": "admin", "disabled": false },
            { "key": "password", "value": "secret123" }
          ]
        },
        "url": {
          "raw": "https://api.example.com/auth/login"
        }
      }
    },
    {
      "name": "Folder with requests",
      "item": [
        {
          "name": "Upload File",
          "request": {
            "method": "POST",
            "body": {
              "mode": "formdata",
              "formdata": [
                {
                  "key": "file",
                  "type": "file",
                  "src": "/path/to/file.txt"
                },
                {
                  "key": "description",
                  "type": "text",
                  "value": "A sample file upload"
                }
              ]
            },
            "url": {
              "raw": "https://api.example.com/upload"
            }
          }
        },
        {
          "name": "Delete User",
          "request": {
            "method": "DELETE",
            "header": [
              {
                "key": "Authorization",
                "value": "Bearer token123"
              }
            ],
            "url": {
              "raw": "https://api.example.com/users/1",
              "protocol": "https",
              "host": ["api", "example", "com"],
              "path": ["users", "1"]
            }
          }
        }
      ]
    }
  ]
}
```

## 未支持的 Postman 功能

以下 Postman Collection 中的功能在首次实现中 **不会** 支持：

| 功能 | 原因 |
|---|---|
| `auth`（认证配置） | Postman 的认证助手（OAuth 2.0, API Key, Digest Auth 等）与本 app 的手动 Headers 方式不兼容，建议用户手动添加对应 Header |
| `event`（脚本） | Pre-request Script / Test Script 与本 app 架构不兼容 |
| `variable`（集合变量） | Postman 的变量模板引擎（`{{var}}`）与本 app 不兼容；用户需手动替换 |
| `protocolProfileBehavior` | Postman 专有行为配置 |
| 多个 `response` | Postman 保存的响应示例，只提取请求部分 |
| GraphQL 的完整 schema 支持 | 仅支持提取 GraphQL body 文本 |

## 实现计划

建议的模块位置和接口：

```
services/
  postman_import.py    # 核心解析逻辑
```

主要公开接口：

```python
def parse_postman_collection(file_path: str) -> List[Tuple[str, HttpRequest]]:
    """解析 Postman Collection JSON 文件，返回 (名称, HttpRequest) 列表。"""

def parse_postman_collection_from_text(text: str) -> List[Tuple[str, HttpRequest]]:
    """从 JSON 字符串解析 Postman Collection。"""
```

UI 入口位置：`main_window.py`中的工具栏 **Import** 下拉按钮 → **Postman Collection...**。

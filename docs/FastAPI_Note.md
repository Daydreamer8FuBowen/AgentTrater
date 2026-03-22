# FastAPI 详细笔记

## 1．FastAPI 是什么

FastAPI 是一个基于 Python 类型注解构建的现代 Web 框架，主要用于开发 API 服务。它建立在两个关键基础之上：

* Starlette：负责 Web 层能力，如路由、请求响应、中间件、ASGI 生命周期、WebSocket 等。
* Pydantic：负责数据校验、序列化、反序列化和类型驱动的数据建模。

因此，FastAPI 本质上不是“从零实现一切”的框架，而是一个将 **异步 Web 能力** 与 **类型驱动数据建模** 组合起来的高层 API 框架。

---

## 2．FastAPI 的核心设计思路

FastAPI 的设计思路可以概括为一句话：

**用 Python 类型注解统一描述接口输入、输出、校验规则、文档和依赖关系。**

这套思路非常重要，因为它决定了 FastAPI 和传统 Flask 式框架的根本区别。

### 2.1 类型注解不是“提示”，而是“接口契约”

在很多 Python 项目里，类型注解只是给 IDE 看；但在 FastAPI 中，类型注解会真正参与运行时行为，包括：

* 请求参数解析
* 请求体校验
* 响应模型约束
* OpenAPI 文档生成
* 依赖注入参数解析

例如：

```python
@app.get("/users/{user_id}")
def get_user(user_id: int, active: bool = True):
    ...
```

这里不是简单写了两个类型：

* `user_id: int` 表示路径参数必须可解析为整数
* `active: bool = True` 表示查询参数是布尔值，默认值为 True

FastAPI 会自动做：

* 路径与查询参数提取
* 类型转换
* 不合法值的错误响应
* 文档描述生成

这意味着，**函数签名本身就是接口定义**。

---

### 2.2 “声明式”优先，而非“手动解析”优先

传统框架常见写法是：

* 自己从 request 中取参数
* 自己判断参数是否存在
* 自己做类型转换
* 自己写错误返回
* 自己维护接口文档

而 FastAPI 倾向于声明式写法：

* 你声明参数长什么样
* 框架自动解析
* 框架自动校验
* 框架自动生成文档
* 框架自动组织错误格式

也就是说，FastAPI 把开发者从“样板代码”里解放出来，让开发者更多描述业务意图，而不是机械处理 HTTP 细节。

---

### 2.3 面向 API，而不是面向模板渲染页面

FastAPI 的定位首先是 API 框架，而不是传统 SSR 页面框架。

它更适合：

* 前后端分离接口
* 微服务
* Agent 服务
* 推理服务
* 数据接口服务
* 后台管理接口
* 异步任务触发接口
* WebSocket 实时服务

所以它强调的是：

* 高性能
* 数据结构清晰
* 文档自动生成
* 并发友好
* 工程化能力强

---

### 2.4 基于 ASGI，而不是 WSGI

FastAPI 基于 ASGI 协议，而不是 Flask 时代常见的 WSGI。

这带来两个关键差异：

#### （1）天然支持异步

可以直接使用 `async def` 编写异步接口，适合：

* 数据库异步访问
* 外部 API 调用
* WebSocket
* 长连接
* 高并发 IO 场景

#### （2）支持更丰富的协议场景

不仅能处理普通 HTTP 请求，还能处理：

* WebSocket
* 生命周期管理
* 异步中间件
* 流式响应

所以从架构角度看，FastAPI 更接近“现代服务框架”。

---

## 3．FastAPI 适合什么场景

FastAPI 适合以下类型的系统：

### 3.1 数据接口型系统

例如：

* 用户中心 API
* 商品管理 API
* 订单系统 API
* 管理后台接口

### 3.2 AI / Agent / 推理服务

例如：

* LLM 推理接口
* 向量检索 API
* 工具调用服务
* 多 Agent 编排入口
* 模型推理网关

### 3.3 异步 IO 明显的服务

例如：

* 调用多个外部服务聚合结果
* 文件上传下载
* 流式处理
* WebSocket 消息推送

### 3.4 需要强文档能力的项目

FastAPI 自动生成 OpenAPI 文档，非常适合：

* 团队协作开发
* 前后端联调
* 第三方集成接口
* 快速验收 API 定义

---

## 4．基础使用简述

基础使用只需要记住几个核心概念：

* `FastAPI()`：创建应用实例
* `@app.get/post/...`：定义路由
* 函数参数：定义请求参数
* Pydantic 模型：定义请求体和响应体
* `uvicorn`：运行服务

### 基础示例代码

```python
from fastapi import FastAPI
from pydantic import BaseModel

# 创建 FastAPI 应用实例
app = FastAPI(title="Demo API")


# 定义请求体模型
class UserCreateRequest(BaseModel):
    name: str
    age: int


# 基础 GET 接口
@app.get("/ping")
def ping():
    # 返回一个简单 JSON
    return {"message": "pong"}


# 路径参数 + 查询参数
@app.get("/users/{user_id}")
def get_user(user_id: int, active: bool = True):
    # user_id 来自路径
    # active 来自查询参数，例如 /users/1?active=false
    return {
        "user_id": user_id,
        "active": active,
    }


# POST 接口，请求体自动解析为 Pydantic 模型
@app.post("/users")
def create_user(request: UserCreateRequest):
    # request.name / request.age 已经过校验
    return {
        "message": "created",
        "user": request.model_dump(),
    }
```

运行方式：

```bash
uvicorn main:app --reload
```

访问自动文档：

* `/docs`
* `/redoc`

---

## 5．FastAPI 的请求处理机制

理解 FastAPI，必须理解它是如何把 HTTP 请求映射到 Python 函数的。

### 5.1 路由函数就是请求处理单元

例如：

```python
@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    ...
```

框架会根据函数签名判断：

* `item_id`：路径参数
* `q`：查询参数
* 返回值：自动转为 JSON 响应

FastAPI 实际上在做一件事：

**根据路由定义和函数签名，构建一个“参数解析与调用执行器”。**

---

### 5.2 参数来源的判定规则

FastAPI 会根据参数位置和类型大致推断来源：

#### （1）路径参数

名称出现在路由路径模板中：

```python
@app.get("/items/{item_id}")
def read_item(item_id: int):
    ...
```

#### （2）查询参数

普通标量参数，且不在路径中：

```python
@app.get("/items")
def read_items(page: int = 1, size: int = 10):
    ...
```

#### （3）请求体

通常是 Pydantic 模型：

```python
class Item(BaseModel):
    name: str
    price: float

@app.post("/items")
def create_item(item: Item):
    ...
```

#### （4）特殊声明参数

使用 `Query`、`Path`、`Body`、`Header`、`Cookie` 等显式声明来源与约束：

```python
from fastapi import Query, Header

@app.get("/search")
def search(keyword: str = Query(..., min_length=2), token: str = Header(...)):
    ...
```

---

## 6．Pydantic 在 FastAPI 中的作用

FastAPI 的强大很大程度来自 Pydantic。

### 6.1 Pydantic 负责什么

* 定义数据结构
* 校验输入数据
* 类型转换
* 默认值处理
* 序列化输出
* 嵌套模型表达

### 6.2 为什么它很重要

因为 API 的本质就是“数据交换”，而数据交换最核心的问题就是：

* 数据格式对不对
* 字段缺不缺
* 类型是否正确
* 默认值是什么
* 输出结构怎么约束

Pydantic 让这些问题变成“模型定义问题”，而不是散落在业务代码中的 if/else 校验问题。

### 6.3 示例

```python
from pydantic import BaseModel, Field

class Address(BaseModel):
    city: str
    zipcode: str

class User(BaseModel):
    name: str = Field(..., min_length=2, max_length=20)
    age: int = Field(..., ge=0, le=150)
    address: Address
```

这个模型的意义是：

* `name` 必填，长度 2 到 20
* `age` 必填，范围 0 到 150
* `address` 是嵌套对象

FastAPI 会自动用这个定义来校验请求体，并生成接口文档。

---

## 7．FastAPI 的依赖注入

依赖注入是 FastAPI 最重要的高级能力之一。

## 7.1 什么是依赖注入

简单说：

**把“路由函数运行前所需的前置对象、前置逻辑、公共上下文”交给框架统一管理和注入。**

不是在路由内部手动创建，而是在参数中声明“我需要它”，框架负责准备。

例如：

```python
@app.get("/me")
def read_me(current_user = Depends(get_current_user)):
    ...
```

这里的意思是：

* `read_me` 依赖 `get_current_user`
* 在执行 `read_me` 前，先执行 `get_current_user`
* 将其返回值注入到 `current_user`

---

### 7.2 为什么 FastAPI 要强调依赖注入

因为 Web 服务中有大量横切逻辑是重复出现的：

* 数据库会话获取
* 当前登录用户解析
* 权限检查
* 配置获取
* 日志上下文构建
* 租户信息提取
* 请求级追踪 ID
* 限流判断
* 参数预处理

如果都写在路由函数内部，会出现：

* 重复代码多
* 逻辑耦合严重
* 测试困难
* 可复用性差

依赖注入的目标是把这些横切逻辑模块化。

---

### 7.3 Depends 的基本机制

```python
from fastapi import Depends, FastAPI

app = FastAPI()

def get_token():
    return "demo-token"

@app.get("/info")
def get_info(token: str = Depends(get_token)):
    return {"token": token}
```

执行流程：

1. 请求进入 `/info`
2. FastAPI 发现 `token` 依赖于 `get_token`
3. 先调用 `get_token`
4. 将返回值注入到 `token`
5. 再执行 `get_info`

---

### 7.4 依赖可以层层嵌套

这是 FastAPI 非常强的一点。

```python
def get_settings():
    return {"env": "dev"}

def get_db(settings = Depends(get_settings)):
    return f"db-for-{settings['env']}"

@app.get("/items")
def read_items(db = Depends(get_db)):
    return {"db": db}
```

这里存在一条依赖链：

* 路由依赖 `get_db`
* `get_db` 又依赖 `get_settings`

FastAPI 会自动解析整棵依赖树。

这使得工程结构可以做到：

* 配置层
* 资源层
* 认证层
* 权限层
* 业务前置层

逐层组合。

---

### 7.5 依赖注入的典型场景

#### （1）数据库会话注入

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

然后：

```python
@app.get("/users")
def list_users(db = Depends(get_db)):
    ...
```

这样路由无需关心连接创建和释放。

#### （2）当前用户注入

```python
def get_current_user(token: str = Depends(get_token)):
    # 校验 token，解析用户
    return {"id": 1, "name": "admin"}
```

#### （3）权限检查

```python
def require_admin(user = Depends(get_current_user)):
    if user["name"] != "admin":
        raise HTTPException(status_code=403, detail="forbidden")
    return user
```

#### （4）公共查询条件构造

```python
from fastapi import Query

def pagination(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)):
    return {"page": page, "size": size}
```

---

### 7.6 yield 依赖：管理资源生命周期

这是 FastAPI 高级使用里非常关键的点。

普通依赖：

```python
def get_config():
    return {"env": "dev"}
```

带 `yield` 的依赖：

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

含义是：

* `yield` 前：进入依赖时执行，通常用于创建资源
* `yield` 返回给路由：路由使用该资源
* `finally`：请求处理结束后执行，通常用于清理资源

这非常适合：

* 数据库 session
* 临时文件句柄
* 网络连接
* trace 上下文
* 请求级资源对象

本质上，`yield` 依赖就是 **请求级资源管理机制**。

---

### 7.7 依赖注入的设计价值

FastAPI 的依赖注入设计，不只是为了“少写代码”，而是为了构建一套清晰的职责分层：

* 路由层：只负责协议入口与返回
* 依赖层：负责上下文、资源、认证、校验
* 服务层：负责业务逻辑
* 仓储层：负责数据访问

这样会让大型项目更可维护。

---

## 8．状态管理

FastAPI 中“状态管理”需要分层理解，不能笼统看。

常见状态有四类：

* 应用级状态
* 请求级状态
* 会话/认证状态
* 外部持久化状态

---

## 8.1 应用级状态

应用级状态指整个服务进程共享的数据或对象，例如：

* 配置对象
* 数据库连接池
* Redis 客户端
* 模型实例
* 调度器
* 全局缓存
* 线程池 / 任务池

这类状态通常放在应用启动阶段初始化，然后挂到应用对象上。

### 使用 `app.state`

```python
from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
def on_startup():
    app.state.service_name = "demo-service"
```

使用时：

```python
from fastapi import Request

@app.get("/name")
def get_name(request: Request):
    return {"service_name": request.app.state.service_name}
```

### 设计理解

`app.state` 适合保存“应用运行期间共享”的对象，但要注意：

* 不要在里面存放请求私有数据
* 不要存放线程不安全且会被并发修改的临时对象
* 更适合存连接池、配置、客户端、服务单例等

---

## 8.2 请求级状态

请求级状态指只在一次请求处理过程中有效的数据，例如：

* trace_id
* 当前用户
* 请求开始时间
* 权限判定结果
* 某个中间计算上下文

FastAPI/Starlette 提供 `request.state`。

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    request.state.trace_id = "trace-123"
    response = await call_next(request)
    return response

@app.get("/trace")
def get_trace(request: Request):
    return {"trace_id": request.state.trace_id}
```

### 设计理解

`request.state` 的作用是：

**在同一次请求的不同处理阶段之间共享上下文。**

它常用于：

* 中间件写入，路由读取
* 依赖写入，服务读取
* 链路追踪数据透传

---

## 8.3 认证/会话状态

FastAPI 自身不强推传统服务端 Session 方案，它更偏向 API 场景，因此常见做法是：

* JWT
* OAuth2
* Bearer Token
* API Key

也就是说，FastAPI 并不以“服务端 session 状态”作为核心设计，而是更偏向 **无状态认证**。

### 为什么偏向无状态

因为 API 服务更适合：

* 水平扩容
* 网关转发
* 微服务部署
* 移动端 / 前端分离
* 第三方调用

如果依赖服务端 Session，会让状态绑定到某些节点或共享存储，复杂度更高。

---

## 8.4 外部持久化状态

真正长期业务状态不应放在 FastAPI 内存中，而应放在外部系统：

* MySQL / PostgreSQL
* MongoDB
* Redis
* 对象存储
* 消息队列
* 向量数据库

FastAPI 只是访问这些状态的接口层，不应本身承担持久化职责。

---

## 8.5 状态管理的设计原则

### 原则一：分清共享状态和请求状态

* 共享状态放 `app.state`
* 请求状态放 `request.state`

### 原则二：不要把业务数据缓存成不可控的全局变量

因为多进程、多 worker 部署时，全局变量并不共享，而且容易产生一致性问题。

### 原则三：持久状态外置

长期业务状态一定外置，不依赖应用内存。

### 原则四：请求上下文尽量显式传递或通过依赖注入组织

不要过度滥用隐式全局上下文。

---

## 9．生命周期管理

FastAPI 服务不是只有“收到请求 -> 返回响应”这么简单，它还有应用生命周期。

例如，一个服务在启动时可能需要：

* 读取配置
* 初始化日志
* 连接数据库
* 初始化 Redis
* 加载模型
* 启动调度器

在关闭时可能需要：

* 关闭连接池
* 停止调度器
* 刷新缓冲区
* 释放模型资源

这就需要生命周期管理。

---

## 9.1 传统方式：startup / shutdown

```python
@app.on_event("startup")
async def startup():
    ...

@app.on_event("shutdown")
async def shutdown():
    ...
```

这种写法简单直观，但在新式工程里，越来越推荐使用 `lifespan`。

---

## 9.2 推荐方式：lifespan

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动阶段
    app.state.ready = True
    yield
    # 关闭阶段
    app.state.ready = False

app = FastAPI(lifespan=lifespan)
```

### 执行逻辑

* `yield` 之前：应用启动时执行
* `yield` 之后：应用关闭时执行

### 为什么推荐 lifespan

因为它把“启动逻辑”和“关闭逻辑”写在一个上下文里，结构更完整，适合复杂资源初始化。

---

## 9.3 生命周期的设计思路

生命周期的本质不是“写几个钩子函数”，而是：

**为应用级资源建立统一初始化入口与统一清理出口。**

它和请求级 `yield` 依赖类似，只是层级不同：

* 生命周期：管理应用级资源
* yield 依赖：管理请求级资源

这两个机制组合起来，就形成了完整的资源管理体系。

---

## 10．中间件

中间件位于请求进入路由之前、响应返回客户端之前的公共处理链上。

常见用途：

* 日志记录
* 统一异常包装
* CORS
* 请求耗时统计
* 认证前置拦截
* 链路追踪
* 请求 ID 注入
* 限流
* 压缩

### 示例

```python
from fastapi import FastAPI, Request

app = FastAPI()

@app.middleware("http")
async def log_middleware(request: Request, call_next):
    # 前置逻辑
    print("request start:", request.url.path)

    response = await call_next(request)

    # 后置逻辑
    print("request end:", request.url.path)
    return response
```

### 设计理解

中间件适合处理“所有请求都要走”的横切逻辑。

但是中间件不要承担太重的业务逻辑，否则会：

* 可读性差
* 排查困难
* 耦合严重

一般原则是：

* 通用协议逻辑放中间件
* 业务相关前置逻辑放依赖
* 核心业务放服务层

---

## 11．异常处理机制

FastAPI 提供：

* 主动抛出 HTTP 异常
* 注册全局异常处理器

### 11.1 主动抛出 HTTPException

```python
from fastapi import HTTPException

@app.get("/items/{item_id}")
def get_item(item_id: int):
    if item_id <= 0:
        raise HTTPException(status_code=400, detail="invalid item id")
    return {"item_id": item_id}
```

### 11.2 全局异常处理器

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

class BizError(Exception):
    def __init__(self, message: str):
        self.message = message

@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(
        status_code=400,
        content={"code": "BIZ_ERROR", "message": exc.message},
    )
```

### 设计理解

推荐分层处理：

* 协议层错误：`HTTPException`
* 业务层错误：自定义异常
* 全局统一转换：异常处理器

这样便于统一响应结构。

---

## 12．响应模型

FastAPI 不仅可以校验输入，也可以约束输出。

```python
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: int
    name: str

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int):
    return {"id": user_id, "name": "Tom", "extra": "ignored"}
```

作用：

* 输出结构更稳定
* 自动过滤多余字段
* 文档更准确
* 防止敏感字段意外泄露

### 设计理解

请求模型解决“你传进来的数据是否合法”，响应模型解决“我返回出去的数据是否规范”。

大项目中，响应模型非常有价值，不能忽视。

---

## 13．APIRouter 与项目模块化

当接口变多时，不可能全部写在一个文件里。FastAPI 用 `APIRouter` 做模块拆分。

### 示例

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/{user_id}")
def get_user(user_id: int):
    return {"user_id": user_id}
```

主应用中注册：

```python
from fastapi import FastAPI
from routers.user import router as user_router

app = FastAPI()
app.include_router(user_router)
```

### 设计思路

`APIRouter` 的作用不是“单纯拆文件”，而是：

* 按领域模块划分接口
* 统一 prefix
* 统一 tags
* 统一依赖
* 统一权限策略

例如一个 router 可以整体挂载某个认证依赖。

---

## 14．同步与异步

FastAPI 支持 `def` 和 `async def`。

### 14.1 什么时候用 `async def`

适用于明显 IO 密集场景：

* 异步数据库访问
* 异步 HTTP 调用
* 文件异步处理
* WebSocket
* 高并发等待型任务

### 14.2 什么时候用 `def`

适用于：

* 纯计算逻辑
* 使用的是同步库
* 没有异步调用链
* 简单接口

### 14.3 一个重要原则

**异步不是“更高级”，而是适合 IO 等待场景。**

如果你内部调用的都是同步阻塞库，那么仅把函数写成 `async def` 并不会自动变快，反而可能误导架构设计。

### 14.4 工程上的判断标准

看调用链是否异步一致：

* 异步框架 + 异步数据库 + 异步 HTTP 客户端，适合全链路 async
* 如果核心库是同步的，就不要强行假异步

---

## 15．后台任务

FastAPI 提供 `BackgroundTasks`，用于响应返回后执行一些轻量后置任务。

```python
from fastapi import BackgroundTasks, FastAPI

app = FastAPI()

def write_log(message: str):
    with open("app.log", "a", encoding="utf-8") as f:
        f.write(message + "\n")

@app.post("/notify")
def notify(background_tasks: BackgroundTasks):
    background_tasks.add_task(write_log, "notify called")
    return {"message": "accepted"}
```

### 设计理解

它适合轻量后置动作：

* 写日志
* 发简单通知
* 清理临时文件
* 非关键后处理

但不适合：

* 长时间任务
* 重计算任务
* 高可靠任务编排

这类任务应交给 Celery、RQ、消息队列、调度系统等外部机制。

---

## 16．WebSocket

FastAPI 也支持 WebSocket，适合实时交互场景。

```python
from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        text = await websocket.receive_text()
        await websocket.send_text(f"you said: {text}")
```

### 设计理解

这使 FastAPI 不只是 REST API 框架，也可以做：

* 实时消息
* 在线推送
* 流式输出
* 终端交互
* 实时监控面板

---

## 17．FastAPI 的工程化组织方式

在中大型项目中，建议按职责拆层，而不是所有逻辑写在路由里。

一个常见结构是：

```text
app/
├── main.py
├── api/
│   ├── routers/
│   │   ├── users.py
│   │   └── orders.py
├── schemas/
│   ├── user.py
│   └── order.py
├── services/
│   ├── user_service.py
│   └── order_service.py
├── repositories/
│   ├── user_repo.py
│   └── order_repo.py
├── dependencies/
│   ├── auth.py
│   └── db.py
├── core/
│   ├── config.py
│   ├── logging.py
│   └── security.py
```

### 各层职责

#### `api/routers`

* 处理 HTTP 层
* 接收参数
* 调用服务
* 返回响应

#### `schemas`

* Pydantic 模型
* 请求响应结构定义

#### `services`

* 业务逻辑层
* 编排领域行为

#### `repositories`

* 数据访问层
* 与数据库/缓存交互

#### `dependencies`

* 公共依赖，如鉴权、DB 会话、分页器等

#### `core`

* 配置、日志、安全、基础设施

### 设计原则

路由层尽量薄，业务层尽量清晰，依赖层专注上下文与资源注入。

---

## 18．FastAPI 的优势

### 18.1 开发效率高

因为：

* 自动校验
* 自动文档
* 类型驱动
* 样板代码少

### 18.2 接口定义清晰

函数签名和模型定义就能直接看出接口结构。

### 18.3 对现代 Python 生态友好

适配：

* async/await
* Pydantic
* Starlette
* OpenAPI

### 18.4 很适合 AI 服务

因为 AI 服务常常具有：

* JSON 输入输出
* 推理参数校验
* 异步调用
* 流式输出
* 文档要求高

---

## 19．FastAPI 的局限与注意点

### 19.1 它不是全能框架

FastAPI 非常适合 API，但不等于它天然覆盖所有后端问题，例如：

* ORM 选择仍要自己定
* 权限体系要自己设计
* 任务调度要自己接
* 分布式事务要自己做
* 服务治理要靠外部系统

### 19.2 类型注解滥用会让代码变复杂

虽然类型驱动是优势，但如果：

* 模型层级过深
* 泛型使用过重
* 依赖链过长
* 参数声明过于复杂

会导致阅读成本上升。

### 19.3 不要把依赖注入当成“魔法”

依赖注入应服务于解耦，不应过度嵌套到难以追踪。

### 19.4 不要误以为 async 一定更快

真正性能取决于：

* 调用链是否异步
* 外部资源是否阻塞
* worker 配置
* 数据库与缓存设计
* 系统整体瓶颈

---

## 20．理解 FastAPI 的一个整体视角

从架构角度看，FastAPI 可以理解为四层拼装：

### 第一层：协议层

由 Starlette/ASGI 提供：

* HTTP
* WebSocket
* 中间件
* 生命周期
* 请求响应对象

### 第二层：参数解析层

FastAPI 根据函数签名和声明式参数规则：

* 提取路径参数
* 提取查询参数
* 提取请求头、Cookie、Body
* 调用依赖

### 第三层：数据建模层

由 Pydantic 提供：

* 校验
* 转换
* 序列化
* 文档 schema 生成

### 第四层：业务层

由开发者自己实现：

* 服务逻辑
* 数据访问
* 权限体系
* 状态管理
* 资源协调

所以 FastAPI 的强项不在于“内置所有业务能力”，而在于：

**它把 Web 接口层做得极其清晰、强类型、工程友好。**

---

## 21．FastAPI 中依赖注入、状态管理、生命周期三者的关系

这三者很容易混，但实际上层级不同。

### 21.1 生命周期

解决的是：

**应用启动和关闭时，如何初始化与清理应用级资源。**

例如：

* 建立连接池
* 启动调度器
* 加载模型

### 21.2 状态管理

解决的是：

**资源和上下文应该存在哪里、以什么粒度存在。**

例如：

* 应用级放 `app.state`
* 请求级放 `request.state`

### 21.3 依赖注入

解决的是：

**路由或其他依赖在执行时，如何获得所需资源和上下文。**

例如：

* 从 `app.state` 中取数据库工厂
* 构造请求级 session
* 获取当前用户
* 进行权限校验

### 21.4 一个完整例子中的协作关系

例如数据库：

1. 生命周期启动时初始化数据库引擎，存入 `app.state`
2. 请求到来时，依赖函数从 `app.state` 中读取引擎并创建 session
3. 路由通过 `Depends(get_db)` 获得 session
4. 请求结束后，`yield` 依赖关闭 session

这说明三者并不是竞争关系，而是配套关系。

---

## 22．推荐的理解方式

学习 FastAPI，不要只盯着“怎么写接口”，而要抓住下面这几个抽象层：

### 22.1 函数签名即接口声明

参数、类型、默认值，都有运行时语义。

### 22.2 模型即数据契约

Pydantic 模型是请求与响应的正式结构定义。

### 22.3 依赖即上下文供应机制

不是简单工具函数，而是请求处理链中的前置依赖系统。

### 22.4 lifespan 与 yield 是两级资源管理

* lifespan：应用级
* yield dependency：请求级

### 22.5 state 是上下文承载容器

* `app.state`：全局共享
* `request.state`：单次请求共享

---

## 23．一个较完整的示意示例

下面这个例子把生命周期、状态、依赖注入放在一起展示。

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from pydantic import BaseModel


# =========================
# 模拟数据库客户端
# =========================
class FakeDBClient:
    def __init__(self):
        self.connected = True

    def close(self):
        self.connected = False

    def get_user(self, user_id: int):
        return {"id": user_id, "name": "Alice"}


# =========================
# 生命周期：应用启动/关闭
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化应用级资源
    app.state.db_client = FakeDBClient()
    app.state.app_name = "FastAPI Notes Demo"
    yield
    # 关闭时清理应用级资源
    app.state.db_client.close()


app = FastAPI(lifespan=lifespan)


# =========================
# 响应模型
# =========================
class UserResponse(BaseModel):
    id: int
    name: str


# =========================
# 请求级状态：中间件写入 trace_id
# =========================
@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    request.state.trace_id = "trace-demo-001"
    response = await call_next(request)
    return response


# =========================
# 依赖：从应用状态中获取数据库客户端
# =========================
def get_db_client(request: Request) -> FakeDBClient:
    return request.app.state.db_client


# =========================
# 依赖：获取当前请求的 trace_id
# =========================
def get_trace_id(request: Request) -> str:
    return request.state.trace_id


# =========================
# 路由：通过 Depends 注入资源和上下文
# =========================
@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db_client: FakeDBClient = Depends(get_db_client),
    trace_id: str = Depends(get_trace_id),
):
    user = db_client.get_user(user_id)
    print("current trace_id:", trace_id)
    return user
```

这个例子体现了完整思路：

* `lifespan`：管理应用级资源初始化与清理
* `app.state`：保存应用共享资源
* `request.state`：保存请求级上下文
* `Depends`：把资源和上下文注入路由
* `response_model`：约束输出结构

这其实就是 FastAPI 的核心工程模式。

---

## 24．总结

FastAPI 的核心不是“写接口更快”这么简单，而是它建立了一套以 **类型注解 + 声明式建模 + 依赖注入 + 分层资源管理** 为中心的 API 开发范式。

可以把它总结成下面四句话：

### 24.1 接口定义靠函数签名

函数参数不只是参数，而是请求协议的一部分。

### 24.2 数据结构靠 Pydantic 模型

模型不是普通类，而是请求与响应的数据契约。

### 24.3 公共上下文靠依赖注入

依赖注入不是辅助功能，而是 FastAPI 组织复杂系统的重要核心。

### 24.4 资源生命周期靠 lifespan 与 yield

FastAPI 真正高级的地方，在于它把应用级资源和请求级资源都纳入了统一管理思路。

所以，学习 FastAPI 最重要的不是背 API，而是理解它背后的设计哲学：

**用声明式方式定义接口，用类型系统驱动校验与文档，用依赖系统组织上下文，用生命周期管理资源。**

这就是 FastAPI 最核心的设计思路。

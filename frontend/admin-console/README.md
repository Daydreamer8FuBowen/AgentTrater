# AgentTrader Admin Console

一个面向 `agent_trader_schema.sql` 表结构的 Vue 管理控制台。

## 功能

- 查询白名单表（分页、关键字、JSON 过滤）
- 读取单行详情
- 修改已有记录（禁止新增与删除）
- 后端不可用时，自动切换为静态演示模式

## 运行

```bash
cd frontend/admin-console
npm install
npm run dev
```

默认通过 Vite 代理访问 `http://127.0.0.1:8000` 的 `/api`。

# 方案市场 — 设计方案

## 概述

用户在方案市场浏览、购买、安装官方或第三方发布的完整车间方案（`.nexus` 包）。每个方案独立定价（按月/按年），支持 VIP 包年全畅装。

与「我的模板」的关系：
- **模板** = 自己车间造的零件（workflow/agent/role），免费，存本地库
- **方案** = 从市场购买的完整车间包（`.nexus`），付费订阅，一键安装

## 命名规范

| 概念 | 中文名 | 说明 |
|------|--------|------|
| 市场 | 方案市场 | 浏览和购买入口 |
| 单个商品 | 方案 | 一个 .nexus 车间包 |
| 订阅 | 按月 / 按年 / VIP 包年 | 三种购买档位 |
| 我的资产 | 已购方案 | 用户已购买的方案列表 |

## 数据模型

### MarketplacePackage（云端存储）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 唯一编号 |
| name | str | 方案名称 |
| description | str | 简介（列表页展示，≤ 200 字） |
| long_description | str | 详细介绍（详情页，含使用方法） |
| category | str | 复用 PACKAGE_CATEGORIES |
| tags | list[str] | 标签 |
| author | str | 发布者 |
| version | str | 版本号 |
| icon_url | str | 缩略图 URL |
| screenshots | list[str] | 预览截图 URL |
| plan_monthly_price | int | 月付价格（分，0 = 不可月付） |
| plan_yearly_price | int | 年付价格（分，0 = 不可年付） |
| package_url | str | .nexus.zip 下载地址 |
| package_size | int | 字节数 |
| download_count | int | 下载次数 |
| created_at | str | 上架日期 |
| updated_at | str | 更新日期 |

### Subscription（云端存储）

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | str | 用户 ID |
| package_id | str | 方案 ID（VIP 则为 "vip"） |
| plan_type | enum | monthly / yearly / vip |
| expires_at | str | 到期时间 |
| created_at | str | 购买时间 |

## 定价模型

| 档位 | 说明 |
|------|------|
| 月付 | 单方案，按月订阅，到期自动锁定 |
| 年付 | 单方案，按年订阅（比月付打折） |
| VIP 包年 | 全方案畅装，不限数量，按年付费 |

## 架构

```
┌────────────────────── 云服务器 ──────────────────────┐
│  marketplace/                                        │
│    api.py          FastAPI 后端                       │
│    models.py       Pydantic 模型                      │
│    store.py        SQLite + OSS 存储                   │
│    auth.py         JWT 认证                           │
│    pay.py          支付回调（支付宝/微信个人收单）        │
│    packages/       方案 .nexus.zip 文件                │
│    marketplace.db  SQLite 数据库                       │
└──────────────────────────────────────────────────────┘
         │                    │
         │  HTTPS             │  HTTPS
         ▼                    ▼
┌───────────────┐    ┌───────────────────┐
│  本地工厂      │    │  官方管理后台      │
│  (本地代理)    │    │  (发布/管理方案)   │
└───────────────┘    └───────────────────┘
```

### 本地代理层

用户工厂不直接访问云端 API，而是通过本地 Gateway 代理：

| 本地端点 | 转发目标 | 说明 |
|---------|---------|------|
| `GET /api/market/catalog` | `{CLOUD}/api/catalog` | 方案目录 |
| `GET /api/market/packages/{id}` | `{CLOUD}/api/packages/{id}` | 方案详情 |
| `GET /api/market/packages/{id}/download` | `{CLOUD}/api/packages/{id}/download` | 下载 + 安装 |
| `GET /api/market/my` | `{CLOUD}/api/my` | 已购方案 |
| `POST /api/market/auth/login` | `{CLOUD}/api/auth/login` | 登录 |
| `POST /api/market/auth/register` | `{CLOUD}/api/auth/register` | 注册 |

本地代理层同时做：请求签名验证、下载缓存、安装流程编排。

## 用户交互流程

```
方案市场页面
  ├── 浏览目录（卡片列表：图标、名称、简介、价格）
  ├── 点击进入详情（完整介绍、截图、价格 / 购买按钮）
  │     ├── 未登录 → 弹出登录/注册
  │     ├── 已购 → 显示「安装」（复用已下载缓存或重新下载）
  │     └── 未购 → 显示「购买」→ 选择档位 → 支付
  └── 已购方案 Tab（我的资产）
```

安装流程：
1. 用户点击安装
2. 本地代理下载 `.nexus.zip` 到本地缓存
3. 校验 zip 完整性
4. 调用 `WorkshopManager.import_package()` 安装
5. 提示安装完成

## 新增文件（本地工厂）

| 文件 | 职责 |
|------|------|
| `gateway/routes/market.py` | 本地代理 API |
| `webui/src/components/Marketplace.tsx` | 方案市场页面 |
| `webui/src/lib/types.ts`（追加） | MarketPackage、Subscription 类型 |
| `webui/src/lib/api.ts`（追加） | 市场 API 调用 |
| `webui/src/App.tsx`（追加） | /market 路由 |
| `gateway/server.py`（追加） | 注册 market router |

## 新增文件（云端服务器）

| 文件 | 职责 |
|------|------|
| `marketplace/api.py` | FastAPI 应用 |
| `marketplace/models.py` | Pydantic 模型 |
| `marketplace/store.py` | SQLite 数据存储 |
| `marketplace/auth.py` | JWT 登录/注册 |
| `marketplace/admin.py` | 管理后台（发布/下架方案） |
| `marketplace/packages/` | 方案包存储目录 |

## 复用已有代码

| 依赖 | 用途 |
|------|------|
| `factory/workflow/package.py` | 验证 .nexus 包 |
| `factory/workshop/manager.py` | import_package 安装 |
| `factory/library/store.py` | LibraryStore 模式参考 |
| PACKAGE_CATEGORIES | 方案分类 |

## 不做

- 支付集成在第一版不做（留接口，手动激活订阅）
- 方案评分/评论（后续迭代）
- 方案更新推送通知
- 第三方发布者入驻
- 多语言界面

## 测试

- 云端：`marketplace/test_api.py` — 目录/详情/购买/下载
- 本地：`gateway/test_server.py` — 代理转发
- 前端：Playwright E2E — 浏览/查看详情

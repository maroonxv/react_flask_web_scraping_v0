# CrawlFlow - 智能网络爬虫系统

[![React](https://img.shields.io/badge/Frontend-React-61DAFB?logo=react)](https://reactjs.org/)
[![Flask](https://img.shields.io/badge/Backend-Flask-000000?logo=flask)](https://flask.palletsprojects.com/)



---

## 📖 项目简介

CrawlFlow 爬虫平台支持多种遍历策略（BFS/DFS/大站优先），内置 Robots 协议解析、智能去重和 PDF 识别功能，并通过 WebSocket 实现毫秒级的日志与状态同步。

### ✨ 核心特性

- **多策略调度引擎**：支持广度优先 (BFS)、深度优先 (DFS) 及创新的 **大站优先 (Big Site First)** 调度算法。
- **实时可视化监控**：基于 WebSocket 的实时日志流和任务状态仪表盘，让爬虫运行过程透明可见。
- **智能化解析**：自动提取标题、作者、摘要、关键词及 PDF 文档链接，支持 Robots.txt 协议合规性检查。
- **高鲁棒性设计**：内置网络异常重试、解析容错机制和速率限制，适应不稳定的网络环境。
- **现代化 UI/UX**：采用 Midnight Ocean 暗色系玻璃拟态设计，提供极佳的交互体验。

---

## 🏗️ 系统架构

本项目严格遵循 **领域驱动设计 (DDD)** 原则，后端代码组织清晰，高内聚低耦合。

### 后端架构 (Python Flask)

| 层级 | 职责描述 | 包含组件 |
| :--- | :--- | :--- |
| **Interfaces (Views)** | 适配层，处理 HTTP/WebSocket 请求 | `views/crawler_view.py` |
| **Application (Services)** | 应用服务层，编排业务流程 | `services/crawler_service.py` |
| **Domain** | 核心业务逻辑，纯净的业务规则 | `entity`, `value_objects`, `domain_event`, `domain_service` |
| **Infrastructure** | 基础设施层，技术实现细节 | `http_client`, `html_parser`, `database_repository` |

#### 关键技术实现细节

**1. 日志记录与实时监控**

*   **业务状态流转**：
    业务层面的状态变化（如“任务开始”、“爬取到一个页面”、“任务完成”）被建模为**领域事件 (Domain Events)**。这些事件发布到进程内的事件总线后，由订阅者 `WebSocketEventHandler` 捕获，并通过 WebSocket 实时推送到前端界面。这种设计使得前端无需轮询即可实时展示爬取进度和结果。

*   **技术日志 (Logging + WebSocket)**：
    基础设施层产生的异常（如“DNS 解析失败”、“连接超时”）和性能指标，通过 Python 标准库 `logging` 记录。为了在前端显示，实现了一个自定义的 `WebSocketLoggingHandler`，它拦截 **ERROR** 级别的日志记录，将其格式化后推送到前端的日志控制台，方便用户监控系统健康状况。

**2. 数据持久化策略**

数据持久化层采用了 **Repository 模式** 结合 **DAO** 的设计：

1.  **ORM 映射**：使用 **SQLAlchemy** 将领域实体 `CrawlTask` 和值对象 `CrawlResult` 映射为关系型数据库表。
2.  **CrawlRepository**：作为领域层与数据层的适配器，负责实现领域层的领域模型与数据库中的持久化模型进行相互转换，向应用层提供纯净的面向对象接口，屏蔽底层数据库细节。
3.  **事务管理 (Unit of Work)**：在保存数据时，采用 Unit of Work 思想，确保“保存爬取结果”和“更新任务状态（如已访问 URL 集合）”在同一个数据库事务中完成，保证了数据的一致性。如果中途发生异常，事务会自动回滚，避免数据损坏。

### 前端架构 (React.js + Vite)

采用组件化开发，通过 `Socket.io` 与后端保持实时双向通信，状态管理清晰，界面响应迅速。

---

## 🧪 测试方案与用例

为了验证系统的各项能力，我们设计了以下五组标准测试用例，覆盖了从基础功能到高级策略的全方位测试。您可以直接在“创建新任务”界面使用这些配置。

### 1. 电商全量扫描 (BFS 基准测试)
**测试目的**：测试爬虫在标准电商网站上的广度优先遍历能力，确保能逐层获取商品列表。
- **任务名称**：`Books_BFS_Test`
- **起始 URL**：`http://books.toscrape.com/`
- **允许的域名**：`books.toscrape.com`
- **策略**：`BFS` (广度优先)
- **最大深度**：3
- **最大页数**：50

### 2. 话题深度挖掘 (DFS 深度测试)
**测试目的**：测试深度优先策略，模拟顺着某个标签或分类一路向下挖掘数据的场景。
- **任务名称**：`Quotes_DFS_Deep`
- **起始 URL**：`http://quotes.toscrape.com/`
- **允许的域名**：`quotes.toscrape.com`
- **策略**：`DFS` (深度优先)
- **最大深度**：5
- **最大页数**：50

### 3. 多站点优先级调度 (大站优先策略 - 核心功能)
**测试目的**：验证在多域名混合环境下，爬虫是否能严格遵守“大站优先”规则，无视链接发现顺序，优先处理指定域名的队列。
- **任务名称**：`Priority_Quotes_First`
- **起始 URL**：`http://toscrape.com/`
- **允许的域名**：`toscrape.com, books.toscrape.com, quotes.toscrape.com`
- **策略**：`BIG_SITE_FIRST` (大站优先)
- **大站域名设置**：`quotes.toscrape.com`
- **预期效果**：尽管入口页同时存在书籍和名言的链接，爬虫应优先抓取 `quotes` 相关的页面（在结果列表中标有 ⭐），处理完或暂无 `quotes` 链接后才会去处理 `books`。

### 4. 真实环境模拟 (复杂 DOM 解析)
**测试目的**：测试对包含图片、分页和较复杂 DOM 结构的真实 WordPress 站点的解析能力。
- **任务名称**：`Pokemon_Shop_Real`
- **起始 URL**：`https://scrapeme.live/shop/`
- **允许的域名**：`scrapeme.live`
- **策略**：`BFS`
- **最大深度**：3
- **最大页数**：30

### 5. 爬虫陷阱与鲁棒性测试
**测试目的**：验证系统的错误处理、超时机制和死链处理能力。
- **任务名称**：`Crawler_Torture_Test`
- **起始 URL**：`https://crawler-test.com/`
- **允许的域名**：`crawler-test.com`
- **策略**：`DFS`
- **最大深度**：2 (该站点陷阱多，建议浅尝辄止)
- **最大页数**：20

---

## 🛠️ 快速开始

### 后端启动
```bash
cd backend
# 激活虚拟环境 (可选)
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
# 运行服务
python run.py
```

### 前端启动
```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173` 即可开始使用。

---

## 📊 测试覆盖
后端拥有完善的单元测试和集成测试体系，覆盖核心组件：
- **Infrastructure 层测试**：覆盖 HTTP 客户端、HTML 解析器、Robots 协议解析器及 URL 队列管理。
- **集成测试**：模拟真实爬取流程，验证各个组件协同工作的正确性。

---


# 系统演进日志 v2.0：混合渲染与动态评分策略

**日期**: 2026-01-02
**版本**: v2.0
**变更摘要**: 本次更新完成了从“静态爬虫”向“智能爬虫”的架构演进，引入了基于 Playwright 的混合解析模式和基于反馈的动态域名评分机制。

---

## 1. 核心架构变更 (Architectural Changes)

### 1.1 混合解析模式 (Hybrid Parsing Strategy)
为了解决 SPA (Single Page Application) 无法抓取的问题，同时保持爬虫性能，我们引入了“按需渲染”机制。

*   **新增组件**:
    *   `PlaywrightClient` (`infrastructure/playwright_client.py`): 封装无头浏览器操作。
    *   `HybridHttpClient` (`infrastructure/hybrid_http_client.py`): 组合模式，同时持有 `HttpClientImpl` (Static) 和 `PlaywrightClient` (Dynamic)。
*   **交互流程**:
    1.  默认使用 `requests` 发起静态请求。
    2.  应用层 (`CrawlerService`) 进行**启发式检测**：
        *   Body 长度 < 500 字符。
        *   存在 SPA 挂载点 (`<div id="app">`, `root`, `__next`).
    3.  若命中启发式规则，`CrawlerService` 再次调用 `http_client.get(..., render_js=True)` 触发浏览器渲染。

### 1.2 动态大站优先策略 (Dynamic Domain Scoring)
为了实现更智能的优先级调度，我们摒弃了纯静态的“大站”配置，转为“静态配置 + 动态反馈”的混合模式。

*   **新增组件**:
    *   `DomainScoreManager` (`domain/domain_service/domain_score_manager.py`): 领域服务，维护域名信誉分。
*   **评分逻辑**:
    *   **初始分**: 1.0 (白名单域名固定 10.0，黑名单 0.0)。
    *   **反馈环 (Feedback Loop)**:
        *   `RESOURCE_FOUND` (发现PDF/文档): +0.2
        *   `HIGH_QUALITY_CONTENT` (摘要>200字): +0.05
        *   `FAST_RESPONSE` (<500ms): +0.02
        *   `ERROR_4XX_5XX`: -0.5
    *   **优先级计算**:
    $$ Priority = (BasePriority + ResourceBonus) \times DomainScore \times 10 $$

---

## 2. 详细文件变更清单 (File Changes)

### Infrastructure Layer (基础设施层)
| 文件路径 | 变更类型 | 说明 |
| :--- | :--- | :--- |
| `src/crawl/infrastructure/playwright_client.py` | **New** | 实现 Playwright 浏览器启动、上下文管理与页面渲染。 |
| `src/crawl/infrastructure/hybrid_http_client.py` | **New** | 实现 `IHttpClient` 接口，根据 `render_js` 参数分发请求。 |
| `src/crawl/infrastructure/http_client_impl.py` | Update | 更新 `get` 签名以兼容接口，但不实现动态逻辑。 |

### Domain Layer (领域层)
| 文件路径 | 变更类型 | 说明 |
| :--- | :--- | :--- |
| `src/crawl/domain/domain_service/domain_score_manager.py` | **New** | 实现域名分数的存储、更新与查询逻辑。 |
| `src/crawl/domain/demand_interface/i_http_client.py` | Update | 接口增加 `render_js: bool` 参数。 |
| `src/crawl/domain/value_objects/crawl_config.py` | Update | 增加 `enable_dynamic_scoring` 配置开关。 |

### Application Layer (应用层)
| 文件路径 | 变更类型 | 说明 |
| :--- | :--- | :--- |
| `src/crawl/services/crawler_service.py` | Update | 1. 初始化 `DomainScoreManager`。<br>2. 在 `_execute_crawl_loop` 中植入启发式检测逻辑。<br>3. 在请求结束后收集反馈并更新分数。<br>4. 在入队时根据动态分数计算优先级。 |

### Interface Layer (接口层)
| 文件路径 | 变更类型 | 说明 |
| :--- | :--- | :--- |
| `src/crawl/view/crawler_view.py` | Update | 在组合根中实例化 `PlaywrightClient` 并组装 `HybridHttpClient`。 |

---

## 3. 环境与依赖 (Dependencies)
本次更新引入了新的外部依赖，部署时需执行：

```bash
pip install playwright
playwright install chromium
```

## 4. 后续优化方向 (Future Roadmap)
1.  **浏览器池化**: 当前 `PlaywrightClient` 每次请求都启动新实例以保证隔离性，未来可引入对象池优化性能。
2.  **指纹对抗**: `HybridHttpClient` 可集成 `fake-useragent` 或指纹注入，防止被反爬虫识别。
3.  **持久化评分**: 当前 `DomainScoreManager` 存储在内存中，重启后重置。未来可将其状态持久化到 Redis 或数据库。

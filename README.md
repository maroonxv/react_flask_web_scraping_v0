本项目采用前后端分离架构
前端使用React.js，后端使用Flask

这是一个 网络爬虫项目，用于从指定的URL中提取数据。

1、实现基于请求队列的广度优先爬取策略/深度优先爬取策略/大战优先爬取策略(至少一种以上),实现Robots协议解析与遵守,实现URL去重PDF链接。
2、提取关键信息如标题、作者、摘要、关键词、发表时间、URL链接等保存。
3、实现爬取速率控制(请求间隔),能够监控爬取状态和记录爬取日志,有一定的设计异常处理机制(网络异常、解析失败等)。
4、界面友好,能够控制爬取开始和结束,显示爬取状态、爬取结果等信息。

采取领域驱动开发的原则进行项目设计和开发。
后端使用Flask框架,实现RESTful API,与前端进行交互。
暂时只实现了crawl一个app，负责爬取功能的实现。

crawl的源码按照领域驱动开发的原则进行组织
- domain：领域层，负责定义领域实体、值对象、领域事件、领域服务与需求方接口
- services：应用层，负责协调领域层的组件
- infrastructure：基础设施层，负责调用外部系统的提供方接口，实现领域层定义的需求方接口以及领域服务

- views：视图层，负责处理HTTP请求和响应，与前端进行交互，相当于前后端的适配器

前端使用React.js,实现用户界面的展示和交互。



后端的测试已经写得比较完善了，有单元测试和集成测试。
单元测试包括对于 infrastructure 层的 http_client_impl.py、html_parser_impl.py、robots_txt_parser_impl.py、url_queue_impl.py的测试
集成测试包括


### 推荐方案：ToScrape 沙盒（最佳效果）
这个网站有两个清晰的子站（书店和名言），非常适合模拟“从入口发现多个站点，并优先爬取其中一个”的场景。

- 入口 URL : http://toscrape.com
- 子站 A : books.toscrape.com
- 子站 B : quotes.toscrape.com
测试配置建议：

1. 起始 URL : http://toscrape.com
2. 允许的域名 : toscrape.com, books.toscrape.com, quotes.toscrape.com
3. 大站优先域名 : books.toscrape.com （您可以填这个，验证是否书店的页面会被优先抓取并打上 ⭐）
### 备选方案 1：Crawler Test
这是您默认配置中的网站，它包含各种链接测试。

- 入口 URL : https://crawler-test.com/
- 测试方法 : 这个网站有很多子页面。您可以随便挑一个二级路径作为“大站”来测试正则匹配（虽然它是单域名，但在我们的逻辑里，通常是匹配域名后缀。如果我们的逻辑严格匹配域名，这个可能不太好测“跨站”优先级，除非它有外链）。
  - 注：由于我们的逻辑是匹配 priority_domains （域名），对于单域名的网站，大站策略可能无法区分同域名下的不同路径。因此强烈建议使用上面的 ToScrape 方案。
### 备选方案 2：Scrape This Site
另一个流行的练习场。

- 入口 URL : https://www.scrapethissite.com/
- 特点 : 包含“Sandbox”和“Lessons”等不同板块。
### 总结
为了最直观地看到**⭐图标 和 优先调度**的效果，请使用 ToScrape 组合：

- Start URL : http://toscrape.com
- Allow Domains : toscrape.com, books.toscrape.com, quotes.toscrape.com
- Priority Domains : books.toscrape.com
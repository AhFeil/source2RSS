# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

source2RSS 是一个通用的信息源转 RSS 的 Python 框架。开发者只需编写抓取器，框架负责 RSS 生成、存储、调度、访问控制和 Web 界面。

## 开发命令

```bash
just run                    # 启动开发服务器（端口 8536）
just test                   # 运行测试（排除慢速测试，自动启停 d_agent）
```

## 架构

### 核心流程

注册抓取器 → 触发（定时或 API）→ 抓取器返回文章 → 保存到数据库 → 生成 RSS → 通过 Web 提供访问

### 核心组件

- **src/scraper/**: 插件化抓取器系统。抓取器继承自 `WebsiteScraper`，通过 `ScraperMeta` 元类自动注册。
- **src/crawl/**: 爬虫调度、RSS 生成、分布式抓取逻辑。
- **src/web/**: FastAPI 路由，处理 RSS 交付、用户管理、源管理。
- **src/data/**: SQLite 数据库层，使用 SQLAlchemy ORM。
- **src/node/**: Agent 节点，用于分布式抓取（direct/reverse agent）。

### 抓取器模式

**单实例抓取器**: 每个源只有一个抓取器实例（如博客 RSS）。不要重写 `__init__`。

**多实例抓取器**: 一个抓取器类有多个实例（如 B站 UP 动态）。重写 `__init__` 接受参数，每组唯一参数在数据库中创建独立源。

需实现的关键接口：
- `_source_info()`: 返回元信息字典（name、link、desc、key4sort、table_name、access）
- `_parse()`: 异步生成器，按从新到旧顺序 yield 文章字典
- 可选：`_parse_old2new()` 支持反向分页

参考模板：`src/scraper/examples/cslrxyz.py`

### Agent 架构

- **Direct Agent (d)**: 内网 Agent 向公网服务器发起连接
- **Reverse Agent (r)**: 公网服务器主动连接
- 公网服务器根据 Agent 能力和配置分配任务

## 配置

主配置：`config_and_data_files/config.yaml`
- `enabled_web_scraper`: 要加载的插件路径
- `crawler_default_cfg`: 调度时间、等待间隔
- `known_agents`: 分布式爬虫的 Agent 连接配置

Agent 配置：`examples/agent_config.example.yaml`

## 测试

测试配置：`tests/test_config.yaml`
测试隔离：使用独立的 `tests/config_and_data_files/` 目录

## Web 端点

- `/source2RSS/{source_name}.xml` - 公开 RSS（无需认证）
- `/query_rss/{source_name}.xml` - 需要认证的 RSS
- `/post_src/{source_name}` - POST 文章创建 RSS
- `/usage` - 列出所有可用源

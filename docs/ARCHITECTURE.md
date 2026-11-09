# 架构设计文档

本文档描述扫地机器人智能客服系统的内部设计，配合根目录 `README.md` 阅读。

## 1. 分层总览

系统自上而下分为四层：

| 层 | 模块 | 职责 |
|---|---|---|
| 交互层 | `app.py` | Streamlit 聊天界面、流式渲染、会话历史 |
| 智能体层 | `agent/react_agent.py`、`agent/tools/` | ReAct 决策、工具调用、中间件增强 |
| 能力层 | `rag/`、`model/` | 检索总结、向量存储、模型实例 |
| 基础设施层 | `utils/`、`config/`、`prompts/` | 配置、提示词、日志、文件与路径工具 |

## 2. 智能体层

### 2.1 ReactAgent

`agent/react_agent.py` 中的 `ReactAgent` 对 LangChain `create_agent` 做了一层封装：

- 装配 `model`（模型工厂产物）、`system_prompt`（主提示词）、7 个 `tools`、3 个 `middleware`；
- `execute_stream(query)` 以 `stream_mode="values"` 流式执行，逐段 yield 最新消息内容；
- 通过 `context={"report": False}` 向运行时注入初始上下文，供报告场景切换使用。

### 2.2 工具（agent/tools/agent_tools.py）

| 工具 | 入参 | 作用 |
|---|---|---|
| `rag_summarize` | `query` | 调用 RAG 服务检索并总结知识库 |
| `get_city_name` | 无 | 获取用户城市（演示：随机） |
| `get_weather` | `city` | 获取天气（演示：固定值） |
| `get_user_id` | 无 | 获取用户 ID（演示：随机） |
| `get_current_month` | 无 | 获取月份（演示：随机） |
| `fetch_external_data` | `user_id, month` | 读取使用记录 CSV |
| `fill_context_for_report` | 无 | 触发报告场景上下文注入 |

`fetch_external_data` 首次调用时惰性加载 `records.csv` 到内存字典 `external_data[user_id][month]`，缺失记录返回空字典并记录告警。

### 2.3 中间件（agent/tools/middleware.py）

- `monitor_tool`（`@wrap_tool_call`）：记录工具名与参数、成功/失败日志；当工具为 `fill_context_for_report` 时，将 `runtime.context["report"]` 置为 `True`。
- `log_before_model`（`@before_model`）：模型调用前记录消息数量与最新消息。
- `report_prompt_switch`（`@dynamic_prompt`）：读取 `context["report"]`，为 `True` 时返回报告提示词，否则返回主提示词。

**提示词动态切换链路**是本项目的设计亮点：将「问答」与「报告生成」两种人格解耦，无需在业务代码中硬编码分支，由中间件在模型调用前动态决定使用哪套提示词。

## 3. 能力层

### 3.1 模型工厂（model/factory.py）

采用抽象工厂模式：`BaseModelFactory` 定义 `generator()` 抽象方法，`ChatModelFactory` 与 `EmbeddingModelFactory` 分别产出 `ChatTongyi` 与 `DashScopeEmbeddings`。模块级单例 `chat_model` / `embedding_model` 在导入时创建，供全局复用。

### 3.2 RAG 流水线

**离线（`rag/vector_store.py` 的 `load_documents`）：**

```
遍历 data/ 允许类型文件 → 计算 MD5 → 已处理则跳过
  → PDF/TXT 加载为 Document → RecursiveCharacterTextSplitter 分块
  → 嵌入并写入 Chroma → 记录 MD5
```

MD5 去重保证增量加载：仅新增或内容变更的文档才会重新嵌入。

**在线（`rag/rag_service.py` 的 `rag_summarize`）：**

```
query → retriever 检索 top-k 文档 → 拼接为带元数据的参考资料
  → 填充 RAG 提示词模板 → 模型 → StrOutputParser → 总结字符串
```

## 4. 基础设施层

- `utils/cofig_handler.py`：加载四个 YAML 配置为模块级字典。
- `utils/prompt_loader.py`：按配置路径加载三套提示词，缺失配置项/文件时记录并抛出异常。
- `utils/path_tool.py`：以本文件位置推导项目根目录，提供 `get_abspath`，使运行不依赖当前工作目录。
- `utils/file_handler.py`：MD5 计算、按类型遍历目录、PDF/TXT 加载。
- `utils/logger_handler.py`：统一日志器，控制台 + 按天文件输出。

## 5. 关键设计取舍

- **配置与提示词外置**：模型 ID、分块参数、提示词内容均与代码分离，便于调整而无需改代码。
- **中间件而非硬编码分支**：报告场景切换通过运行时上下文 + 动态提示词实现，扩展新场景只需新增中间件。
- **增量知识库**：MD5 去重降低重复嵌入成本。
- **演示用模拟工具**：天气/城市/用户/月份为模拟实现，便于在无外部依赖时跑通完整 ReAct 链路。
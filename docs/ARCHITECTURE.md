# 架构设计文档

本文档描述扫地机器人智能客服系统的内部设计，配合根目录 `README.md` 阅读。

## 1. 分层总览

系统自上而下分为四层：

| 层 | 模块 | 职责 |
|---|---|---|
| 交互层 | `app.py` | Streamlit 聊天界面、流式渲染、会话管理侧边栏 |
| 智能体层 | `agent/react_agent.py`、`agent/tools/` | ReAct 决策、工具调用、中间件增强 |
| 能力层 | `rag/`、`model/` | 检索总结、向量存储、模型实例 |
| 基础设施层 | `utils/`、`config/`、`prompts/` | 配置、提示词、日志、文件与路径工具 |

## 2. 智能体层

### 2.1 ReactAgent

`agent/react_agent.py` 中的 `ReactAgent` 对 LangChain `create_agent` 做了一层封装：

- 装配 `model`（模型工厂产物）、`system_prompt`（主提示词）、7 个 `tools`、3 个 `middleware`；
- `execute_stream(query, history)` 以 `stream_mode="values"` 流式执行，逐段 yield 最新消息内容；`history` 为既往对话，按滑动窗口仅保留最近 8 条，避免上下文无限增长；
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

采用抽象工厂模式：`BaseModelFactory` 定义 `generator()` 抽象方法，`ChatModelFactory` 与 `EmbeddingModelFactory` 分别产出 `ChatOpenAI`（新一代千问模型仅支持 OpenAI 兼容端点，`base_url` 配置化）与 `DashScopeEmbeddings`（需向封装层 `BATCH_SIZE` 表注册新模型批次上限）。模块级单例 `chat_model` / `embedding_model` 在导入时创建，供全局复用。

### 3.2 RAG 流水线

**离线（`rag/vector_store.py` 的 `load_documents`）：**

```
遍历 data/ 允许类型文件 → 计算 MD5 → 已处理则跳过
  → PDF/TXT 加载为 Document → RecursiveCharacterTextSplitter 分块
  → 嵌入并写入 Chroma → 记录 MD5
```

MD5 去重保证增量加载：仅新增或内容变更的文档才会重新嵌入。注意 MD5 记录与集合配套：更换嵌入模型时向量空间不兼容，需同时换新集合名与 MD5 记录文件重建。

**在线（`rag/rag_service.py` 的 `rag_summarize`）：**

```
query → retriever 粗召回 top-k 文档 → DashScopeRerank 精排留 top-n
  → 拼接为带元数据的参考资料 → 填充 RAG 提示词模板 → 模型 → StrOutputParser → 总结字符串
```

两段式检索：粗召回保覆盖率，精排保相关性；精排模型名构造后显式覆盖（封装层默认模型已下线），精排后文档 metadata 附带 `relevance_score`。

### 3.3 离线测评（evals/）

轻量测评模块，不引入额外评估框架，直接复用生产链路的 `RagSummarizeService`：

- **标注集**：`evals/dataset.jsonl`，每行一个用例（`query` / `keywords` / `source`），随代码进版本库；
- **指标**：检索关键词召回率、期望来源命中率；`--with-answer` 时额外算答案关键词覆盖率（忠实度代理指标）；
- **消融对照**：`--no-rerank` 基线用粗召回截断到相同 top_n，与默认 rerank 组对照量化精排贡献；基线答案用已检索片段直接走总结链，保证上下文拼接一致；
- **报告**：带时间戳存入 `evals/results/`（gitignore），支持历次纵向对比；改动检索相关配置后重跑对照，指标不回退再上线。

实测基线 vs rerank（12 用例）：关键词召回 79.2% → 91.7%，来源命中 83.3% → 91.7%。注意关键词覆盖是代理指标：否定表述（如"不可直接冲洗"）与跨分片关键词会造成假阴性，低分用例需人工复核而非直接归咎检索。

## 4. 基础设施层

- `utils/cofig_handler.py`：加载四个 YAML 配置为模块级字典。
- `utils/prompt_loader.py`：按配置路径加载三套提示词，缺失配置项/文件时记录并抛出异常。
- `utils/path_tool.py`：以本文件位置推导项目根目录，提供 `get_abspath`，使运行不依赖当前工作目录。
- `utils/file_handler.py`：MD5 计算、按类型遍历目录、PDF/TXT 加载。
- `utils/logger_handler.py`：统一日志器，控制台 + 按天文件输出。
- `utils/session_store.py`：SQLite 会话持久化，提供建表与新建/列表/加载/保存/删除。

### 4.1 会话存储（utils/session_store.py）

为 Web 端提供多轮对话的持久化，单表 `sessions` 存储：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | 会话唯一 ID |
| `title` | TEXT | 侧边栏标题，取首条用户消息前 20 字 |
| `messages` | TEXT | 整段对话的 JSON（role/content 列表） |
| `created_at` / `updated_at` | DATETIME | 创建 / 最近活跃时间 |

CRUD：`create_session` / `list_sessions`（按 `updated_at` 倒序）/ `load_messages` / `save_messages` / `delete_session`。

设计要点：

- **整段 JSON 存储**：demo 规模下整读整写最简单，无需按消息拆表；
- **随用随开连接**：每次操作独立 `connect`/`commit`/`close`，规避 Streamlit 多线程下的 `check_same_thread` 限制；
- **中文不转义**：`json.dumps(..., ensure_ascii=False)`；
- **懒创建会话**：点击「新建」仅清空状态，首条消息落库时才真正 `INSERT`，避免空会话；
- **只存最终对话**：持久化干净的 user/assistant 文本，不含 ReAct 中间工具轨迹。

## 5. 关键设计取舍

- **配置与提示词外置**：模型 ID、分块参数、提示词内容均与代码分离，便于调整而无需改代码。
- **中间件而非硬编码分支**：报告场景切换通过运行时上下文 + 动态提示词实现，扩展新场景只需新增中间件。
- **增量知识库**：MD5 去重降低重复嵌入成本。
- **演示用模拟工具**：天气/城市/用户/月份为模拟实现，便于在无外部依赖时跑通完整 ReAct 链路。
- **会话存储选 SQLite**：单机单用户、低并发场景下零依赖、免起服务，克隆即可跑，降低复现门槛；多用户线上部署再迁移 MySQL（SQL 与表设计通用）。
- **滑动窗口上下文**：仅向模型传入最近若干轮历史，控制 token 成本与上下文长度，避免长会话超窗口。
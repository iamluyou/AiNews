# 技术总结与使用说明

## 文档变更记录

| 版本 | 日期 | 修改人 | 修改说明 |
|-----|------|--------|---------|
| v1.0 | 2026-04-16 | Claude | 初始版本 |

## 一、技术栈总结

### 1.1 核心技术栈

| 模块 | 技术选型 | 版本 | 用途 |
|------|---------|------|------|
| 编程语言 | Python | 3.9.6 | 主要开发语言 |
| Web 框架 | Flask | 最新 | Web 管理界面 |
| 定时任务 | APScheduler | 最新 | Cron 定时调度 |
| 数据库 | SQLite | 最新 | 新闻数据存储 |
| ORM | SQLAlchemy | 最新 | 数据库操作 |
| 配置管理 | Pydantic + YAML | 最新 | 配置验证与管理 |
| HTTP 请求 | requests + BeautifulSoup | 最新 | 网页爬虫 |
| 大模型 | OpenAI SDK | 最新 | 新闻智能排序 |
| 邮件 | smtplib | 标准库 | 邮件通知 |
| 日志 | loguru | 最新 | 日志记录 |

### 1.2 项目结构

```
MVP/
├── config/
│   └── settings.yaml              # 配置文件
├── src/
│   ├── news_agent/
│   │   ├── __init__.py
│   │   ├── config.py               # 配置管理
│   │   ├── scheduler.py            # 定时调度器
│   │   ├── main.py                 # 入口文件
│   │   ├── models/
│   │   │   └── news.py            # 新闻数据模型
│   │   ├── crawlers/               # 爬虫模块
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # 爬虫基类
│   │   │   ├── kr36.py            # 36氪爬虫
│   │   │   ├── aiera.py           # Aiera 爬虫
│   │   │   ├── radar.py           # RadarAI 爬虫
│   │   │   └── qbit.py            # QbitAI 爬虫
│   │   ├── llm/                    # LLM 模块
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # LLM 基类
│   │   │   └── client.py          # OpenAI 客户端
│   │   ├── notifiers/              # 通知模块
│   │   │   ├── __init__.py
│   │   │   ├── base.py            # 通知基类
│   │   │   ├── feishu.py          # 飞书通知
│   │   │   └── email_163.py      # 163 邮件通知
│   │   ├── storage/                # 存储模块
│   │   │   ├── __init__.py
│   │   │   ├── database.py        # 数据库初始化
│   │   │   └── repository.py      # 数据访问层
│   │   ├── utils/                  # 工具模块
│   │   │   ├── __init__.py
│   │   │   └── logger.py          # 日志工具
│   │   └── web/                    # Web 管理界面
│   │       ├── __init__.py
│   │       ├── app.py             # Flask 应用
│   │       ├── templates/
│   │       │   └── index.html     # 前端页面
│   │       └── static/
│   │           └── css/
│   │               └── style.css  # 前端样式
│   ├── run_once.py                 # 单次执行脚本
│   └── tests/                      # 单元测试
│       └── test_web_config.py
├── data/                           # 数据目录
│   └── news.db                    # SQLite 数据库
├── logs/                           # 日志目录
│   ├── news_agent.log             # 应用日志
│   ├── scheduler.log              # Scheduler 日志
│   └── scheduler.pid              # Scheduler PID
├── start_scheduler.sh              # 启动 Scheduler
├── stop_scheduler.sh               # 停止 Scheduler
├── view_logs.sh                    # 查看日志
├── start_web.sh                    # 启动 Web 界面
├── requirements.txt                # 依赖列表
└── pyproject.toml                  # 项目配置
```

## 二、核心功能说明

### 2.1 新闻爬虫

#### 支持的网站
- **36氪** (kr36) - https://36kr.com
- **Aiera** (aiera) - https://www.aiera.com
- **RadarAI** (radar) - https://radarai.top
- **QbitAI** (qbit) - https://www.qbitai.com

#### 爬虫基类 (`BaseCrawler`)
```python
class BaseCrawler:
    name: str = ""
    url: str = ""

    def fetch(self) -> List[NewsItem]:
        """抓取新闻，返回 NewsItem 列表"""
        pass
```

#### 新增爬虫
1. 继承 `BaseCrawler`
2. 实现 `fetch()` 方法
3. 在 `crawlers/__init__.py` 中注册到 `CRAWLER_REGISTRY`

---

### 2.2 LLM 智能排序

#### 核心流程
1. **分批处理**：新闻按 `batch_size` 分批
2. **LLM 筛选**：每批用 LLM 选出 Top N
3. **合并排序**：所有候选用关键词排序
4. **降级方案**：LLM 失败时用关键词筛选

#### 配置项 (`settings.yaml`)
```yaml
llm:
  base_url: https://api.openai.com/v1
  api_key: sk-xxx
  model: gemma-4-e2b-it
  use_llm_for_ranking: true
  batch_size: 30
  top_n_per_batch: 10
  final_top_n: 20
  fallback_per_source: 10
  ranking_prompt: "自定义提示词..."
```

---

### 2.3 通知系统

#### 支持的通知方式
1. **飞书 Webhook**
2. **163 邮件**

#### 通知基类 (`BaseNotifier`)
```python
class BaseNotifier:
    name: str = ""

    def send(
        self,
        news_list: List[NewsItem],
        title: str = "新闻推送",
        used_llm: bool = False,
        custom_message: str = None
    ) -> bool:
        """发送通知"""
        pass
```

#### 新增通知器
1. 继承 `BaseNotifier`
2. 实现 `send()` 方法
3. 在 `scheduler.py` 中初始化

---

### 2.4 数据存储

#### 数据库模型 (`NewsModel`)
| 字段 | 类型 | 说明 |
|------|------|------|
| url | String | 新闻 URL（主键） |
| title | String | 新闻标题 |
| cover_image | String | 封面图（可选） |
| publish_time | DateTime | 发布时间（可选） |
| source | String | 来源网站 |
| content | Text | 内容（可选） |
| ai_relevance_score | Float | AI 相关度评分（可选） |
| created_at | DateTime | 创建时间 |
| sent_at | DateTime | 发送时间（可选） |

#### Repository 方法
```python
NewsRepository.add(news_item)           # 添加单条
NewsRepository.add_batch(news_list)      # 批量添加
NewsRepository.get_unsent()               # 获取未发送新闻
NewsRepository.mark_as_sent(urls)         # 标记为已发送
NewsRepository.is_sent(url)               # 检查是否已发送
```

---

### 2.5 Web 管理界面

#### 功能特性
1. **新闻爬虫状态**：显示 Scheduler 运行状态
2. **新闻爬虫开关**：启动/停止 Scheduler
3. **日志信息**：实时显示日志
4. **新闻爬虫配置**：
   - 定时时间设置
   - 收件人设置
   - 启用邮件开关
   - 加载/保存配置
   - 一键获取新闻

#### API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 主页 |
| GET | `/api/config` | 获取配置 |
| POST | `/api/config` | 保存配置 |
| GET | `/api/config-save-status` | 配置保存状态 |
| GET | `/api/scheduler/status` | 获取 Scheduler 状态 |
| POST | `/api/scheduler/start` | 启动 Scheduler |
| POST | `/api/scheduler/stop` | 停止 Scheduler |
| POST | `/api/fetch-news` | 触发新闻抓取 |
| GET | `/api/fetch-status` | 抓取状态 |

---

## 三、使用说明

### 3.1 环境准备

#### 1. 安装依赖
```bash
cd MVP
pip install -r requirements.txt
```

#### 2. 配置文件
编辑 `config/settings.yaml`：
```yaml
# 邮件配置
email_163:
  enabled: true
  sender: your-email@163.com
  sender_name: AI 新闻助手
  password: your-password
  recipients:
    - user1@example.com
    - user2@example.com

# 飞书配置
feishu:
  enabled: true
  webhook_url: https://open.feishu.cn/...

# LLM 配置
llm:
  base_url: https://api.example.com/v1
  api_key: sk-xxx
  model: gemma-4-e2b-it
  use_llm_for_ranking: true

# 定时任务
scheduler:
  cron_times:
    - '08:30'
    - '11:30'
    - '17:30'
  timezone: Asia/Shanghai
```

---

### 3.2 启动方式

#### 方式一：单次执行
```bash
python3 src/run_once.py
```

#### 方式二：Scheduler 后台运行
```bash
# 启动
./start_scheduler.sh

# 停止
./stop_scheduler.sh

# 查看日志
./view_logs.sh
```

#### 方式三：Web 管理界面
```bash
./start_web.sh
```
访问：http://localhost:5547

---

### 3.3 Web 界面使用

1. **查看状态**：
   - 新闻爬虫状态：显示 Scheduler 运行状态

2. **控制开关**：
   - 点击开关启动/停止相应服务
   - 点击"刷新"更新状态

3. **查看日志**：
   - 点击"显示日志"展开日志面板
   - 日志实时刷新，自动滚动到底部

4. **配置管理**：
   - 点击"加载配置"读取当前配置
   - 修改后点击"保存配置"（会自动重启 Scheduler）
   - 点击"获取新闻"手动触发一次抓取

---

### 3.4 日志说明

| 日志文件 | 说明 |
|---------|------|
| `logs/news_agent.log` | 应用主日志 |
| `logs/scheduler.log` | Scheduler 输出日志 |

---

## 四、常见问题

### Q1: Scheduler 启动后不触发任务？
**A**: 检查以下几点：
1. 确认 cron_times 格式正确（用单引号括起来）
2. 确认 timezone 设置正确
3. 查看 scheduler.log 日志

### Q2: LLM 处理超时怎么办？
**A**: 系统有自动降级机制：
1. LLM 超时会自动使用关键词筛选
2. 可以调整 llm.timeout 配置
3. 可以设置 use_llm_for_ranking: false 禁用 LLM

### Q3: 如何添加新的爬虫网站？
**A**: 按以下步骤：
1. 在 `src/news_agent/crawlers/` 下创建新爬虫类
2. 继承 `BaseCrawler`，实现 `fetch()` 方法
3. 在 `crawlers/__init__.py` 中注册
4. 在 `settings.yaml` 的 crawlers.enabled 中添加

### Q4: 邮件发不出去？
**A**: 检查：
1. 确认 163 邮箱开启 SMTP 服务
2. 确认密码是授权码（不是登录密码）
3. 查看日志中的错误信息

---

## 五、扩展开发

### 5.1 添加新的通知器

示例：钉钉通知
```python
# src/news_agent/notifiers/dingtalk.py
from .base import BaseNotifier
from ..models.news import NewsItem
from ..utils.logger import get_logger

logger = get_logger(__name__)

class DingTalkNotifier(BaseNotifier):
    name = "dingtalk"

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, news_list: List[NewsItem], title: str = "新闻推送",
             used_llm: bool = False, custom_message: str = None) -> bool:
        # 实现发送逻辑
        pass
```

### 5.2 自定义 LLM 提示词

在 `settings.yaml` 中修改 `llm.ranking_prompt`：
```yaml
llm:
  ranking_prompt: |
    请从以下新闻中选出最相关的 {top_n} 条 AI 相关新闻...
    【评分权重规则】
    ...
```

---

## 六、维护建议

### 6.1 日常维护
1. 定期检查日志，确认任务正常执行
2. 定期清理旧日志（loguru 已配置自动轮转）
3. 定期备份数据库

### 6.2 监控告警
1. 监控 Scheduler 进程是否存活
2. 监控新闻抓取成功率
3. 监控 LLM 调用成功率
4. 监控通知发送成功率

### 6.3 性能优化
1. 爬虫添加请求缓存
2. LLM 结果缓存
3. 数据库添加索引
4. 考虑使用 Redis 缓存

---

## 七、总结

本项目采用模块化设计，各模块职责清晰，易于扩展。核心特性包括：

1. **多网站爬虫**：可插拔的爬虫架构
2. **AI 智能排序**：LLM + 关键词双重保障
3. **多渠道通知**：飞书 + 邮件灵活配置
4. **Web 管理界面**：直观易用的可视化管理
5. **配置化设计**：无需修改代码即可调整行为

通过合理的技术选型和清晰的架构设计，项目具有良好的可维护性和可扩展性。

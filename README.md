# MVP 新闻爬虫与 AI 整理系统

自动化的新闻采集、AI 整理与分发系统。

## 功能特性

- 多网站新闻爬虫（机器之心、36氪、Aiera、RadarAI、QbitAI）
- 定时任务调度（可配置多个时间点）
- 大模型智能整理与排序
- 飞书群通知
- 163 邮件推送
- 模块化设计，易于扩展

## 快速开始

### 1. 安装依赖

```bash
cd MVP
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config/settings.yaml.example config/settings.yaml
# 编辑 config/settings.yaml，填写实际配置
```

### 3. 运行

```bash
cd src
python -m news_agent.main
```

## 项目结构

```
MVP/
├── src/
│   └── news_agent/         # 主包
│       ├── crawlers/        # 爬虫模块
│       ├── models/          # 数据模型
│       ├── storage/         # 存储模块
│       ├── llm/             # 大模型模块
│       ├── notifiers/       # 通知模块
│       └── utils/           # 工具模块
├── config/                  # 配置文件
├── docs/                    # 文档
└── tests/                   # 测试
```

## 开发

### 运行测试

```bash
pytest src/tests/
```

### 代码格式化

```bash
black src/
isort src/
```

## License

MIT

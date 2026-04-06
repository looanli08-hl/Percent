<div align="center">

<img src="assets/logo.svg" alt="Percent logo" width="120" height="120" />

# Percent

**你的数字痕迹，能还原百分之多少的你？**

[![CI](https://github.com/looanli08-hl/percent/actions/workflows/ci.yml/badge.svg)](https://github.com/looanli08-hl/percent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

[文档](#工作原理) · [快速开始](#快速开始) · [PersonaBench](#personabench) · [参与贡献](#参与贡献) · [English](README.md)

</div>

---

## 为什么需要 Percent？

每个 AI 助手都从零开始。它不知道你怎么思考、在乎什么、习惯怎么表达。每次对话你都要重新介绍自己。

**Percent 解决了这个问题。**

把你的微信聊天记录、B 站观看历史、YouTube 记录喂给它——任何能反映你真实思维的数据。Percent 从中提取你的人格，生成结构化的 `core.md`，让任何大语言模型都能成为真正属于你的 AI，而不是千篇一律的通用助手。

- **隐私优先。** 原始数据保存在本地。使用云端模型（OpenAI/Claude/DeepSeek）时，文本片段会发送到对应提供商进行分析——使用 Ollama 可实现完全本地处理。
- **数据源无关。** 微信、YouTube、B 站——更多来源持续接入。
- **模型无关。** 兼容 Claude、GPT-4、DeepSeek、Ollama 等所有 LiteLLM 支持的模型。
- **可量化。** PersonaBench 给出具体的准确率分数，不是感觉。

---

## PersonaBench

PersonaBench 是 Percent 内置的人格一致性基准测试，衡量你的人格模型有多准确地反映了真实的你。

```
PersonaBench v0.1
Score: 72.5%  (10 tests)

  [1] 0.95  游戏偏好和主动邀约行为完全一致
  [2] 0.90  数码研究习惯和务实风格高度匹配
  [3] 0.90  家教细节和精打细算心态精准对齐
  [4] 0.90  实用主义价值观和省钱行为符合档案
  [5] 0.80  足球热情和球队忠诚度预测正确
  [6] 0.80  直接表达风格和技术好奇心得到验证
  [7] 0.70  情绪表达模式部分匹配
  [8] 0.70  吐槽风格一致但实际回应更偏叙事
  [9] 0.30  回应格式偏离预测的互动模式
  [10] 0.30  预测的随性口语 vs 实际的正式描述
```

自己跑一下：

```bash
percent persona validate --num-tests 10
```

---

## 快速开始

```bash
pip install percent
percent init
percent import run wechat ~/exports/wechat_chat.csv
percent chat
```

就这四步。`import run` 完成后，Percent 已经构建好你的 `core.md`，chat 就会以你的风格说话。

---

## 工作原理

```
你的数据                  Percent 流水线               输出
─────────────────────    ────────────────────────     ──────────────────
微信 CSV            ──►  解析器（Parser）         ──►  数据块（DataChunk）
YouTube Takeout     ──►  提取器（Extractor，LLM） ──►  发现（Finding）
B 站历史            ──►  片段库（SQLite）          ──►  向量嵌入
                         合成器（Synthesizer，LLM）──►  core.md
                         人格引擎（PersonaEngine） ──►  core.md（持续更新）
                                                   ──►  Chat / SOUL.md
```

1. **解析** — 各数据源解析器将原始导出文件标准化为 `DataChunk` 对象
2. **提取** — LLM 读取每个数据块，提取人格发现（特质、观点、偏好）
3. **存储** — 发现被嵌入并存储到本地 SQLite + 向量索引
4. **合成** — 所有发现被压缩为结构化的 `core.md` 人格档案
5. **使用** — 与你的人格对话，或导出 `SOUL.md` 作为任何系统提示

---

## 支持的数据源

| 数据源 | 格式 | 命令 |
|--------|------|------|
| 微信 | PyWxDump CSV 导出 | `percent import run wechat <路径>` |
| YouTube | Google Takeout JSON | `percent import run youtube <路径>` |
| B 站 | 观看历史 JSON | `percent import run bilibili <路径>` |

欢迎提交更多数据源——参见[参与贡献](#参与贡献)。

---

## 命令参考

```
percent init                         配置 API key 和模型提供商
percent import run <来源> <路径>      导入并分析数据
percent import guide <来源>           查看某数据源的导出说明
percent import status                查看片段库统计

percent persona view                 打印当前 core.md
percent persona stats                片段统计
percent persona rebuild              从所有存储的片段重建 core.md
percent persona validate             运行 PersonaBench

percent export soul                  生成 SOUL.md 系统提示
percent export core                  将 core.md 复制到指定路径

percent chat                         与你的人格进行交互对话
percent config llm                   修改 LLM 提供商 / 模型 / key
percent config parsers               列出可用的解析器
```

---

## 架构

```
percent/
├── cli.py                  Typer CLI 入口
├── config.py               PercentConfig（Pydantic），加载/保存 YAML
├── models.py               DataChunk、Finding、Fragment（Pydantic）
├── llm/
│   └── client.py           LiteLLM 封装（提供商无关）
├── parsers/
│   ├── base.py             DataParser 抽象基类
│   ├── bilibili.py         B 站观看历史
│   ├── youtube.py          YouTube Takeout
│   └── wechat.py           微信 PyWxDump CSV
├── persona/
│   ├── engine.py           PersonaEngine（编排提取→合成）
│   ├── extractor.py        基于 LLM 的发现提取器
│   ├── synthesizer.py      基于 LLM 的 core.md 合成器
│   ├── fragments.py        FragmentStore（SQLite + 余弦搜索）
│   ├── validator.py        PersonaValidator（对齐评分）
│   └── bench.py            PersonaBench v0.1
├── export/
│   └── soul_md.py          SOUL.md 导出器
└── chat/
    └── engine.py           ChatEngine（基于片段的 RAG）
```

---

## 参与贡献

Percent 是开源项目，欢迎贡献。

目前最有价值的贡献方向：

- **新数据源解析器** — Spotify、Twitter/X、Notion、iMessage
- **提示词优化** — 改进 `prompts/` 下的提取和合成提示词
- **PersonaBench 数据集** — 用于校准的参考人格数据

添加解析器：在 `percent/parsers/` 中继承 `DataParser`，在 `cli.py` 注册，并在 `tests/test_parsers/` 下添加测试。

```bash
git clone https://github.com/looanli08-hl/percent
cd percent
uv sync
uv run pytest tests/ -v
```

---

## 许可证

MIT — 随意使用。你的人格模型属于你。

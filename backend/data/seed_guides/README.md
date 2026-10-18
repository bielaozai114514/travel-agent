# 种子攻略目录

用于 RAG 测试语料管理、删库后快速恢复、Qdrant 索引重建和论文实验复现。

## 文件格式

每个攻略由一组 JSON + Markdown 文件组成：

### JSON 元数据

```json
{
  "import_key": "hangzhou_elder_3d2n",
  "title": "杭州3天2晚老人轻松游攻略",
  "city": "杭州",
  "summary": "攻略摘要...",
  "content_file": "example_hangzhou_elder_3d2n.md",
  "content_format": "markdown",
  "tags": ["杭州", "三日游"],
  "status": "published",
  "is_official": true,
  "is_ai_generated": false,
  "author_username": "admin"
}
```

### Markdown 正文

推荐使用二级标题（##）和三级标题（###）组织内容，TCR-RAG 分块依赖标题结构。

## 字段说明

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| import_key | 是 | - | 全局唯一标识，用于幂等更新 |
| title | 是 | - | 攻略标题 |
| city | 是 | - | 标准城市名（杭州、成都、北京），不要写"杭州市"或"浙江杭州" |
| summary | 否 | "" | 攻略摘要 |
| content_file | 否* | - | Markdown 正文文件名（与 JSON 同目录） |
| content | 否* | - | 正文内容（与 content_file 二选一） |
| content_format | 否 | "markdown" | 内容格式 |
| tags | 否 | [] | 标签数组，建议包含城市、主题、人群、天数、核心景点 |
| status | 否 | "published" | 攻略状态，published 才会同步到 Qdrant |
| is_official | 否 | true | 是否官方攻略 |
| is_ai_generated | 否 | false | 必须为 false，否则 sync_guide_to_rag 会跳过 |
| author_id | 否 | - | 作者 ID |
| author_username | 否 | - | 作者用户名，用于查询数据库获取 author_id |

\* content_file 和 content 至少填一个。

## content_path 自动生成

导入时自动设置 `content_path = "seed://{import_key}"`，作为幂等更新标识。

## 导入命令

```bash
cd backend

# 预览（不写入数据库）
python scripts/import_guides.py --dir data/seed_guides --author-username admin --dry-run

# 正式导入
python scripts/import_guides.py --dir data/seed_guides --author-username admin

# 仅重建 Qdrant 索引
python scripts/import_guides.py --dir data/seed_guides --resync-only

# 清理所有种子攻略
python scripts/clear_seed_guides.py --dry-run
python scripts/clear_seed_guides.py
```

## 注意事项

- 以 `_` 开头的 JSON 文件会被忽略（如 `_import_report.json`）
- 不符合 SeedGuide schema 的 JSON 会被记录为 failed，不影响其他文件
- 同一 import_key 重复导入会更新而非重复插入

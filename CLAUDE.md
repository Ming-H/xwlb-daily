# CLAUDE.md — xwlb-daily

## 项目概述
央视新闻联播投资参考网站。每日自动抓取 CCTV 新闻联播文字稿，提取经济关键词，映射 A 股板块，生成投资信号。

## 技术栈
- 数据层：Python（爬虫 + jieba + 规则引擎）
- 展示层：Hugo + PaperMod 主题
- 部署：GitHub Pages + GitHub Actions

## 目录结构
```
xwlb-daily/
├── scraper/               # Python 数据采集+分析
│   ├── fetch_xwlb.py     # 爬虫
│   ├── extract_keywords.py
│   ├── sector_mapper.py
│   ├── signal_tracker.py
│   ├── build_content.py
│   ├── run_daily.py      # 每日入口
│   └── economic_dict.yaml # 经济词库+板块映射
├── data/                  # 原始数据 JSON
├── site/                  # Hugo 站点
│   ├── hugo.toml
│   ├── themes/PaperMod/
│   ├── layouts/
│   └── content/
└── .github/workflows/
```

## 命令
```bash
# 本地预览
cd site && hugo server --buildDrafts

# 手动运行每日流水线
python scraper/run_daily.py

# 指定日期抓取
python scraper/run_daily.py --date 20260611

# 构建
cd site && hugo --minify
```

## 数据流
CCTV官网 → fetch_xwlb.py → JSON → extract_keywords.py → sector_mapper.py → signal_tracker.py → build_content.py → Hugo Markdown → hugo build → GitHub Pages

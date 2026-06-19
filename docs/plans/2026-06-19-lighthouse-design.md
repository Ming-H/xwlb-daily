# 灯塔 Lighthouse — 重构设计方案

> 日期:2026-06-19
> 背景:将 `xwlb-daily`(新闻联播日报,单源、视角偏政策播报)重构为 **A 股投资辅助终端**。
> 方法论底座:威廉·欧奈尔《笑傲股市》CAN SLIM 法则 + IBD(投资者商业日报)产品体系,A 股本土化。

---

## 1. 定位与目标

**一句话定位**:每日自动产出「宏观大势判断 + 全市场 CAN SLIM 选股」的 A 股投资辅助终端,像 IBD 一样做"每日决策辅助"。

**为什么是「宏观 + 个股」双支柱**:CAN SLIM 的 **M(大盘方向)** 恰恰需要宏观判断;而新闻联播是 A 股最强的**政策催化剂**,正好喂给 **N(新催化)**。两支柱不是硬拼,是同一条决策链的两端:

> **宏观支柱**(自上而下):该不该进场、资金往哪流 → M
> **个股支柱**(自下而上):具体买什么、什么形态买 → C/A/N/S/L/I

**目标用户**:个人投资者(主用);兼作技术作品展示(面试)。

**设计原则**
1. **双支柱咬合** — 宏观信号直接驱动个股的 M 与 N。
2. **自动化优先** — 七要素阈值固化成 Python 规则引擎打分;LLM 只做"叙述"(催化剂解读、宏观信号),不做打分(贵且不稳)。
3. **自我验证** — 历史候选回看命中率,用结果证明方法论。
4. **CI 可跑** — 数据用 akshare(免费、纯 Python、CI 内可跑),**不依赖本地问财 skill**。
5. **YAGNI** — 不做实时行情/交易、不做美股港股、不做社区、不给买卖点承诺。

---

## 2. 信息架构(页面 ↔ IBD 模块映射)

| 灯塔页面 | 参考 IBD 模块 | 内容 | 更新 |
|---|---|---|---|
| **大盘视野** The View | The Big Picture + Market Pulse | 新闻联播 + 宏观四板块 + LLM「灯塔信号」三色(进攻/观望/防守)= CAN SLIM 的 M | 每晚 21:45 |
| **每日选股** Daily Picks | IBD 50 + Daily Stock Lists | 全市场打分排行榜 + TOP20 候选 + 每只七要素体检卡 + 趋势 SVG | 交易日 18:00 |
| **个股体检** Checkup | MarketSmith / Stock Checkup | 输入代码 → 七要素深度体检(akshare 实时取数) | 按需 |
| **命中回看** Hit Rate | *(IBD 无,灯塔独创)* | 历史 TOP20 今日表现追踪 + 累计胜率/超额净值曲线 | 交易日 18:00 |
| 新闻联播存档 | — | 现有全文存档(保留) | 每晚 |
| 板块热力 / 生命周期 | — | 现有图表(保留) | 每晚 |

导航:`大盘视野 · 每日选股 · 个股体检 · 命中回看 · 新闻存档 · 板块热力`

---

## 3. 宏观支柱 — 大盘视野

### 3.1 内容
- **新闻联播全文 + 板块/关键词信号**(现有,保留)
- **宏观四板块仪表盘**:
  - **央行与流动性**:公开市场操作净投放/回笼、Shibor、社融/M2
  - **利率汇率与外资**:10Y 国债收益率、USDCNY、北向资金净流入
  - **景气与价格**:PMI、CPI/PPI
  - **市场情绪与异动**:龙虎榜、大宗(铜/油/金)、成交额/换手热度
- **LLM「灯塔信号」**:GLM-5.2 综合上述 + 新闻联播,输出**三色市场判断**(直接服务 CAN SLIM 的 M):
  - 🟢 **进攻**(Confirmed Uptrend):指数多头、资金流入、政策友好 → 选股激进
  - 🟡 **观望**(Uptrend Under Pressure):信号矛盾/承压 → 只看不做,防守仓
  - 🔴 **防守**(Market in Correction):破位/流出 → 暂停买入,该止损止损

### 3.2 数据源(akshare)
| 指标 | akshare 接口 |
|---|---|
| 公开市场操作 | `macro_china_money_supply` / 央行公告抓取 |
| Shibor | `rate_interbank` |
| 社融/M2 | `macro_china_money_supply` |
| 10Y 国债 | `bond_zh_us_rate` |
| USDCNY | `currency_boc_sina` |
| 北向资金 | `stock_hsgt_north_net_flow_in` |
| PMI/CPI/PPI | `macro_china_*` 系列 |
| 龙虎榜 | `stock_lhb_detail_em` |
| 大宗商品 | `futures_main_sina` / `index_cci` |

### 3.3 降级
GLM 失败/限流 → 灯塔信号降级为**规则版**(指数均线 + 北向净流入符号 + 量能的简单组合),保证每日必出信号。

---

## 4. 个股支柱 — 打分引擎

### 4.1 灯塔分(Lighthouse Score,0–100)

七要素各算子分(0–100),加权合成。**阈值固化在 Python,不靠 LLM。**

| 要素 | 权重 | akshare 接口 | 子分逻辑(示例阈值) |
|---|---|---|---|
| **C** 当季净利同比 | 0.20 | `stock_financial_abstract` | 同比 <0→0~20;0–25→20–60;25–100→60–95;>100→100。剔除一次性收益注水 |
| **A** 年度盈利 | 0.15 | `stock_financial_abstract` + `stock_financial_analysis_indicator` | 近 3 年复合增速 + ROE;复合 ≥25% & ROE ≥17% → 90+ |
| **N** 新高/催化 | 0.15 | `stock_zh_a_spot` + 政策标记 | 距 52 周高 ≤3% → 高;命中政策催化 → 加成 |
| **S** 量价供需 | 0.10 | `stock_zh_a_spot_em` | 量比 1.5–3 & 换手 2–10% & 流通市值 <500 亿 → 优 |
| **L** 领涨强度 | 0.20 | spot 自算阶段涨幅(替代 IBD RS Rating) | 近 6 月涨幅在全市场百分位,前 10% → 100 |
| **I** 机构资金 | 0.10 | `stock_individual_fund_flow` + 十大股东 | 主力 5 日净流入 >0 & 机构持股比例高 → 高 |
| **M** 大盘方向 | 0.10 | `stock_zh_index_daily` | 进攻=100 / 观望=50 / 防守=0 |

**合成**:`灯塔分 = Σ(子分 × 权重)`;当 **M = 防守** 时整体 `× 0.6`(总开关压制,符合"大盘是总开关")。

### 4.2 排除池(不进选股)
ST / *ST、退市预警、上市 <6 月(次新)、停牌、流通市值 <10 亿或 >3000 亿(可配)、北交所默认排除(可开关)、当季亏损且无扭亏迹象。

### 4.3 输出形态(重度)
1. **全市场打分排行榜**:~5000 只按灯塔分排序,分页,可按单要素子分排序筛选。
2. **TOP20 候选**:灯塔分 ≥80 或排名前 20,标注"符合买点特征"。
3. **每只体检卡**:七要素雷达 + 子分明细 + 近 6 月价格趋势 SVG(叠加沪深 300)+ 政策催化徽章。

---

## 5. 政策 × 个股咬合(点睛)

新闻联播每日提取的板块/公司信号 → 自动映射到个股 **N 要素**:

- **板块命中**:关键词(如"半导体""新能源")→ 映射申万行业 → 该行业所有股票 N 加分 + 标 `🚩政策催化` 徽章(附来源日期)。
- **公司点名**:新闻联播直接提及公司名 → 点亮该股 N。
- **选股页呈现**:每个候选显示 `催化来源:新闻联播 06-19「半导体」`,宏观政策直接点亮个股。

实现:复用现有 `extract_keywords.py` + `economic_dict.yaml`,新增 `stocks/policy_link.py` 做关键词→行业→个股映射。

---

## 6. 命中回看(自我验证闭环)

灯塔区别于普通选股站的灵魂——**用结果证明方法论有效**:

- **每日快照**:存档当日 TOP20(代码、灯塔分、各子分、入选日期)。
- **跟踪计算**:次日(T+1)、T+5、T+20 收盘后,算这些票**相对沪深 300 的超额收益**。
- **累计指标**:
  - 胜率 = 跑赢沪深 300 的比例
  - 平均超额收益
  - TOP20 等权组合的累计净值曲线(对比沪深 300)
- **页面呈现**:昨日 TOP 今日表现、近 30 日胜率曲线、累计净值曲线。

---

## 7. 更新节奏与 CI

两套独立 GitHub Actions workflow,互不阻塞:

| Workflow | 触发(cron,UTC) | 北京时间 | 内容 |
|---|---|---|---|
| `scrape.yml`(宏观) | `45 13 * * *` | 21:45 | 新闻联播 + 宏观四板块 + LLM 灯塔信号 → 内容 push → Pages 部署 |
| `stocks.yml`(个股) | `0 10 * * 1-5` + 交易日历过滤 | 18:00 | akshare 全市场打分 + TOP20 + 政策咬合 + 回看更新 → 内容 push → 部署 |

- 个股 workflow 用 akshare 交易日历(`tool_trade_date_hist_sina`)过滤节假日,非交易日 skip。
- 收盘 15:00 后定 18:00,留时间等尾盘资金流/龙虎榜落地。
- 部署:各 workflow 末尾接 Pages 部署,或独立 `deploy.yml`(任一 push 触发)。

---

## 8. 域名迁移(lighthouse 新仓库,弃旧)

**决策**:新建仓库 `ming-h/lighthouse`,部署到 `https://ming-h.github.io/lighthouse/`;旧 `xwlb-daily` 不再部署(保留作存档)。**彻底不沾旧地址。**

迁移清单:
1. 新建仓库 `lighthouse`,推送现有代码 + `data/` 历史数据。
2. `site/hugo.toml`:`baseURL = "https://ming-h.github.io/lighthouse/"`,`canonifyURLs = true`(保持),菜单 URL 无前导斜杠(保持)。
3. 新仓库 Settings → Pages → Source = GitHub Actions。
4. `.github/workflows/deploy.yml` 在新仓库运行(`pages: write` / `id-token: write`)。
5. 品牌全改:站名「灯塔 Lighthouse」、副标题、`favicon.svg`/logo 换灯塔图标、og 信息。
6. 旧 `xwlb-daily`:停止 Actions 部署(可选保留只读存档)。

---

## 9. 技术栈与目录结构

**数据**:akshare(CI 主源,免费无 key)、Anthropic SDK → GLM-5.2(`https://open.bigmodel.cn/api/anthropic`,叙述)、问财(本地 Claude Code 深度体检,不进 CI)
**站点**:Hugo + PaperMod(保留)
**图表**:`charts.py` 纯 SVG(保留)+ 新增个股趋势 SVG、命中率净值曲线

新增目录结构:
```
scraper/
  run_daily.py            # 宏观管道(扩展现有)
  fetch_xwlb.py llm_brief.py build_content.py charts.py extract_keywords.py  # 现有保留
  macro/
    liquidity.py          # 央行/流动性
    rates_fx.py           # 利率汇率外资
    business.py           # 景气价格
    sentiment.py          # 情绪异动
    big_picture.py        # 聚合 → 灯塔信号(M)
  stocks/
    engine.py             # akshare 全市场取数 + 打分主流程
    score.py              # 七要素子分公式(纯函数,可单测)
    policy_link.py        # 新闻联播 → 个股 N 咬合
    hit_rate.py           # 历史候选回看
    snapshot.py           # 每日 TOP20 快照存储
site/
  content/  market-view/ daily-picks/ checkup/ hit-rate/   # 新增 + 现有保留
  layouts/  market-view.html daily-picks.html checkup.html hit-rate.html
```

---

## 10. 风险与降级

| 风险 | 降级 |
|---|---|
| akshare 接口变动/限流 | 重试 + 缓存 + 失败跳过该要素(标注缺口,不打满分) |
| GLM 限流/失败 | AI 解读降级为规则模板(指数均线+资金符号组合) |
| C/I 数据字段缺失 | 用替代指标(净利代 EPS、主力资金代机构明细),注明 |
| 全市场扫描超时 | 分批/增量 + 缓存财务数据(季频更新) |
| 数据准确性 | 全程标注来源;非投资建议,不给买卖点承诺 |

---

## 11. 路线图(分阶段实施)

- **P0** 域名迁移 + 品牌改名(lighthouse)
- **P1** 个股打分引擎:akshare 取数 + 七要素子分 + 灯塔分 + TOP20 + 全市场排行页
- **P2** 命中回看:每日快照 + T+1/T+5/T+20 跟踪 + 胜率/净值页
- **P3** 宏观四板块 + LLM 灯塔信号(M)
- **P4** 政策 × 个股咬合(新闻联播 → N 徽章)
- **P5** 个股体检在线页 + 趋势 SVG
- **P6** UI/导航/品牌视觉打磨

---

## 附:与 IBD 的差异声明

- IBD 的 RS/EPS/Composite Rating 是**专有付费评分**,灯塔用 akshare 可得指标的**公开替代**(阶段涨幅百分位代 RS Rating)。
- 灯塔的"命中回看"是 IBD 没有的**独创自我验证模块**。
- 全程不荐股、不给买卖点;输出框架、信号与体检,使用者自负盈亏。

---
title: "个股体检"
date: 2026-06-19
description: "输入代码 → CAN SLIM 七要素深度体检"
aliases: ["/checkup/"]
---

> 🚧 **在线体检页开发中（P5 阶段）**。完成后输入任意 A 股代码即可实时跑七要素体检。下方为单股体检预览。

## 体检示例 · 贵州茅台（600519）

<div class="score-ring" style="width:96px;height:96px">
  <svg width="96" height="96" viewBox="0 0 96 96">
    <circle class="sr-track" cx="48" cy="48" r="42" stroke-width="7"/>
    <circle class="sr-prog" cx="48" cy="48" r="42" stroke-width="7" stroke-dasharray="263.9" stroke-dashoffset="71"/>
  </svg>
  <span class="sr-num">73</span>
</div>

<div class="radar-card">
  <svg class="radar" viewBox="0 0 260 240">
    <polygon class="r-axis" points="130,30 217,93 184,197 76,197 43,93"/>
    <polygon class="r-axis" points="130,60 191,105 168,176 92,176 69,105"/>
    <polygon class="r-fill" points="130,42 200,100 175,185 90,180 60,100"/>
    <text class="r-label" x="130" y="22" text-anchor="middle">C 收益</text>
    <text class="r-label" x="225" y="95" text-anchor="middle">A 年度</text>
    <text class="r-label" x="195" y="215" text-anchor="middle">N 催化</text>
    <text class="r-label" x="65" y="215" text-anchor="middle">S 供需</text>
    <text class="r-label" x="35" y="95" text-anchor="middle">L 强度</text>
  </svg>
</div>

<div class="factor-row"><span class="f-letter">C</span><span class="f-name">当季收益<div class="factor-track"><div class="f-fill" style="width:75%"></div></div></span><span class="f-val">同比 +16%</span></div>
<div class="factor-row"><span class="f-letter">A</span><span class="f-name">年度收益<div class="factor-track"><div class="f-fill" style="width:85%"></div></div></span><span class="f-val">ROE 30%</span></div>
<div class="factor-row"><span class="f-letter">N</span><span class="f-name">新催化<div class="factor-track"><div class="f-fill" style="width:70%"></div></div></span><span class="f-val">—</span></div>
<div class="factor-row"><span class="f-letter">L</span><span class="f-name">领涨强度<div class="factor-track"><div class="f-fill" style="width:62%"></div></div></span><span class="f-val">前 35%</span></div>

> 雷达图 + 七要素条 + 趋势 SVG 将由 akshare 实时取数生成。

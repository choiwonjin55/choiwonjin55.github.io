---
title: TidyTuesday #01 - 노르웨이 연어류 폐사 데이터에서 본 종별 사망률 패턴
date: 2026-03-19
description: 2026-03-17 TidyTuesday의 Salmonid Mortality Data로 먼저 EDA를 하고, 국가 단위 월별 사망률 패턴을 비교한 첫 연습 기록.
slug: tidytuesday-01-salmonid-mortality
category: 데이터분석
tags: TidyTuesday, Python, pandas, matplotlib, 시각화
format: html
---
<h2>Dataset</h2>
<ul>
  <li>출처: TidyTuesday, Norwegian Veterinary Institute, Laksetap app/API</li>
  <li>기간: 2020-01 ~ 2025-12</li>
  <li>주제: 노르웨이 양식 연어류의 월별 사망률과 <code>losses</code></li>
  <li><code>losses</code> = <code>dead + discarded + escaped + other</code></li>
  <li><code>median</code>은 같은 월·지역 안에서 양식장별 월별 사망률의 중앙값이고, <code>q1</code>과 <code>q3</code>는 그 분포의 사분위수다.</li>
  <li><strong>monthly_mortality_data.csv</strong>: <code>date</code>, <code>species</code>, <code>geo_group</code>, <code>region</code>, <code>median</code>, <code>q1</code>, <code>q3</code></li>
  <li><strong>monthly_losses_data.csv</strong>: <code>date</code>, <code>species</code>, <code>geo_group</code>, <code>region</code>, <code>losses</code>, <code>dead</code>, <code>discarded</code>, <code>escaped</code>, <code>other</code></li>
</ul>

<h2>EDA</h2>
<ul>
  <li>전체 <code>losses</code>는 <code>salmon</code>이 압도적이다. 총 <code>losses</code>는 약 1,187,800,395건이고 <code>rainbowtrout</code>는 약 58,317,426건이다. 같은 글 안에서 절대 규모와 비율을 같이 봐야 하는 이유가 여기서 나온다.</li>
  <li><code>losses</code> 구성은 두 종 모두 비슷하지만 완전히 같지는 않다. <code>dead</code>가 각각 약 85.5%, 84.0%로 가장 크고, <code>discarded</code>는 <code>salmon</code> 4.7%, <code>rainbowtrout</code> 6.7% 수준이다. 그래서 "죽은 개체 수"만 보면 <code>losses</code> 구조의 일부를 놓친다.</li>
  <li>국가 단위 월별 사망률 중앙값은 종별 계절성이 다르다. <code>rainbowtrout</code>는 여름 평균이 <code>0.712</code>, 가을 평균이 <code>0.798</code>로 올라가고 <code>9월</code> 평균 중앙값이 <code>0.962</code>로 가장 높다.</li>
  <li>반대로 <code>salmon</code>은 겨울 평균 <code>0.663</code>, 봄 평균 <code>0.654</code>가 높고 여름 평균은 <code>0.428</code>까지 내려간다. 월별 peak는 <code>3월 (0.732)</code>이고 저점은 <code>7월 (0.393)</code>이다.</li>
  <li><code>losses</code>의 계절성은 사망률과 완전히 같지 않다. 국가 단위 평균 <code>losses</code>는 두 종 모두 가을에 가장 크고, 월별 평균 기준 peak는 둘 다 <code>9월</code>이다. 즉 총량의 피크와 사망률의 피크를 같은 의미로 읽으면 안 된다.</li>
  <li>연도별 국가 <code>losses</code>도 다르게 움직인다. <code>salmon</code>은 2020년 약 60.3M에서 2023년 약 71.4M까지 늘었다가 2025년 약 67.5M으로 내려왔고, <code>rainbowtrout</code>는 2020년 약 3.4M에서 2025년 약 3.7M 정도로 비교적 완만하다.</li>
  <li>지역 평균도 차이가 크다. county 평균 월별 사망률 중앙값은 <code>Nordland</code>가 약 0.427로 낮고, <code>Vestland</code>는 약 0.796으로 높다. 거의 2배 차이라 지역 비교 차트가 충분히 의미 있다.</li>
</ul>

<h2>Question</h2>
<p>전체 <code>losses</code> 규모는 <code>salmon</code>이 훨씬 큰데, 왜 국가 단위 월별 사망률 중앙값의 피크는 <code>rainbowtrout</code>에서 더 또렷하게 보일까. 같은 나라, 같은 월 단위 데이터인데도 두 종의 계절 패턴이 다르게 보여서, 첫 차트는 국가 단위에서 두 종의 월별 사망률 중앙값과 변동 범위를 나란히 비교하는 데 집중했다.</p>

<h2>Approach</h2>
<ul>
  <li>우선 <code>geo_group == "country"</code>만 남겨 국가 단위 패턴에 집중했다.</li>
  <li><code>median</code>을 중심선으로 그리고 <code>q1</code>~<code>q3</code>의 범위를 감싸서 월별 변동폭까지 함께 보이게 했다.</li>
  <li>종별 차이를 한눈에 읽을 수 있게 <code>salmon</code>과 <code>rainbowtrout</code>를 두 개의 패널로 나눴다.</li>
</ul>

<h2>Visualization</h2>
<figure style="margin: 0 0 1.25rem;">
  <img
    src="./assets/tidytuesday/2026-03-17-salmonid-mortality-data/chart-01-country-mortality-trend.png"
    alt="Norway country-level monthly median mortality values for salmon and rainbowtrout"
    style="width: 100%; height: auto; border-radius: 16px; display: block;"
  />
  <figcaption style="margin-top: 0.65rem; color: #5a6b7c;">
    국가 단위 월별 사망률 중앙값과 사분위 범위. <code>rainbowtrout</code>는 여름 후반에, <code>salmon</code>은 겨울~초봄에 상대적으로 높은 구간이 보인다.
  </figcaption>
</figure>

<div style="margin: 0 0 1.25rem;">
  <div style="font-weight: 700; margin-bottom: 0.55rem;">종별 계절별 사망률 요약</div>
  <div style="overflow-x: auto;">
    <table style="width: 100%; max-width: 780px; border-collapse: collapse; font-size: 0.95rem;">
      <thead>
        <tr style="background: #f5f7fa; text-align: left;">
          <th style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #d7dee5;">species</th>
          <th style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #d7dee5;">겨울</th>
          <th style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #d7dee5;">봄</th>
          <th style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #d7dee5;">여름</th>
          <th style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #d7dee5;">가을</th>
          <th style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #d7dee5;">최고 월</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2; text-align: left;">salmon</th>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">0.663</td>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">0.654</td>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">0.428</td>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">0.529</td>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">3월 (0.732)</td>
        </tr>
        <tr>
          <th style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2; text-align: left;">rainbowtrout</th>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">0.630</td>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">0.575</td>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">0.712</td>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">0.798</td>
          <td style="padding: 0.65rem 0.8rem; border-bottom: 1px solid #e7edf2;">9월 (0.962)</td>
        </tr>
      </tbody>
    </table>
  </div>
  <p style="margin-top: 0.65rem; color: #5a6b7c;">
    각 숫자는 그 계절에 포함된 월들의 <code>월별 사망률 중앙값</code> 평균이다. 표만 봐도 <code>salmon</code>은 겨울·봄, <code>rainbowtrout</code>는 여름·가을에 상대적으로 높다는 점을 확인할 수 있다.
  </p>
</div>

<figure style="margin: 0 0 1.25rem;">
  <img
    src="./assets/tidytuesday/2026-03-17-salmonid-mortality-data/chart-02-country-loss-composition.png"
    alt="Country-level annual composition of salmonid losses by species"
    style="width: 100%; height: auto; border-radius: 16px; display: block;"
  />
  <figcaption style="margin-top: 0.65rem; color: #5a6b7c;">
    국가 단위 연간 <code>losses</code> 구성 비율. <code>losses = dead + discarded + escaped + other</code>로 집계되며, 두 종 모두 <code>dead</code>가 가장 크지만 <code>other</code>와 <code>discarded</code>도 계속 일정 비중을 차지한다.
  </figcaption>
</figure>

<h2>Insight</h2>
<ul>
  <li>두 종의 계절 패턴은 비슷하지 않다. <code>rainbowtrout</code>의 월별 사망률 중앙값 peak는 <code>9월 0.962</code>이고, <code>salmon</code>의 peak는 <code>3월 0.732</code>이다. 같은 연어류라도 위험 시기를 하나로 묶어 보기 어렵다.</li>
  <li>계절성의 강도도 차이가 난다. <code>rainbowtrout</code>는 <code>5월 0.500</code>에서 <code>9월 0.962</code>까지 <code>0.462</code>포인트 움직이고, <code>salmon</code>은 <code>7월 0.393</code>에서 <code>3월 0.732</code>까지 <code>0.338</code>포인트 움직인다. 이 기준에서는 <code>rainbowtrout</code> 쪽이 더 뚜렷한 계절성을 보인다.</li>
  <li><code>losses</code> 구성은 두 종 모두 <code>dead</code> 중심이지만 세부 비중은 조금 다르다. <code>discarded</code> 비중은 <code>rainbowtrout 6.72%</code>, <code>salmon 4.72%</code>이고, <code>escaped</code>는 두 종 모두 <code>0.1%</code> 안팎이다. 국가 단위에서는 <code>rainbowtrout</code> 쪽이 상대적으로 더 복합적인 <code>losses</code> 구성을 가진다.</li>
</ul>

<h2>Code</h2>
<pre><code>import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("monthly_mortality_data.csv", parse_dates=["date"])
country = df[df["geo_group"] == "country"].copy()

for species in ["salmon", "rainbowtrout"]:
    subset = country[country["species"] == species].sort_values("date")
    ax.fill_between(subset["date"], subset["q1"], subset["q3"], alpha=0.18)
    ax.plot(subset["date"], subset["median"], linewidth=2.4, label=species)
</code></pre>
<p>실행 가능한 전체 코드: <code>data/tidytuesday/2026/2026-03-17-salmonid-mortality-data/viz/code/01_country_mortality_trend.py</code></p>

<p><code>losses</code> 구성 비율 차트 코드: <code>data/tidytuesday/2026/2026-03-17-salmonid-mortality-data/viz/code/02_country_loss_composition.py</code></p>

<h2>Reproducibility</h2>
<ul>
  <li>Week: <code>2026-03-17</code></li>
  <li>Source: TidyTuesday, Norwegian Veterinary Institute</li>
  <li>Local workspace: <code>data/tidytuesday/2026/2026-03-17-salmonid-mortality-data/</code></li>
  <li>EDA note: <code>data/tidytuesday/2026/2026-03-17-salmonid-mortality-data/viz/notes/eda.md</code></li>
  <li>Next charts: 지역별 mortality 비교</li>
</ul>

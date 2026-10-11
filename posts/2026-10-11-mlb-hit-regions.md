---
title: 타구 속도와 각도로 보는 안타와 홈런
date: 2026-10-11
description: 2026 MLB 타구 속도와 발사각에 따른 안타·홈런 결과와 무라카미의 타구 분석
slug: mlb-2026-hit-regions
category: 데이터분석
tags: MLB, Statcast, 데이터분석, 시각화
format: html
---

<p>야구에서 타구 속도와 발사각이 중요하다는 이야기를 자주 접했다. 실제로 두 조건에 따라 비거리와 안타·홈런 확률이 어떻게 달라지는지 궁금해 2026년 MLB 데이터를 살펴봤다.</p>

<h2 id="전체-타구의-안타와-홈런">전체 타구의 안타와 홈런</h2>

<table><thead><tr><th>타구 결과</th><th>타구 수</th><th>전체 타구 중 비중</th></tr></thead><tbody><tr><td>아웃</td><td>83,271</td><td>68.0%</td></tr><tr><td>홈런 제외 안타</td><td>33,699</td><td>27.5%</td></tr><tr><td>홈런</td><td>5,570</td><td>4.5%</td></tr></tbody></table>

<iframe src="../scripts/statcast-dashboard.html" title="타구 속도와 발사각에 따른 비거리·홈런·안타 확률" loading="lazy" style="width:100%;height:1600px;border:0;border-radius:14px;"></iframe>

<figure><img src="../assets/mlb-2026/01-response-maps.png" alt="타구 속도와 발사각에 따른 모델 예측 비거리·홈런·안타 확률 · 정적 그림" loading="lazy"></figure>

<p>타구 속도가 높아질수록 예상 비거리가 길어지는 모습은 비교적 분명했다. 반면 안타 확률은 속도만으로 설명되지 않았다. 약한 타구에서도 안타 확률이 높은 조합이 있었고, 어느 정도 빠르게 날아간 타구에서도 안타 확률이 낮은 조합이 있었다.</p>

<h2 id="안타가-모이는-두-영역">안타가 모이는 두 영역</h2>

<p>안타 확률을 홈런 제외 안타와 홈런으로 나누면 두 영역의 차이가 더 잘 보인다.</p>

<figure><img src="../assets/mlb-2026/hit-decomposition.png" alt="모델 예측과 실제 관측의 안타·홈런 제외 안타·홈런 구성" loading="lazy"></figure>

<p>홈런 제외 안타 그래프에는 약하게 띄운 타구와 빠르고 낮게 보낸 타구가 곡선 형태로 이어진다. 강하게 띄운 타구 쪽의 높은 안타 확률은 홈런 그래프에서 두드러진다.</p>

<table><thead><tr><th>비교 구간</th><th>속도 / 발사각</th><th>타구 수</th><th>안타율</th><th>홈런 제외 안타율</th><th>홈런율</th></tr></thead><tbody><tr><td>약하게 띄운 타구</td><td>65~75 mph / 20~35°</td><td>1,700</td><td>83.4%</td><td><strong>83.3%</strong></td><td>0.1%</td></tr><tr><td>빠르고 낮은 타구</td><td>90~105 mph / 5~15°</td><td>9,276</td><td>74.5%</td><td><strong>74.5%</strong></td><td>0.0%</td></tr><tr><td>강하게 띄운 타구</td><td>105~115 mph / 25~35°</td><td>1,429</td><td>95.0%</td><td>3.4%</td><td><strong>91.7%</strong></td></tr><tr><td>중간 속도의 뜬공</td><td>85~100 mph / 25~35°</td><td>7,341</td><td><strong>17.9%</strong></td><td>8.8%</td><td>9.1%</td></tr></tbody></table>

<figure><img src="../assets/mlb-2026/region-outcomes.png" alt="대표 영역의 실제 단타·2루타·3루타·홈런·아웃 구성" loading="lazy"></figure>

<h2 id="두-영역-사이의-중간-속도-뜬공">두 영역 사이의 중간 속도 뜬공</h2>

<p>중간 속도의 뜬공에서는 7,341타구 중 6,009개에서 아웃이 기록됐다. 약하게 띄운 타구보다 멀리 날아갔지만, 안타율은 약하게 띄운 타구와 강하게 띄운 타구 모두보다 낮았다.</p>

<table><thead><tr><th>비교 구간</th><th>타구 속도</th><th>발사각</th><th>타구 수</th><th>안타 수·홈런 포함</th><th>안타율</th></tr></thead><tbody><tr><td>약하게 띄운 타구</td><td>65~75 mph</td><td>20~35°</td><td>1,700</td><td>1,417</td><td><strong>83.4%</strong></td></tr><tr><td>중간 속도의 뜬공</td><td>85~100 mph</td><td>25~35°</td><td>7,341</td><td>1,317</td><td><strong>17.9%</strong></td></tr><tr><td>강하게 띄운 타구</td><td>105~115 mph</td><td>25~35°</td><td>1,429</td><td>1,358</td><td><strong>95.0%</strong></td></tr></tbody></table>

<p>중간 속도로 띄운 공은 약한 타구보다 멀리 가지만, 강한 타구처럼 담장을 넘기기는 어렵다. 하지만 외야수가 도달할 수 있는 반경에 공이 날아가고, 날아가는 동안 이동할 시간도 더 주기 때문에 잡기 쉬운 타구가 되는 것으로 보인다.</p>

<p>속도뿐 아니라 각도의 차이도 살펴봤다. 같은 100 mph 타구에서도 발사각에 따라 결과가 달랐다.</p>

<table><thead><tr><th>100 mph에서의 발사각</th><th>예상 비거리</th><th>기대 홈런 확률</th><th>기대 안타 확률</th></tr></thead><tbody><tr><td>10°</td><td>58.3 m</td><td>0.0%</td><td><strong>76.8%</strong></td></tr><tr><td>30°</td><td><strong>117.1 m</strong></td><td><strong>41.7%</strong></td><td>51.6%</td></tr><tr><td>45°</td><td>97.1 m</td><td>2.2%</td><td><strong>3.8%</strong></td></tr></tbody></table>

<h2 id="무라카미의-타구-속도발사각과-홈런">무라카미의 타구 속도·발사각과 홈런</h2>

<p>이번 시즌 무라카미는 볼넷으로 걸어나가거나, 강하게 때려 홈런을 만드는 것을 목표로 하는 타자처럼 보였다. 그의 타구가 리그 전체의 속도·각도 분포에서 어디에 놓이는지, 홈런은 어떤 조합에서 나왔는지 살펴봤다.</p>

<p>역시 무라카미는 약하게 띄워 안타를 만드는 쪽보다 강한 타구를 만드는 쪽에 가까웠다.</p>

<iframe src="../scripts/murakami-dot-plot.html" title="무라카미의 타구 속도·발사각과 실제 결과" loading="lazy" style="width:100%;height:1050px;border:0;border-radius:14px;"></iframe>

<table><thead><tr><th>타구 구분</th><th>타구 수</th><th>평균 타구 속도</th><th>평균 발사각</th></tr></thead><tbody><tr><td>전체 타구</td><td>257</td><td>93.9 mph</td><td>15.6°</td></tr><tr><td>안타 전체</td><td>94</td><td>101.3 mph</td><td>19.1°</td></tr><tr><td>홈런 제외 안타</td><td>59</td><td><strong>98.0 mph</strong></td><td><strong>10.7°</strong></td></tr><tr><td>홈런</td><td>35</td><td><strong>106.8 mph</strong></td><td><strong>33.3°</strong></td></tr></tbody></table>

<p>홈런 제외 안타도 평균 속도가 높은 타구였지만, 홈런보다 낮은 각도로 날아갔다. 홈런 타구는 더 빠르고 높게 날아갔다.</p>

<h3 id="리그-전체와의-비교">리그 전체와의 비교</h3>

<p>리그 전체와 무라카미를 같은 타구 결과별로 비교했다.</p>

<table><thead><tr><th>타구 구분</th><th>리그 평균 속도</th><th>무라카미 평균 속도</th><th>리그 평균 발사각</th><th>무라카미 평균 발사각</th></tr></thead><tbody><tr><td>전체 타구</td><td>88.7 mph</td><td><strong>93.9 mph</strong></td><td>13.9°</td><td>15.6°</td></tr><tr><td>안타 전체</td><td>93.9 mph</td><td><strong>101.3 mph</strong></td><td>12.0°</td><td>19.1°</td></tr><tr><td>홈런 제외 안타</td><td>92.2 mph</td><td><strong>98.0 mph</strong></td><td>9.2°</td><td>10.7°</td></tr><tr><td>홈런</td><td>104.0 mph</td><td><strong>106.8 mph</strong></td><td>29.1°</td><td><strong>33.3°</strong></td></tr></tbody></table>

<p>무라카미는 홈런뿐 아니라 홈런 제외 안타에서도 리그 평균보다 타구 속도가 높았다. 따라서 약하게 쳐서 안타를 만드는 쪽보다 강하게 때려 홈런을 노리는 타자에 가까웠다.</p>

<h2 id="시즌-초와-마지막-날의-타구-변화">시즌 초와 마지막 날의 타구 변화</h2>

<p>정규시즌 초인 3월 26일과 정규시즌 마지막 날인 9월 27일의 타구를 따로 남겨두고, 속도·발사각과 안타·홈런 결과를 비교했다. 시즌 초와 마지막 날의 타구 경향이 달라졌는지 확인하였다.</p>

<table><thead><tr><th>항목</th><th>3월 26일</th><th>9월 27일</th></tr></thead><tbody><tr><td>경기 / 타구 수</td><td>11경기 / 542타구</td><td>14경기 / 704타구</td></tr><tr><td>평균 타구 속도</td><td><strong>89.7 mph</strong></td><td><strong>88.7 mph</strong></td></tr><tr><td>평균 발사각</td><td><strong>13.2°</strong></td><td><strong>15.3°</strong></td></tr><tr><td>95 mph 이상 타구 비중</td><td>41.9%</td><td>39.2%</td></tr><tr><td>실제 안타율 · 타구 기준</td><td>35.1%</td><td>31.0%</td></tr><tr><td>평균 예측 안타 확률</td><td>33.2%</td><td>31.2%</td></tr><tr><td>실제 홈런율 · 타구 기준</td><td>5.7%</td><td>5.3%</td></tr><tr><td>평균 예측 홈런 확률</td><td>5.6%</td><td>4.9%</td></tr></tbody></table>

<p>마지막 날에는 타구 속도와 강한 타구의 비중이 낮아지고, 발사각은 높아졌다. 안타율은 낮아졌지만 홈런율의 차이는 작았다. 두 날짜 사이에서는 공을 더 높이 띄우는 모습과 함께 안타가 줄어드는 변화가 나타났다. (하루 데이터라서 조금 더 구간을 넓게 보는 것도 필요할 수 있음)</p>

<h2 id="마무리">마무리</h2>

<p>타구 속도가 빠르면 좋은 결과가 나올 것이라 생각했지만, 안타는 속도와 각도의 조합에 따라 달라졌다. 약하게 띄운 공과 빠르고 낮게 보낸 공은 주로 단타로, 강하게 띄운 공은 홈런으로 이어졌다. 얼마나 세게 치느냐만큼 어떤 각도로 보내느냐도 중요했다.</p>

<h3 id="분석-데이터-출처">분석 데이터 출처</h3>

<p>타구 데이터는 <a href="https://baseballsavant.mlb.com/statcast_search">Baseball Savant의 Statcast Search</a>에서, 무라카미의 시즌 기록은 <a href="https://statsapi.mlb.com/api/v1/people/808959/stats?stats=season&amp;group=hitting&amp;season=2026&amp;gameType=R">MLB 공식 기록</a>에서 가져왔다.</p>

<script>
window.addEventListener('message',event=>{
 const frame=document.querySelector('iframe[src*="statcast-dashboard.html"]');
 const value=event.data;
 if(frame&&event.source===frame.contentWindow&&value&&value.type==='mlb-statcast-height'
    &&Number.isFinite(value.height)&&value.height>=200&&value.height<=5000){
  frame.style.height=value.height+'px';
 }
});
</script>

# MLB 득점권 타격 분석 재현

2025·2026년 정규시즌을 이용해 득점권에서 평소보다 더 잘 치는 성적이 다음 해에도 이어지는지 확인한다. 본문 초안은 `drafts/2026-10-23-mlb-clutch.md`, 선수 선택 그래프는 `scripts/mlb-clutch-dashboard.html`이다. 블로그 생성·커밋·푸시는 이 작업에 포함하지 않는다.

## 실행

프로젝트 루트에서 Python 3.12 이상과 독립 가상환경을 사용한다. 기존 환경에 필요한 패키지가 있다면 재설치할 필요가 없다.

```powershell
python -m venv data/mlb/clutch-2026/.venv
data/mlb/clutch-2026/.venv/Scripts/python.exe -m pip install -r scripts/requirements-mlb-clutch.txt
python -X utf8 scripts/mlb_clutch_collect.py collect
python -X utf8 scripts/mlb_clutch_collect.py audit
data/mlb/clutch-2026/.venv/Scripts/python.exe -X utf8 scripts/mlb_clutch_analysis.py
data/mlb/clutch-2026/.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_mlb_clutch.py
python -X utf8 scripts/check_mlb_clutch_dashboard.py
```

수집에만 네트워크가 필요하다. `collect`는 원본과 메타데이터가 있으면 URL·SHA-256을 확인하고 재사용한다. 공식 기록이 수정된 새 스냅샷을 받으려면 기존 폴더를 별도로 보관하고 `collect --refresh`를 명시적으로 실행한다. `audit`와 분석은 오프라인으로 실행한다. Windows 그래프는 맑은 고딕과 DejaVu Sans를 사용한다. 다른 OS에서는 해당 글꼴을 설치하거나 한국어 글꼴로 변경한다.

## 자료와 감사

- MLB Stats API의 `stats=season` 전체 기록과 `stats=statSplits&sitCodes=risp` 득점권 기록. `sportIds=1`, `gameType=R`, `playerPool=ALL`, `limit=10000`을 명시한다. API가 반환한 `totalSplits`와 실제 행 수, 선수 ID 중복, 정수·음수·안타≤타수를 검사한다.
- 같은 시즌 30개 팀 합계와 선수 합계를 전체·득점권 각각 대조한다. H, AB, PA, K, BB, HBP, SF, SH, 타격방해 수가 모두 일치해야 한다. 각 시즌 타수가 가장 많은 이적 선수 3명은 개인 API의 팀 합산 행으로 재검증한다. 합산 행과 팀별 행을 함께 더하지 않는다.
- 공식 일정의 완료 경기로 날짜 범위·고유 경기 수를 확인한다. 중단 후 재개된 경기는 일정에 중복 기재될 수 있으므로 gamePk를 구분한다. 연도별 원본 URL·조회 시각·응답 바이트·해시를 보관한다.
- 타수에는 삼진·안타 번트·실책 출루가 포함된다. 볼넷·사구·희생타·타격방해는 공식 타수에서 제외된다. 기존 인플레이 타구의 EV/LA 결측 처리나 번트 제외 규칙을 가져오지 않는다.
- 득점권 행이 없는 선수는 2025년 100명, 2026년 100명이다. 원본과 inventory에는 남기고 0으로 대체하지 않는다. 이 중 300타수 이상인 선수는 양년 모두 0명이다. 존재하는 기록의 필수 수치 결측은 0건이다.
- 원본·감사·선수 CSV는 Git 제외 경로 `data/mlb/clutch-2026/`에 둔다. 공유 가능한 수치와 설정은 `assets/mlb-clutch-2026/results.json`, 코드와 문서는 Git 대상 경로에 둔다. 분석 결과에는 입력 파일과 실행 코드의 SHA-256 및 실제 패키지 버전을 남긴다.

## 고정한 분석 규칙

주 분석 기준은 연도별 전체 300타수·득점권 75타수 이상이다. 민감도 분석은 전체 300타수를 유지하고 득점권을 50·100타수로 바꾼다. 분포는 해당 연도 전체 적격 선수, 지속성은 양년 모두 적격인 공통 선수에 관한 것이다. 평균·상관은 선수별 동일 가중치다.

차이 D = H_R/n_R − H/N, 비교 지표 C = H_R/n_R − (H−H_R)/(N−n_R)다. D = (N−n_R)/N × C가 모든 행에서 성립해야 한다. 반올림된 공식 AVG 대신 H/AB로 계산한다.

우연 모형에서는 선수별 전체 H, 전체 N, 득점권 n_R를 고정한다. 득점권 안타 X는 Hypergeometric(N,H,n_R)에서 추출한다. 이는 선수별 안타를 상황과 독립적으로 무작위 배정하는 조건부 귀무모형이다. Var(X)=n_R×p×(1−p)×(N−n_R)/(N−1), p=H/N이며, D의 표준오차는 sqrt(Var(X))/n_R다. z=D/SE(D)로 표본 크기가 다른 선수들을 보조 비교한다.

분포 모의실험 20,000회로 평균·중심화한 표준편차·중심화한 |z|>1.96 선수 수를 비교한다. 표준편차는 평균을 빼는 통계량이지만, 이 귀무모형이 공통 득점권 효과를 따로 추정·보정한 모형은 아니다. 실제 득점권 평균 상승이 확인되므로 ‘자료 전체가 완전한 무작위’라고 해석하지 않는다. 점수·이닝·상대 투수·수비·선수별 공통 효과 이질성도 보정하지 않는다. 정규성 검정은 Shapiro–Wilk와 Q–Q plot을 이용하는 보조 진단이다.

지속성은 Pearson·Spearman 상관, 2026년 값을 선수 사이에서 섞는 20,000회 양측 순열 검정으로 확인한다. 신뢰구간은 선수 쌍을 함께 복원추출하는 percentile bootstrap 10,000회의 2.5·97.5 분위수다. Spearman은 각 복원표본 안에서 중복 관측을 포함해 다시 순위를 매긴다.

상·하위권은 공통 선수에서 2025년 지표 순서로 정하고 각각 floor(0.2×N)명이다. 동률은 player_id 순서로 처리하며 2026년 집단도 동일하게 정의한다. 집단 평균·평균 변화·2026년 상하위 평균 차이의 CI는 고정한 2025년 집단 내 선수 복원추출로 계산한다. 이 CI는 집단 선정의 불확실성을 포함하지 않는다. 2026년 상하위 평균 차이는 순열 검정도 병행한다.

잔류율의 귀무분포는 같은 크기 k의 두 집단이 무작위로 겹치는 Hypergeometric(N,k,k)이며 기대 잔류율은 k/N이다. 단측 p는 관측 이상 잔류할 확률이다. 신뢰구간으로 표시한 Wilson 구간은 기술적 근사이며, 검정은 정확한 초기하분포 확률을 사용한다. 무작위 잔류율 95% 구간은 20,000회 모의실험의 분위수다.

탐색적 잔류율 검정 12개(3개 타수 기준 × 2개 차이 지표 × 상하위)를 하나의 family로 묶어 Holm 보정한다. 다른 분포·상관 검정의 p는 개별 값으로 표시하며 전체 분석에서의 다중검정 보정값으로 주장하지 않는다. 난수 seed는 20261023을 기준으로 분석별 정해진 offset을 더한다. 정확한 설정은 결과 JSON에 있다.

## 해석 범위와 확인 결과

주 표본은 2026년 237명, 공통 선수 163명이다. 2025년 적격 선수 238명 가운데 75명은 2026년 기준에 미달한다. 2025년 전체 적격자에서 정한 상위 47명 중 36명, 하위 47명 중 29명이 2026년 기준을 충족한다. 본문 상하위 32명씩은 공통 표본 안에서 다시 정의한 집단이므로 이 47명 집단과 혼동하지 않는다.

주 지표 상관은 0.0047(bootstrap 95% CI −0.1470~0.1651), 일반 타율 상관은 0.3567(0.2199~0.4807)이다. 100타수 기준에서는 주 지표 상관이 0.1288로 높아지나 CI에 0이 포함된다. ‘효과가 정확히 0’이나 ‘클러치 능력의 부재’를 입증한 분석으로 표현하지 않는다. 표본이 줄어들면 확인 가능한 효과 크기도 제한된다.

보조 지표 하위권 잔류는 75타수 기준 11/32(p=0.0217), 100타수 기준 8/19(p=0.0104)였다. 100타수의 주 지표 하위권도 7/19(p=0.0417)다. 12개 검정 Holm 보정 후 각각 약 0.239·0.124·0.417이며, 이 예외도 본문에 포함한다. 원자료의 낮은 연도 간 상관·일부 집단 잔류·타수 제한에 따른 표본 감소를 함께 해석한다.

완료된 정규시즌의 타율 기록으로는 투수·수비·상황 선택의 인과적 효과를 분리할 수 없다. 일반 타율의 더 높은 상관도 표본 수와 측정 오차가 다르므로 클러치의 잠재 능력보다 타격 능력이 몇 배 크다는 비율 해석에는 사용하지 않는다.

## 검증

감사 스크립트의 합계·중복·이적·범위 검증, 모든 선수의 차이 항등식, 작은 표본의 완전 열거를 통한 우연모형 분산과 잔류확률 검증, SciPy와 상관 계산 대조, 원본 정수 기록과 공유 코호트 대조, 12개 p의 Holm 보정, 입력·코드 해시를 확인한다. 그래프는 데스크톱·좁은 화면에서 선수 선택·지표 변경·키보드 조작·이미지 로드·가로 넘침을 확인한다.

## 공식 자료와 방법 문서

- [MLB 상황 코드](https://statsapi.mlb.com/api/v1/situationCodes)
- [2026년 공식 득점권 기록](https://statsapi.mlb.com/api/v1/stats?stats=statSplits&group=hitting&season=2026&sitCodes=risp&sportIds=1&gameType=R&playerPool=ALL&limit=10000)
- [MLB 공식 타수 정의](https://www.mlb.com/glossary/standard-stats/at-bat)
- [SciPy hypergeometric distribution](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.hypergeom.html)
- [SciPy Shapiro–Wilk](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.shapiro.html)
- [SciPy Pearson correlation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.pearsonr.html)

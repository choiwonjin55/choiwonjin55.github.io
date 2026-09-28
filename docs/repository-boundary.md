# 저장소 구분

`blog-workspace` 아래에 공개 사이트 저장소 `homepage`와 비공개 분석 저장소 `analysis-private`를 나란히 둡니다. 두 저장소는 각각 독립된 Git 이력을 유지합니다.

| 공개 저장소 `homepage` | 비공개 저장소 `analysis-private` |
| --- | --- |
| 홈페이지와 블로그 화면 코드 | 원본·가공 데이터 |
| 공개할 글 `posts/*.md`와 생성된 `blog/*.html` | 분석 코드, 노트북, 작업 메모 |
| 공개를 승인한 이미지 `blog/assets/` | 초안과 검토 중인 차트 |

분석을 마친 뒤 공개할 글과 이미지만 `homepage`로 복사합니다. 공개 전에 `python build_blog.py`로 페이지를 만들고 `git diff`로 포함된 파일을 확인합니다. 공개 글에는 독자가 열 수 없는 비공개 로컬 경로를 링크하지 않습니다.

공개 저장소에서는 `data/`, `analysis/`, `notebooks/`를 Git에서 제외합니다. 이미 커밋한 파일은 제외 규칙을 추가해도 Git 기록에서 사라지지 않으므로 공개할 파일을 먼저 확인해야 합니다.

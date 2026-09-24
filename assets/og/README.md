# 공유 대표 이미지

| 파일 | 용도 |
| --- | --- |
| `home-ko-v1.png` | 한국어 홈페이지 |
| `home-en-v1.png` | 영어 홈페이지 |
| `blog-v1.png` | 블로그 목록과 별도 이미지가 없는 글 |

모든 이미지는 1200×630px PNG이다. 같은 이름의 SVG가 편집 가능한 원본이다.
버전 1은 macOS의 로컬 Chrome에서 SVG를 1200×630 CSS 픽셀, 기기 배율 1로 표시한 뒤 PNG로 내보냈다.
서체는 SVG에 지정한 Arial과 한글용 Apple SD Gothic Neo를 사용했다. 외부 웹폰트 다운로드는 필요 없다.
다른 OS에서는 Malgun Gothic 또는 시스템 sans-serif로 대체되므로 다시 내보낼 때 한글 모양과 줄 길이를 확인한다.

원본을 수정하면 PNG도 다시 내보내고 400×210px로 축소해 읽기 쉬운지 확인한다.
배포한 이미지를 변경할 때는 새 버전 파일명을 사용하고 `social_metadata.py`의 참조를 갱신한다.
이미지 alt도 실제 문구에 맞춰 함께 갱신한다.

홈페이지 공유 문구·주소·이미지는 `social_metadata.py`의 `HOME_PAGES`에서 관리한다.
아래 명령은 홈페이지의 공유 메타정보 블록과 블로그 생성 결과를 갱신한다.

```bash
python3 scripts/update_home_social_metadata.py
python3 build_blog.py
python3 scripts/check_social_metadata.py
```

글의 front matter에서는 다음 선택 필드로 기본값을 바꿀 수 있다.
기존 파서에 맞춰 문자열을 감싸는 따옴표 없이 한 줄로 작성한다.

```yaml
og_description: 링크를 공유할 때 보여줄 글의 짧은 요약입니다.
og_image: /assets/og/example-v1.png
og_image_alt: 예시 글의 제목과 핵심 질문을 담은 이미지
```

1차 지원 형식은 PNG이다. 지정한 파일은 사이트 안에 존재해야 하며, `og_image`를 지정하면 `og_image_alt`도 필요하다.
가로·세로 크기는 파일에서 읽으므로 별도 필드로 지정하지 않는다.
이미지를 지정하지 않으면 `blog-v1.png`를 사용한다.

실제 공유 미리보기는 공개 배포 후 확인한다. 로컬 검증만으로 외부 서비스의 표시나 캐시 갱신을 확인할 수는 없다.

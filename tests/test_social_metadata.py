import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_blog
from scripts.check_social_metadata import HeadMetadata
from social_metadata import (DEFAULT_IMAGE, SITE_URL, image_info, post_description,
                             post_image, site_url, summarize)


class SharingTests(unittest.TestCase):
    def test_description_precedence_and_prose_fallback(self):
        body = '<pre><code>secret_code()</code></pre><table><tr><td>table data</td></tr></table><p>첫 문단 &amp; 설명.</p><p>두 번째.</p>'
        self.assertEqual(post_description({'og_description': '공유용', 'description': '기존'}, body, '제목'), '공유용')
        self.assertEqual(post_description({'description': '기존'}, body, '제목'), '기존')
        self.assertEqual(post_description({}, body, '제목'), '첫 문단 & 설명.')
        self.assertIn('제목', post_description({}, '<pre>code</pre>', '제목'))

    def test_summary_strips_markup_and_limits_length(self):
        self.assertEqual(summarize('<p>한글 <b>강조</b> &amp; "인용"</p>'), '한글 강조 & "인용"')
        for value in ['아주 긴 설명입니다. ' * 40, 'word ' * 100, '가' * 200]:
            summary = summarize(value)
            self.assertLessEqual(len(summary), 160)
            self.assertTrue(summary.endswith('…'))

    def test_image_fallback_and_validation(self):
        self.assertEqual(post_image({})[0], DEFAULT_IMAGE)
        self.assertEqual(image_info(DEFAULT_IMAGE), ('image/png', 1200, 630))
        with self.assertRaises(ValueError):
            post_image({'og_image': DEFAULT_IMAGE})
        with self.assertRaises(FileNotFoundError):
            image_info('/assets/og/nonexistent.png')
        with self.assertRaises(ValueError):
            image_info('/assets/og/blog-v1.svg')

    def test_invalid_urls_fail(self):
        for path in ['https://example.com/a.png', '//example.com/a.png', 'relative.png',
                     '/assets/../private.png', '/assets/%2e%2e/private.png', '/x.png?q=1', '/x.png#top']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                site_url(path)

    def test_generated_article_preserves_overrides_and_escapes_attributes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'example.md'
            source.write_text('''---
title: 한글 "인용" & <비교>
date: 2026-09-24
slug: example
format: markdown
description: 기존 설명
og_description: 공유용 "설명" & 검증
og_image: /assets/og/home-ko-v1.png
og_image_alt: 카드 "설명" & 한글
---
본문은 그대로입니다.
''')
            with patch.object(build_blog, 'OUT_DIR', root):
                build_blog.build_post(source)
            output = (root / 'example.html').read_text()
            tags = HeadMetadata()
            tags.feed(output)
            self.assertEqual(tags.values['og:title'], ['한글 "인용" & <비교>'])
            self.assertEqual(tags.values['og:description'], ['공유용 "설명" & 검증'])
            self.assertEqual(tags.values['description'], ['기존 설명'])
            self.assertEqual(tags.values['og:image'], [SITE_URL + '/assets/og/home-ko-v1.png'])
            self.assertEqual(tags.values['og:image:alt'], ['카드 "설명" & 한글'])
            self.assertEqual(tags.values['article:published_time'], ['2026-09-24'])
            self.assertIn('<p>본문은 그대로입니다.</p>', output)


if __name__ == '__main__':
    unittest.main()

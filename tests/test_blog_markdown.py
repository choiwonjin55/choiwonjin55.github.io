import unittest

from build_blog import markdown_to_html


class MarkdownRenderingTests(unittest.TestCase):
    def test_analysis_table_preserves_bold_values(self):
        rendered = markdown_to_html('| Result | Count |\n| --- | ---: |\n| HR | **35** |')
        self.assertIn('<th>Result</th>', rendered)
        self.assertIn('<td><strong>35</strong></td>', rendered)
        self.assertEqual(rendered.count('<tr>'), 2)

    def test_image_and_interactive_graph_remain_loadable(self):
        frame = '<iframe src="../scripts/statcast-dashboard.html" title="Chart"></iframe>'
        rendered = markdown_to_html('![Observed](../assets/mlb-2026/region-outcomes.png)\n\n' + frame)
        self.assertIn('src="../assets/mlb-2026/region-outcomes.png"', rendered)
        self.assertIn(frame, rendered)
        self.assertIn("event.source===frame.contentWindow", rendered)

    def test_code_is_escaped_without_rendering_embeds(self):
        rendered = markdown_to_html('```html\n<iframe src="statcast-dashboard.html"></iframe>\n| a | b |\n| --- | --- |\n```')
        self.assertNotIn('<iframe ', rendered)
        self.assertNotIn('<table>', rendered)
        self.assertNotIn("window.addEventListener", rendered)
        self.assertIn('&lt;iframe', rendered)

    def test_existing_headings_lists_links_and_escaping(self):
        rendered = markdown_to_html('## Topic\n\n- <note>\n- [Source](https://example.com)\n\nText & detail')
        self.assertIn('<h2>Topic</h2>', rendered)
        self.assertIn('<li>&lt;note&gt;</li>', rendered)
        self.assertIn('href="https://example.com"', rendered)
        self.assertIn('<p>Text &amp; detail</p>', rendered)


if __name__ == '__main__':
    unittest.main()

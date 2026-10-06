import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reading-yearbook-skill/scripts'))
from skill_release import manifest,verify


class ReleaseTests(unittest.TestCase):
    def test_git_line_ending_conversion_does_not_break_text_manifest(self):
        with tempfile.TemporaryDirectory() as tmp,patch('skill_release.REQUIRED',[]):
            root=Path(tmp);source=root/'entry.py';source.write_bytes(b'print("hello")\n')
            expected=manifest(root);(root/'release-manifest.json').write_text(json.dumps(expected),encoding='utf-8')
            source.write_bytes(b'print("hello")\r\n')
            self.assertEqual(verify(root),expected)
            source.write_bytes(b'print("changed")\r\n')
            with self.assertRaisesRegex(ValueError,'版本不匹配'):verify(root)

    def test_svg_and_browser_scripts_survive_git_checkout_line_endings(self):
        with tempfile.TemporaryDirectory() as tmp,patch('skill_release.REQUIRED',[]):
            root=Path(tmp)
            for name,content in [('shape.svg',b'<svg>\n</svg>\n'),('render.cjs',b'const x = 1;\n')]:
                (root/name).write_bytes(content)
            expected=manifest(root)
            (root/'release-manifest.json').write_text(json.dumps(expected),encoding='utf-8')
            for name in ('shape.svg','render.cjs'):
                source=root/name;source.write_bytes(source.read_bytes().replace(b'\n',b'\r\n'))
            self.assertEqual(verify(root),expected)

    def test_manifest_paths_cannot_read_outside_installation(self):
        with tempfile.TemporaryDirectory() as tmp,patch('skill_release.REQUIRED',[]):
            root=Path(tmp)
            (root/'release-manifest.json').write_text(json.dumps({'version':'test','files':[{'path':'../outside','sha256':'irrelevant'}]}),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'路径无效'):verify(root)


if __name__=='__main__':unittest.main()

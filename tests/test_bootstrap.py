import contextlib, io, pathlib, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class BootstrapTests(unittest.TestCase):
    def test_sections(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from bootstrap import sections
        self.assertEqual(sections('## A\nhello\n## B\nworld')['B'],'world')
    def test_markers(self):
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        from bootstrap import replace_generated
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'x.md'
            p.write_text('before\n<!-- BEGIN GENERATED -->\nold\n<!-- END GENERATED -->\nafter')
            replace_generated(p,'new')
            self.assertIn('after',p.read_text())
            self.assertNotIn('old',p.read_text())
    def test_preview_apply_check_and_conflict(self):
        import sys
        sys.path.insert(0, str(ROOT/'scripts'))
        from bootstrap import MAPPING, START, END, main
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            (root/'.loop').mkdir()
            (root/'PROJECT_KNOWHOW.md').write_text('## One-Line Purpose\nA useful tool\n')
            for rel in MAPPING:
                path = root/rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f'# Heading\n\n{START}\nold\n{END}\ncustom prose\n')
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([], root), 0)
                self.assertEqual(main(['--check'], root), 1)
                self.assertEqual(main(['--apply'], root), 0)
                self.assertEqual(main(['--check'], root), 0)
            self.assertIn('custom prose', (root/'docs/PRD.md').read_text())
            path = root/'docs/PRD.md'
            path.write_text(path.read_text().replace('A useful tool', 'human edit'))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--apply'], root), 2)
            self.assertIn('human edit', path.read_text())

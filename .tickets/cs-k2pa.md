---
id: cs-k2pa
status: closed
deps: [cs-wyaa]
links: []
created: 2026-02-20T05:33:37Z
type: task
priority: 2
assignee: Michael Barrett
parent: cs-kmv6
---
# Clean up test_session.py: eliminate decorator stacking

Every test in TestRunSession repeats the same triple @patch decorator stack:
  @patch('claude_storm.session.generate_summary')
  @patch('claude_storm.session.compile_deliverables')  
  @patch('claude_storm.session.invoke_agent')

That's 3 decorators x 13+ tests = 39+ lines of pure noise. mock_compile and mock_summary are often not even asserted on.

FIX: Move the patches into the existing _setup autouse fixture:

  @pytest.fixture(autouse=True)
  def _setup(self, make_config, capture_display):
      self.make_config = make_config
      self.display, self.buf = capture_display
      with patch('claude_storm.session.generate_summary') as self.mock_summary,            patch('claude_storm.session.compile_deliverables') as self.mock_compile,            patch('claude_storm.session.invoke_agent') as self.mock_invoke:
          yield

Then each test method sets self.mock_invoke.side_effect = [...] directly, no decorators needed.

NOTE: This ticket should be done AFTER cs-wyaa (split test_cli.py) since that ticket moves additional test classes into test_session.py.

Files touched: test_session.py only


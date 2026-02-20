---
id: cs-5rz4
status: closed
deps: [cs-wyaa]
links: []
created: 2026-02-20T05:34:33Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-kmv6
---
# Simplify _resolve_start_config test boilerplate in test_cli.py

After cs-wyaa splits test_cli.py, the remaining TestResolveStartConfig tests pass all 14 keyword arguments explicitly every time, even though most are None/False defaults. This creates walls of identical boilerplate that obscure what each test actually varies.

FIX: Create a helper function at the top of the test class or module:

  def _resolve(console, **overrides):
      defaults = dict(
          topic=None, config_path=None, goal=None, roles=None,
          max_turns=None, max_minutes=None, auto_complete=None,
          interactive=None, model=None, deliverable=None,
          reference_dir=None, agent_timeout=None, debug=False,
      )
      defaults.update(overrides)
      return _resolve_start_config(console=console, **defaults)

Then each test only specifies the params it cares about:
  config = _resolve(console, topic='AI', max_turns=5)

Locations (approximate — verify after split): TestResolveStartConfig, roughly lines 1199-1318 of current test_cli.py.

Files touched: test_cli.py only (after split)


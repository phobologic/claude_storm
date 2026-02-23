---
id: cs-tgzr
status: closed
deps: []
links: []
created: 2026-02-23T02:38:19Z
type: task
priority: 3
assignee: Michael Barrett
parent: cs-ohde
tags: [code-review, reviewer:readability]
---
# test_app.py new scroll-indicator tests duplicate the following=False/True toggle pattern without a shared helper

**File**: tests/test_app.py **Line(s)**: 65-100 **Description**: test_scroll_indicator_shows_when_not_following and test_scroll_indicator_hides_when_following_resumes each repeat the same setup pattern: create config, construct StormApp, patch _session_worker, run_test, query log, set log.following, await pilot.pause(), query indicator, assert indicator.display. The boilerplate is four lines longer than it needs to be and the pattern will likely be copied again. Extracting a small async helper or using a pytest fixture to obtain (pilot, log, indicator) would make each test body a two-liner and keep the suite DRY. **Suggested Fix**: Extract a shared async context helper or fixture for scroll-indicator tests.


## Notes

**2026-02-23T05:39:53Z**

Closing as won't-fix. Three tests sharing ~4 lines of setup is normal test structure. Extracting a helper would add indirection for no meaningful gain.

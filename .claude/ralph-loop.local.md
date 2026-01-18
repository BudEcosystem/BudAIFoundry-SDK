---
active: true
iteration: 6
max_iterations: 30
completion_promise: "FEATURE_READY"
started_at: "2026-01-18T19:50:13Z"
---

ROTATING PERSONA REVIEW (cycle each iteration):

ITERATION MOD 4:

[0] CODE REVIEWER:
- Review code for bugs, security issues, edge cases
- Check error handling and types
- Fix any issues found

[1] SYSTEM ARCHITECT:
- Review file structure and dependencies
- Check separation of concerns
- Refactor if needed

[2] QA ENGINEER:
- Run: all test
- Identify any edge case scenarios

[3] SECURITY ANALYST:
- Review input validation and sanitization
- Check for DoS vectors (large inputs, timeouts)
- Verify no sensitive data in logs
- Check dependency vulnerabilities: cargo audit
- Review authentication/authorization if applicable

EACH ITERATION:
- Identify current persona (iteration % 4)
- Perform that persona's review
- Make ONE improvement or fix
- Identify  edge cases scenarios
- If no issues found by ANY persona for 2 full cycles, output completion

OUTPUT <promise>FEATURE_READY</promise> when all personas report no issues

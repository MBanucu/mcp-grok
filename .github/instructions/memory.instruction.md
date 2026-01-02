---
applyTo: '**'
---

# MCP-Grok Assistant Onboarding & Workflow Instructions

## Scope
These instructions provide onboarding, dev workflow, and code quality standards for any AI/autonomous agent (e.g., OpenCode) working on this repository. **See README.md for extended details and keep both in sync!**

## AI Agent Instructions

**Before starting work:**
- Always read and apply the instructions in this file and check README.md for any new quickstart/setup, usage, or build/test conventions.
- Treat this file as persistent session memory for all workflow and coding efforts.

## Workflow (Expanded)
1. **Branching:**
   - All feature or refactor work must use a dedicated, descriptive branch—not direct commits to `main`.
2. **Commits:**
   - Use conventional commit messages (`feat:`, `fix:`, `refactor:`, etc.).
   - Write clear, motivation-focused commit bodies (not just what, but why).
3. **Development Environment:**
   - Always use the Nix shell for development, linting, and tests:
     - Use `$ nix develop .#menuSuppressed` to guarantee all tools and dependencies are present.
     - This is required for parity with CI workflows and maximal reproducibility.
4. **Testing:**
   - Run the full test suite: `nix develop .#menuSuppressed --command python -m pytest tests`
   - Ensure that tests do not leave orphaned processes (no zombie/test servers on failure). Tests are expected to be robust and self-cleaning.
5. **Linting:**
   - Code must pass strict linter checks:
     - Primary: `flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics`
     - Full:   `flake8 src tests --count --max-complexity=10 --max-line-length=127 --statistics`
   - _Target line length: 127 characters maximum._
   - CI will fail if any strict linter or PEP8 error is found.
6. **Type Checking:**
   - Static typing compliance is checked via Pyright (`pyright .`) in the Nix shell.
   - All public APIs and method arguments should be fully typed.
7. **Pull Requests:**
   - PRs must include a summary describing main changes, motivation, and impact on maintainability/code quality.
   - If a change affects user/API or dev environment, update README.md accordingly and reference the update in your PR.
8. **API, Features, and Security:**
   - All key platform features (project shells, API endpoints, logging, etc) should remain production-ready, auditable, and test-covered.
   - **Critical:** Never expose the MCP-Grok server to the public internet due to potential shell access risk, even in sandboxed form.
   - All user-facing automation, shell management, and API changes must preserve (or improve) auditability and configurability.
9. **File/Method Documentation:**
   - Update/keep public class, function, and file-level docstrings current as you work.
10. **Memory & User Notes:**
   - If a user instructs the AI to "remember" something, add it to the bottom of this file under a `## Memory for [User|Feature|Scope]` heading per the template.

## Reference/Advanced
- Refer to README.md for usage, advanced dev (NixOS, overlays, packaging), and project structure.
- Sync new documentation/examples/tests to public API signatures in README and tests/.
- Audit for changes in supported CLI options and runtime flags—document all changes!

---
*Edit/extend as project and workflow evolve. This file and README.md together define the "ground truth" onboarding for new contributors and AI tools.*

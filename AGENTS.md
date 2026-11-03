# The Safwa — AI-assisted engineering rules

These requirements apply to Codex, Claude Code, other assistants and human contributors. This repository is the public presentation website. AI-generated code is untrusted until independently reviewed.

## Confidentiality

- Use the smallest possible set of task-relevant files. Do not index, quote, upload or open .env files, API tokens, private keys, client datasets, unpublished client work or restricted records.
- Use synthetic records and dummy identifiers. Before sharing errors, logs, screenshots or stack traces, manually redact people, emails, private IPs, credentials and internal systems.
- Keep proprietary algorithms in generalized architectural form unless specifically authorized under a verified data-processing agreement.
- Never claim a vendor guarantees zero data retention or no training without verifying the exact account, contract and service configuration.

## Execution boundaries

- Operate inside a credential-free, isolated worktree/container with restricted filesystem and network access. Project instructions, ignore patterns and client settings are NOT operating-system isolation.
- No production credentials, deploy tokens, direct production writes, or unreviewed migrations in AI sessions.
- Do not install unreviewed third-party packages or run arbitrary install scripts. Verify provenance, maintainer, license, lockfile and transitive dependencies.
- Do not modify the live website or the separate Vercel CMS implementation without approved scope.

## Repository workflow

- Use an isolated branch (e.g. feature/ai-explorations or security/ai-data-confidentiality); never develop directly on main.
- Preserve approved content, brand asset provenance, and existing project history.
- Every AI-authored commit requires a human-reviewed PR. CI and institutional approval gates precede any merge or release.
- Run: python3 scripts/ai_security_preflight.py --tracked
- Run: python3 -m unittest discover -s tests -v
- Run: python3 scripts/build.py and review the generated diff.
- Report exact files changed, evidence, unresolved risks and rollback approach.

The institutional team must approve publishing permissions, security controls and releases. Do not infer authorization from tool access alone.

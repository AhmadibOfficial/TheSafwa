# Safwa confidentiality and AI-assisted engineering standard

Status: branch-only implementation; controls are NOT yet approved or enforced on main.

## Scope

This change protects the public AhmadibOfficial/TheSafwa repository. The separate repository and administrator CMS behind thesafwa.vercel.app have not been reviewed. Do not assume these controls cover them.

## Threats to address

Secret leakage through commits, prompts or logs; exposed client information; malicious assistant instructions; unreviewed generated code; package confusion; overbroad AI tool access; compromised CI; and unapproved production deployments.

## Practical controls

1. Credentials and client data never belong in Git or an AI-visible workspace. The expanded .gitignore excludes common secret paths but does not untrack already committed secrets.
2. .claude/settings.json denies direct read access to sensitive paths for supported Claude Code tools. This does not block every Bash subprocess. Actual isolation requires OS/container permissions and sanitized mounts.
3. .codex/config.toml provides restricted project defaults when trusted and supported by the installed client. These are NOT a replacement for OS-level access boundaries.
4. Run git config core.hooksPath .githooks once after checking out the security changes. The hook runs the dependency-free staged-file scanner. Developers can bypass hooks; CI independently checks tracked files.
5. CI includes pinned official GitHub checkout and CodeQL, and the pinned Gitleaks v3 action. Gitleaks PR comments and report uploads are disabled to avoid distributing potentially sensitive report content. The action may require a license after the repository transfers to an organization.
6. All packages and Actions must be assessed for provenance and licensing. Dependency updates go through reviewed pull requests.
7. AI assistance must never hold deploy tokens, production database access, SSH agents, unrestricted home-directory mounts, or an authorized production deployment path.
8. Before prompts, manually redact personal information, private IP addresses, customer logs, infrastructure hostnames, keys and identifiers. Feed only the minimum authorized source excerpt.
9. Zero-data-retention and no-training requirements must be verified contractually for the specific AI provider, service, and account. A repository file cannot create these guarantees.

## Required GitHub administrator actions

- [ ] Agree institutional GitHub ownership and at least two accountable maintainers.
- [ ] Enable main-branch rules: reviewed PRs only, resolved conversations, no force pushes/deletions, and required security checks.
- [ ] Require Confidentiality and source verification, CodeQL static analysis and Gitleaks history and PR scan after these jobs have passed in CI.
- [ ] Enable GitHub secret scanning/push protection where available; assign alert triage owner.
- [ ] Restrict Actions tokens, third-party Actions, environment secrets and production deploy permissions.
- [ ] Establish separate staging and production credentials, mandatory release approval and tested rollback.
- [ ] Verify AI contracts and account settings before any restricted data is processed.
- [ ] Test recovery and document incident notification and credential rotation procedures.

## Validation and limitations

Local security unit tests validate common sensitive-path and credential patterns; the scanner deliberately does not print matched secrets. These automated controls are not comprehensive: they may miss novel tokens, embeddings of secrets in binaries, or historical disclosures. A detected leak requires rotation and investigation; adding .gitignore or deleting a line does not revoke a compromised secret.

Do not merge this PR until the team has reviewed the diff, CI has passed, and the governance decisions are recorded. No production deployment is authorized by this document.

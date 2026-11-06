# Remote access during local review

The CMS can stay on the owner's Kali computer while authorized staff use it through an HTTPS address. This is a local review arrangement, dependent on that computer, its internet connection, and the ngrok service. It does not change the existing public Render website or require a paid Render instance.

## Owner setup

1. Set up the existing CMS using `bash safwa setup`, create your individual administrator account, enroll its authenticator, and confirm that `bash safwa local` works. Stop the local server with Ctrl+C before starting a remote session.
2. Create your own [ngrok account](https://dashboard.ngrok.com/signup) and install the official [Linux ngrok agent](https://ngrok.com/downloads/linux). Use the vendor's signed package repository or verify a release against the vendor's checksum. The agent is proprietary software governed by [ngrok's terms](https://ngrok.com/tos); it is not included in this repository or the Python dependency lockfile. No software is downloaded or installed by the remote commands.
3. In [Domains](https://dashboard.ngrok.com/domains), copy the assigned HTTPS dev domain. This helper accepts only an assigned `ngrok-free.app` or `ngrok-free.dev` domain. Do not enter the Render address.
4. From the Safwa project directory, run:

   ```sh
   bash safwa remote-setup
   ```

   Enter the HTTPS address and the exact Google sign-in email addresses permitted to use it. Include your own. Wildcards, whole-domain grants, empty lists, and lists exceeding three people are rejected. Settings are saved under ignored, owner-only `private/remote/`; they contain no passwords or tokens. Configure the addresses locally rather than posting the list in a repository.

5. Open [Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) privately, then run:

   ```sh
   bash safwa remote
   ```

   Paste the agent authtoken into the hidden terminal prompt. The launcher does not save it in a file, command argument, shell history, or CMS database. It passes the token in the ngrok child's environment for this session. The operating-system account owner and root can inspect that process; use a trusted computer and individual OS accounts. Keep the token private and revoke it in ngrok if exposed.

The command validates the agent configuration, starts Waitress on `127.0.0.1`, checks CMS health using the exact HTTPS Host, then starts a single named ngrok endpoint. An occupied port, invalid configuration, missing agent, or failed CMS health check prevents tunnel startup. It does not start SSH, remote desktop, a system service, router forwarding, or a network-wide listener. Stop it with Ctrl+C; it stops both child processes. If either process exits, the other is stopped. A session lock prevents a second launcher or setup from changing access while a session is active.

For a database outside the default location, supply its existing path before the command:

```sh
bash safwa --database /absolute/path/to/review.sqlite3 remote
```

## Access checks before sharing

Process startup is not proof that the external authentication policy works. The owner must perform these checks on the assigned HTTPS address before inviting staff:

| Check | Required result |
| --- | --- |
| Open `/editor` in a private browser without an ngrok login | Google authentication is required before reaching the CMS. |
| Authenticate with an explicitly allowed email | The CMS asks for that staff member's username, passphrase and authenticator code. |
| Authenticate with an email absent from the list | Access is denied before the CMS is reached. |
| Enter an incorrect CMS passphrase or authenticator code | CMS sign-in fails. |
| Sign in with an editor's account | Only that account's assigned area and editorial permissions are available. |
| Close the owner session | Remote requests no longer reach the CMS. |

Create an individual CMS account for each person through the existing staff workflow. An email being allowed through ngrok does not grant a CMS account or publishing rights. Do not share administrator credentials or authenticator seeds. To remove access, stop the session, run `bash safwa remote-setup` with the reduced list, revoke that person's CMS account, and restart. Reconfiguration is intentionally blocked while the launcher holds its lock.

## Security and service limits

The policy runs Google OAuth first and denies any identity absent from the explicit list. The CMS keeps its exact Host and Origin checks, CSRF defenses, Secure/HttpOnly/SameSite cookies, MFA, role boundaries, and publishing approvals. The helper does not weaken these controls to make proxying work. Local ngrok request inspection, its local web UI, and remote agent management are disabled in the generated configuration.

HTTPS terminates at ngrok; ngrok is a trusted intermediary that processes this traffic. Disabling local inspection does not disable or guarantee the absence of provider-side metadata or retention. Keep full request/response capture off in the ngrok dashboard and verify the account settings before using private institutional records. Use synthetic content for review until the institution approves the service and access checks pass. For permanent production, ngrok recommends a customer-owned OAuth application instead of its managed Google application; the current helper is scoped to local review.

At verification on 6 November 2026, ngrok's free offering included one assigned dev domain, three monthly active OAuth identities, 1 GB of outgoing data, 20,000 HTTP requests per month, and a browser interstitial. Traffic Policy usage also consumes the account's usage allowance. Those are provider limits, not guaranteed free permanent hosting. See [current pricing](https://ngrok.com/pricing) and [free plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits). A denied Google identity may still consume the identity quota by authenticating, so perform the negative access check with awareness of the three-user allowance.

## Implementation references and verification

The helper uses only Python's standard library and the CMS's existing pinned Waitress runtime. ngrok is an independently installed vendor agent. Configuration follows the official [v3 agent reference](https://ngrok.com/docs/gateway/agent/config/v3), [CLI reference](https://ngrok.com/docs/gateway/agent/cli), [explicit email allowlist example](https://ngrok.com/docs/gateway/traffic-policy/examples/oauth-protection), and [official container's token environment convention](https://github.com/ngrok/docker-ngrok).

Repository checks use synthetic identities, temporary settings, a synthetic CMS database and a local agent stand-in. They verify input rejection, owner-only file permissions, the policy and server boundary, occupied-port refusal, child-process cleanup, and preservation of existing public pages. These checks do not exercise a real ngrok account or Google OAuth. No live endpoint is provisioned by CI or this code change.

The generated configuration was also accepted by the official ngrok agent 3.39.13 using `ngrok config check` with synthetic input, without opening a tunnel. The QA binary's archive matched SHA-256 `c3bb99ccd29f6ed4a901cf88100d646256d291d80fc94f53c241f8d544f2a8a5`, published by ngrok in its `docker-ngrok` release manifest. Normal Ctrl+C, SIGTERM and terminal hangup are handled; a forced process kill cannot run cleanup, so stop any remaining local ngrok process if the launcher is forcibly killed.

To return to local-only work, stop the remote session and run `bash safwa local`. Retain the database and its separately protected CMS encryption key. Do not commit `private/`, tunnel tokens, staff data, or enrollment material.

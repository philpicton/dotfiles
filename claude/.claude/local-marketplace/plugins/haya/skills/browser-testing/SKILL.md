---
name: browser-testing
description: Test or regression-test the local Haya apps (create, collect, collaborate) in a real browser. Use whenever the user asks to check, test, verify, smoke-test or regression-test something "in the browser", on admin/dashboard/partner.haya-local.dev, or to check a branch/PR doesn't break the UI. Contains local login accounts for every role, customers mapped to cases, partner logins, the chrome-devtools workflow and known environment quirks.
---

# Haya local browser testing

Local docker stack only. Everything below is test data — fine to use freely.

## Apps

| App | URL | Who logs in |
|---|---|---|
| create (staff) | https://admin.haya-local.dev | staff roles |
| collect (customer) | https://dashboard.haya-local.dev | customers |
| collaborate (partner) | https://partner.haya-local.dev | partners (staff can log in but see empty pages) |
| API | https://api.haya-local.dev | — |
| mail catcher | https://mail.haya-local.dev | — |

Check the stack first with `haya_status`; if containers aren't running use `haya_up` / `haya_wait_healthy`. Restarting/rebuilding containers is the user's call — ask first.

## Logins — password for all of these is `password`

**Staff (create)** — role: email (user id)
- super_admin: `super.admin@haysto.com` (1) — default; sees everything, single account, no partners
- admin: `admin@haysto.com` (8)
- Mortgage Expert (mortgage_seller_staff): `mortgage@haysto.com` (20, team Leader), `mortgage.expert@haysto.com` (21), `evan.parry@haysto.com` (19)
- Mortgage Advisor (mortgage_staff): `advisor@haysto.com` (14), `mortgage.advisor@haysto.com` (15)
- MA with training NOT completed: `training@haysto.com` (18) — the only one; use for training-cases view / training gates
- PAM (pre_app_staff): `pre_app@haysto.com` (27), `pre_app.manager@haysto.com` (28)
- Case Manager: `case@haysto.com` (23), `case.manager@haysto.com` (24)
- Case Administrator: `case.administrator@haysto.com` (34)
- Insurance Specialist: `insurance@haysto.com` (11), `insurance.specialist@haysto.com` (12)
- Underwriter: `underwriter@haysto.com` (31)
- Customer Support: `support@haysto.com` (25)
- Compliance: `compliance@haysto.com` (30)
- HLP partner (hlp_partner): `hlp@haysto.com` (29)
- Other team Leaders: `uw.haysto.haysto.3@haysto.com` (102), `is.haysto.cmf.1@haysto.com` (109), `pam.picnic.picnic.1@haysto.com` (136)

Super admin skips many permission/role branches. When a change touches role, permission, training or "my cases" logic, also test with a non-admin role from the list.

**Customers (collect)** — email → case id
- `james.phillips+client@haysto.com` → case 2 (messages, pending mortgage status-change request, XSSTEST data)
- `joao.matos+client@haysto.com` → case 1
- `dave.phillips+client@haysto.com` → case 3 (never logged in → onboarding flow)
- `luke.clarke@example.org` → case 24 (documents awaiting approval — good for document viewer / Approve-Reject)
- `holmes.lilly@example.net` → case 32, `bethany44@example.org` → case 21

**Partners (collaborate)**
- `matt.dobson+partner@checkmyfile.com` (85) → Checkmyfile — **use this one**; has a metrics config so analytics / loss-analysis render.
- `super.admin+partner@haysto.com` (84) → Haysto — logs in but `haysto` has no entry in `haysto-v2-create/assets/partners/data/partner-metrics.ts`, so pages are empty by design.
- `PartnerSeeder` creates partner users with an empty password. Ids 84 and 85 were set to `password` by hand; a DB re-seed reverts this. If their login fails with "credentials do not match", re-set them (local DB only):
  ```
  haya_exec_api: php artisan tinker --execute='use Illuminate\Support\Facades\{DB,Hash}; DB::table("users")->whereIn("id",[84,85])->update(["password"=>Hash::make("password")]);'
  ```
  Other partner users (86–90: experian, picnic, oaknorth, persimmon, charleschurch) still have empty passwords — ask before changing more.
- Factory partner users (e.g. `florence.cook@example.net`) accept `password` but have no partners → empty pages.

Not available: no user with multiple related accounts, so the account switcher can't be tested without setting data up.

IDs reflect the local DB as of Nov 2026. If one doesn't exist, look it up rather than guessing (see "Finding test data").

## Browser workflow (chrome-devtools MCP)

1. **Start:** `list_pages`. If it errors that the profile at `~/.cache/chrome-devtools-mcp/chrome-profile` is already in use, ask the user to close the other DevTools Chrome instance. Never kill it yourself.
2. **Sessions:** cookies are shared across `*.haya-local.dev`, so logging in or out on one app affects the others. Test each extra role in its own `new_page` with `isolatedContext: "<role>"` (e.g. `"customer"`, `"partner"`, `"ma"`). That keeps the super-admin session in the default context intact. A new context has a cold cache, so expect the reload quirk below.
3. **Log in:** go to `/auth/login`, `take_snapshot`, `fill` Email and Password, click "Sign in". Pre-login console 419/401 errors are normal.
4. **Per page:** `navigate_page`, then wait about 6–10 s (an `evaluate_script` that sleeps, then returns `location.href` plus the `main` innerText), then `list_console_messages` with `types: ["error"]`. Check warnings separately, because Vue warnings are noisy (see below).
5. **Checking a feature:** read `document.body.innerText` or target elements with `evaluate_script`. Use `take_screenshot` (jpeg, quality ~45) for visual checks. Modals are `[role=dialog]`. Nuxt state such as the current user: `document.querySelector('#__nuxt').__vue_app__.config.globalProperties.$nuxt.payload.state['$suser']`.
6. **Don't change data** unless the user asks: open forms and modals to inspect them, then Cancel/Close. Never submit, approve, delete or send.
7. **Logout check:** a good test for auth-state changes. It should land on `/auth/login?redirect=…` without errors.

## Known environment quirks (not app bugs)

- **"Failed to fetch dynamically imported module" / blank white page / Nuxt client error page ("500") on first load after a container restart, a Vite dependency re-optimisation (`?v=` hash changes, e.g. the first visit to `/diary/calendar`), or in a fresh isolated context. Reload; it sometimes takes 2–3 reloads. To see which module failed, navigate with `initScript: "performance.setResourceTimingBufferSize(20000);"` and filter the resource entries for `responseStatus === 0`. The file usually serves fine via `curl -sk`.
- **API rate limit:** 400 requests per window. Heavy testing gives 429s; pause for a minute.
- **Request to an odd domain** (e.g. `v1tpes.cc/...` returning `{"success":true}`) is FormKit Pro's obfuscated licence check from `@formkit/pro`, not an exfiltration.
- **`take_snapshot` / `get_network_request` `filePath`** only accept paths inside the MCP's workspace roots. Return data inline instead of using the scratchpad.
- **Pre-existing console noise:** `[VPV Warning]` licence warning; `injection "cases" not found` in `CasesAssignRoleModal` on pipelines; prop-type warnings in pipeline table cells; missing `skipChaseTask` prop on the document request page; a collect sign-out `Cannot destructure property 'items'` from `useFees.ts` (fees fetch 401s after logout). Compare against `origin/main` before blaming a branch.

## Finding test data

Use `haya_exec_api` with tinker (read-only queries unless the user agrees otherwise). Roles are spatie: join `model_has_roles` → `roles.name`. Examples:
```
# users per role, with a check that "password" works
php artisan tinker --execute='use Illuminate\Support\Facades\{DB,Hash}; foreach (DB::table("model_has_roles")->join("roles","roles.id","=","role_id")->join("users","users.id","=","model_id")->orderBy("roles.id")->get(["roles.name as role","users.id","users.email","users.password"])->groupBy("role") as $r=>$g){echo "$r\n"; foreach($g->take(4) as $u) echo "  $u->id $u->email ".(Hash::check("password",$u->password)?"ok":"NO-PW")."\n";}'
# customer → case
... DB::table("users")->join("case_contact","case_contact.contact_id","=","users.primary_contact_id") ...
# cases with documents
... DB::table("documents")->whereNull("deleted_at")->selectRaw("case_id,count(*) c")->groupBy("case_id")->orderByDesc("c")->take(5)->get() ...
```
Seeders: `haysto-v2-api/database/seeders/UsersTableSeeder.php` (named staff), `ExtendedUsersTableSeeder.php` (`<role>.<brand>.<partner>.N@haysto.com`), `PartnerSeeder.php`.

## Regression-testing a branch

1. Repos: `haysto-v2-create`, `haysto-v2-collect`, `haysto-v2-collaborate`, `lib/js/haysto-v2-lib_shared` (shared layer; it affects all three apps). Use read-only git only (`status`, `log`, `diff`). Never checkout, pull or stash.
2. `git -C <repo> log --oneline --no-merges origin/main..HEAD` and `git -C <repo> diff origin/main...HEAD` for each repo. Read the diffs, list the pages and components touched, and grep consumers of anything changed in lib_shared.
3. Build a page list per app from the diff, then run the browser workflow with the role(s) that exercise the changed branches.
4. The apps are client-side SPAs (`ssr: false` in the lib_shared `nuxt.config.ts`), so runtime errors show up in the browser console, not in container logs. The Nuxt/Vite dev-server logs only help for build, compile and HMR problems or dependency re-optimisation: `docker compose -f docker-compose.yml -f docker-compose.local.yml logs --no-color --since 30m haysto-create` (and the collect/collaborate services), run from `~/code/haysto-v2`. API errors are in the `haysto-api` logs and in the network tab.
5. Report: what was tested and passed, findings (separating branch-caused from pre-existing), and what wasn't covered and why.

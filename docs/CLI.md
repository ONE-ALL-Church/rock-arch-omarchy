# Terminal and agent CLI

A managed Omarchy installation creates an owner-local `rock-arch` command in
`~/.local/bin` when its broker starts. The command is a client of the same
broker used by the Omarchy panel; it does not implement another login, cookie
store, Rock client, or Magnus client. A source checkout cannot repoint the
managed launcher. If an unrelated `rock-arch` command already exists, Rock
Arch does not overwrite it and reports the conflict in Settings.

Terminal and agent access is enabled by default and can be disabled in
**Settings**. It is intentionally not another onboarding decision: enabling it
does not open a TCP port or allow another OS user through the owner-only socket.
When disabled, Rock commands return `terminal_access_disabled`. Local settings
and shortcut management remain available, including
`rock-arch settings set terminalAccess true` to restore access. Settings reads
return preferences only, without profile identities or Rock data.

The local Unix account remains the security boundary. The preference controls
the supported CLI, not hostile software already running as that same account.

## Output and lifecycle

Every successful command writes one JSON object to stdout. Errors write one
JSON object to stderr and return nonzero. Output is compact by default for
agents; put `--pretty` before the command for indented output.

Every object includes `"protocolVersion": 1`. Inspect the complete contract
without starting or contacting the broker:

```bash
rock-arch schema
```

```bash
rock-arch status
rock-arch --pretty status --probe-magnus
rock-arch capabilities --refresh
rock-arch doctor
rock-arch doctor --refresh
```

`doctor` checks the private broker socket, secure storage, Rock login, detected
entity access, optional Magnus access, terminal launcher, and update manager.
Its output is deliberately redacted: it contains no profile names or IDs,
instance origin, filesystem path, query, target URL, cookie, username, or
password. `--refresh` performs current entity/Magnus/update checks.

The CLI connects to `$XDG_RUNTIME_DIR/rock-arch/broker.sock`. It safely starts
the broker when needed; `--no-start` changes a missing broker into a stable
`broker_unavailable` error. Requests are limited to 16 KiB and responses to
5 MiB. The CLI validates that both the socket and its directory belong to the
current user and are inaccessible to group and other users before connecting.

Search results, Knowledge results, links, files, and build descriptors use
opaque `safeId` values. Use the ID returned by one command in the follow-up
command. IDs are intentionally invalidated when the broker restarts.

## Login and profiles

Login normally uses a masked prompt. Agents can use `login --stdin` or
`profiles add --stdin` to supply a bounded JSON object through stdin. Passwords
are never CLI arguments or part of JSON output.

```bash
rock-arch login
rock-arch profiles list
rock-arch profiles add --name "Production" --domain rock.example.org
rock-arch profiles use PROFILE_ID
rock-arch profiles test
rock-arch profiles rename PROFILE_ID "Main Campus"
rock-arch profiles sign-out --confirm
rock-arch profiles remove PROFILE_ID --confirm
```

`login` updates the active profile. When no profile exists, it asks for profile
name and domain before the username and masked password. `profiles add` also
prompts for any omitted non-secret fields and prompts for the password.

For `login --stdin`, supply `username` and `password`; also include `name` and
`domain` when there is no active profile. `profiles add --stdin` requires all
four string fields. Input is limited to 8 KiB. Deliver it through a protected
stdin channel, rather than embedding credentials in shell command text or
arguments. Unknown fields and conflicting input modes are rejected.

## Settings and keyboard shortcuts

```bash
rock-arch settings get
rock-arch settings schema
rock-arch settings set showPersonContext false
rock-arch settings set enabledCategories '["People","Groups"]'
rock-arch settings set tabOrder '["knowledge","search","personal","magnus"]'
rock-arch settings set --stdin
```

The final form reads a JSON object such as:

```json
{"tabOrder":["knowledge","search","personal","magnus"],"recentLinks":false}
```

Changes use the same preference store and validation as the panel. A batch
either saves completely or changes nothing. The offline schema lists every
editable preference, type, default, and allowed category/tab ID. Internal
onboarding flags are not editable settings. Tab order must contain every tab
ID exactly once; `personal` is the Links tab. Numbered shortcuts follow the
visible order, with unavailable tabs omitted; Settings uses `Ctrl+,`.

Successful changes request a panel refresh without opening it. `panelRefreshed`
indicates whether the running shell accepted that request; saved preferences
also load the next time the panel opens. Hiding the menu icon requires an
existing working shortcut.

```bash
rock-arch shortcuts status
rock-arch shortcuts check 'Super + Shift + R'
rock-arch shortcuts set 'Super + Shift + R' --dry-run
rock-arch shortcuts set 'Super + Shift + R' --confirm
rock-arch shortcuts remove --confirm
```

Shortcut changes use a fresh revision check, conflict detection, backup,
Hyprland reload verification, and rollback from the panel's shortcut manager.
Existing manual bindings are never replaced. Removal restores the menu icon.
`status` and `check` return structured shortcut state; failed set/remove
operations return nonzero and a stable error code.

## Rock search and links

```bash
rock-arch search --stdin
rock-arch search -
rock-arch search
rock-arch search 42 --entity groups
rock-arch search GUID --entity people
rock-arch person SAFE_ID
rock-arch links personal
rock-arch links recent
rock-arch open SAFE_ID --confirm
rock-arch links activate SAFE_ID --confirm
rock-arch links clear --confirm
```

The first two search forms read at most 8 KiB from stdin. With no query, an
interactive terminal prompts for it; redirected stdin is read automatically.
This is preferred for person names and other private terms because the query
does not appear in the command's arguments. Positional queries remain supported
for compatibility and non-sensitive terms.

`--entity` accepts `people`, `groups`, `group-types`, `workflows`, `jobs`,
`pages`, `content-types`, or `content-items`. Search still honors the active
profile's detected Rock permissions and enabled categories. Opening an item,
rerunning a Recent Link, and clearing history require `--confirm` because they
affect the desktop, Rock, or local history.

Use `rock-arch describe SAFE_ID` to inspect a registered target's title, kind,
available actions, and opaque-ID lifetime without opening or reading it. Every
confirmed action also accepts `--dry-run` in place of `--confirm`. A dry run
validates the registered target and returns expected side effects with
`"executed": false`.

## Public Rock Knowledge

```bash
rock-arch knowledge search "workflow activation"
rock-arch knowledge search "mm: Group"
rock-arch knowledge search "is: check-in labels"
rock-arch knowledge get SAFE_ID
rock-arch knowledge open SAFE_ID --confirm
```

Knowledge uses the same credentialless, fixed-origin public boundary as the UI.
Details can return related items with their own `safeId`, allowing an agent to
walk article, issue, Lava-context, concept, and Model Map relationships without
receiving arbitrary URLs. Opening the cited public source requires confirmation.

## Magnus

```bash
rock-arch magnus status
rock-arch magnus browse
rock-arch magnus browse SAFE_FOLDER_ID
rock-arch magnus preview SAFE_FILE_ID
rock-arch magnus hash SAFE_FILE_ID
rock-arch magnus download SAFE_FILE_ID --confirm
rock-arch magnus copy SAFE_FILE_ID hash --confirm
rock-arch magnus copy SAFE_FILE_ID content --confirm
rock-arch magnus open SAFE_FILE_ID --confirm
rock-arch magnus build SAFE_APP_ID --confirm
rock-arch magnus builds
rock-arch magnus build-status BUILD_ID
```

Browse first to register folder, file, and mobile-app descriptors as opaque
IDs. Preview is bounded to UTF-8 text. Hash returns SHA-256 and size without
returning file contents. Download writes a new mode-`0600` file without
overwriting; clipboard, browser, and build actions require confirmation. A
build remains limited to a descriptor-advertised numeric mobile-app endpoint.

When Magnus accepts a build request, Rock Arch stores a profile-scoped,
mode-`0600` local receipt with an opaque `buildId`, acceptance time, and state
`accepted`, then sends a local desktop notification. `builds` and
`build-status` can poll those receipts across broker restarts. They do not claim
completion: the Magnus surface currently available to Rock Arch has no
dependable completion-status endpoint, so each receipt explicitly returns
`"statusSource": "local"` and `"completionVerifiable": false`.

Rock Arch still exposes no Magnus write, upload, delete, mkdir, touch, arbitrary
endpoint, SQL, job-run, or generic Rock mutation command.

## Updates

```bash
rock-arch updates status
rock-arch updates check
rock-arch updates install --confirm
```

The same Git-managed-install, clean-worktree, fast-forward, manifest identity,
and Omarchy validation rules used by Settings apply to CLI updates.

## Omarchy panel handoff

```bash
rock-arch ui open
rock-arch ui open links
rock-arch ui open knowledge --stdin
rock-arch ui open magnus
rock-arch ui open settings
rock-arch ui close
```

Rock Arch stages a one-time view/query payload in the owner-only broker and
then calls the canonical `omarchy-shell` IPC target with fixed arguments. Query
text is never placed in the Omarchy command arguments. The panel consumes the
payload once; an unclaimed payload is erased after 30 seconds.

## Legacy module commands

`python3 -m rock_arch_broker rock status|login` and
`python3 -m rock_arch_broker magnus status|configure` are deprecated aliases.
They print migration guidance on stderr and use the supported broker client,
JSON output, and exit codes. `magnus configure` maps to `rock-arch login`.

The raw-path `magnus ls|cat|hash` module commands now exit with status 2 and
instructions to use `rock-arch magnus browse` plus opaque IDs. They do not start
a broker, access the keyring or network, or write an output file. See
[MAGNUS.md](MAGNUS.md) for replacement commands.

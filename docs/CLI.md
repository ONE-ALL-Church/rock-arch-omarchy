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
When disabled, the command stays installed but its official requests return
`terminal_access_disabled`, so the user has a clear recovery path.

The local Unix account remains the security boundary. The preference controls
the supported CLI, not hostile software already running as that same account.

## Output and lifecycle

Every successful command writes one JSON object to stdout. Errors write one
JSON object to stderr and return nonzero. Output is compact by default for
agents; put `--pretty` before the command for indented output.

```bash
rock-arch status
rock-arch --pretty status --probe-magnus
rock-arch capabilities --refresh
```

The CLI connects to `$XDG_RUNTIME_DIR/rock-arch/broker.sock`. It safely starts
the broker when needed; `--no-start` changes a missing broker into a stable
`broker_unavailable` error. Requests are limited to 16 KiB and responses to
5 MiB. The CLI validates that both the socket and its directory belong to the
current user and are inaccessible to group and other users before connecting.

Search results, Knowledge results, links, files, and build descriptors use
opaque `safeId` values. Use the ID returned by one command in the follow-up
command. IDs are intentionally invalidated when the broker restarts.

## Login and profiles

Login is interactive. The password is read by a masked prompt and is never a
CLI argument or part of JSON output.

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
prompts for any omitted non-secret fields and always prompts for the password.

## Rock search and links

```bash
rock-arch search "Alex Smith"
rock-arch search 42 --entity groups
rock-arch search GUID --entity people
rock-arch person SAFE_ID
rock-arch links personal
rock-arch links recent
rock-arch open SAFE_ID --confirm
rock-arch links activate SAFE_ID --confirm
rock-arch links clear --confirm
```

`--entity` accepts `people`, `groups`, `group-types`, `workflows`, `jobs`,
`pages`, `content-types`, or `content-items`. Search still honors the active
profile's detected Rock permissions and enabled categories. Opening an item,
rerunning a Recent Link, and clearing history require `--confirm` because they
affect the desktop, Rock, or local history.

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
```

Browse first to register folder, file, and mobile-app descriptors as opaque
IDs. Preview is bounded to UTF-8 text. Hash returns SHA-256 and size without
returning file contents. Download writes a new mode-`0600` file without
overwriting; clipboard, browser, and build actions require confirmation. A
build remains limited to a descriptor-advertised numeric mobile-app endpoint.

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

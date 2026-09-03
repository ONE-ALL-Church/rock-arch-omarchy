# Rock Arch design system

Rock Arch is an Omarchy panel first and a Rock RMS utility second. Its visual
language should therefore come from the active Omarchy theme and the shell's
first-party components, not from a parallel application theme.

## Reference surfaces

The primary references are the current Omarchy shell and the Basecamp-owned
plugins that ship the same kind of keyboard-first bar panel:

- [Omarchy shell architecture and theme tokens](https://github.com/basecamp/omarchy/blob/quattro/docs/omarchy-shell.md)
- [Omarchy first-party plugins](https://github.com/basecamp/omarchy/blob/quattro/shell/plugins/README.md)
- [Basecamp notifications for Omarchy](https://github.com/basecamp/omarchy-basecamp-plugin)
- [HEY for Omarchy](https://github.com/basecamp/omarchy-hey-plugin)

The supporting desktop guidance is intentionally narrow and authoritative:

- [GNOME typography](https://developer.gnome.org/hig/guidelines/typography.html)
- [GNOME writing style](https://developer.gnome.org/hig/guidelines/writing-style.html)
- [GNOME boxed lists](https://developer.gnome.org/hig/patterns/containers/boxed-lists.html)
- [GNOME placeholder pages](https://developer.gnome.org/hig/patterns/feedback/placeholders.html)
- [KDE layout and navigation](https://develop.kde.org/hig/layout_and_nav/)
- [KDE accessibility and inclusiveness](https://develop.kde.org/hig/accessibility/)
- [W3C focus appearance guidance](https://www.w3.org/WAI/WCAG22/Understanding/focus-appearance)

## Requirements

### Native theme behavior

- Use `Color`, `Style`, and `Border` roles from `qs.Commons` for every color,
  font size, corner, border, state, gap, and padding that has a shell token.
- Use controls from `qs.Ui` for buttons, text fields, toggles, separators,
  panel headers, focus surfaces, and panel geometry.
- Never assume a dark theme, a particular accent color, rounded corners, or a
  fixed 12 px base font. The active `shell.toml` remains authoritative.
- Reserve custom drawing for the Rock Arch brand mark. Functional icons use
  the same Nerd Font glyph language as the first-party panels.

### Panel anatomy

- Match the first-party utility-panel width of `Style.space(430)` and cap
  content height at `Style.space(600)`.
- Start with a compact hero: Rock Arch mark, product name, and the active
  profile or onboarding purpose.
- Separate the hero from navigation and content with `PanelSeparator`.
- Keep primary navigation on one quiet row. The active destination uses the
  shell's selected state; pointer hover and keyboard focus use the shell's
  hover/focus state.
- Put persistent status in the relevant section. Keep the panel footer for
  transient progress, success, and error messages only.

### Hierarchy and density

- Use only the shell type scale: title for the product, heading for a single
  major task title, body for primary row text, caption/body-small for metadata,
  and `PanelSectionHeader` for section labels.
- Use no more than two weights in one row. Primary text may be semibold; metadata
  is regular and dimmed with the first-party `Qt.darker` treatment.
- Use `Style.spacing.panelGap` between major regions, `rowGap` between rows,
  and `rowPaddingX` inside interactive rows.
- Group related controls closely and separate different groups with space or a
  separator. Do not use decorative cards around every section.

### Lists and selection

- Every searchable, recent, personal-link, Magnus, and profile row shares the
  same `CursorSurface`-equivalent selection treatment.
- The selected row must be visible without changing its text metrics or causing
  reflow. Text always keeps at least `Style.spacing.rowPaddingX` of inset.
- Rows use a title plus one compact metadata line. A third line appears only
  when it materially distinguishes the item, such as person context or the last
  Magnus deployment.
- Long titles and identifiers elide; explanatory text wraps only in detail,
  confirmation, or empty-state regions.

### Controls and settings

- Use quiet, borderless actions for low-risk row commands and bordered controls
  for primary or confirmable actions.
- Preferences are full-width toggle rows with a short title and one useful
  description. Category choices are compact selected buttons, not a loose
  wrap of platform-default checkboxes.
- Destructive actions use `Color.urgent`, require an explicit second action,
  and always support Escape to cancel.
- Profile cards show identity and connection capability first. Management
  actions are visually secondary and use the same action treatment.

### Keyboard and accessibility

- Opening a destination focuses the control or first item most likely to be
  used next.
- Tab, Shift+Tab, arrows, Enter, Space, Backspace, and Escape retain their
  existing behavior across all views.
- Keyboard focus and list selection use the shell's visible focus/cursor tokens;
  focus must never be indicated by color alone or hidden behind clipped content.
- No essential action is available only through hover or a tooltip. Shortcut
  hints may supplement, but never replace, a visible label.

### Copy and states

- Labels use Rock users' vocabulary and say what an action does: `Search`,
  `Open`, `Deploy`, `Sign out`, and `Update`.
- Keep explanatory copy short. Avoid implementation terms such as broker,
  socket, endpoint, descriptor, or synthetic data in normal user-facing UI.
- Loading, empty, signed-out, unavailable, confirmation, success, and error
  states each provide one clear next action when an action is possible.
- Never surface domains, credentials, file contents, or identifiers where they
  are not needed for the current task.

## Panel-specific decisions

- **Onboarding:** one focused connection task with four labeled fields and one
  primary Connect action, followed by one Finish setup screen for search
  categories and the optional automatic-update choice when the install supports
  it. The primary action continues to Search; no application navigation
  competes with the active onboarding step.
- **Search:** search input first, then either Recent Links or Rock results. It
  contains no public-KB control or tutorial copy. Person context stays attached
  to the person result instead of becoming a competing card.
- **Knowledge:** a dedicated top-level workspace visibly explains that its query
  goes to a public service. Its empty state teaches the supported area prefixes
  without crowding Search. Results reuse the standard selected-row treatment;
  Enter opens a plain-text detail with trust/version context, Back, and Open
  source. Typed related items continue within the panel, and Back unwinds that
  detail history before returning to results.
- **Personal Links:** a single bookmark list with section metadata; no repeated
  keyboard tutorial below the list.
- **Magnus:** breadcrumb/task title plus Refresh, a shared list treatment, and a
  bounded preview. Deploy remains the only server-side action and keeps a
  dedicated production confirmation.
- **Settings:** profiles, preferences, categories, and updates are four visibly
  separate groups. The active profile includes Magnus availability so there is
  no redundant Connection section.

# Keyboard navigation contract

Updated 2026-09-08. This replaces the earlier model that used Tab to cycle
workspaces. Switching workspaces, moving focus between controls, and selecting
items now have separate keyboard paths.

## Shared navigation

The panel keeps a stable order: header, workspace tabs, workspace controls,
content. Search opens with the input focused. The tab bar is one focus stop:
Shift+Tab from the first workspace control reaches it; Left/Right selects tabs,
Home/End selects the first/last, and Tab enters that workspace.

| Key | Behavior |
|---|---|
| Ctrl+Tab / Ctrl+Shift+Tab | Next/previous visible workspace, wrapping in the user's saved order |
| Ctrl+1…4 | Direct visible workspace position; unavailable Magnus takes no number |
| Tab / Shift+Tab | Next/previous visible enabled control; composite lists and choices have one stop |
| Arrows | Select tabs, list rows, section children, view choices or adjacent confirmation buttons |
| Ctrl+F | Focus Search/Knowledge input, or the existing Model Map filter in detail |
| Ctrl+, | Settings; Escape restores the previous workspace |
| F1 | Keyboard and search help; also reachable from Settings |
| Escape | Close the innermost menu, confirmation or detail; at workspace root close the panel |

Settings is not part of the workspace cycle. From Settings, Ctrl+Tab cycles
relative to the workspace that opened it. Workspace changes retain selection,
query, inline detail, scroll and valid content focus. A tab selected with arrows
keeps focus on the tab bar until the user enters its content.

## Flow paths

1. **Search and Recent:** input → list → available selected-row actions. Down
   enters results; Up from the first result returns to the input. List boundaries
   never switch workspaces. Ctrl+B bookmarks a result or Recent Link; R prepares a permitted job run.
   Recent rows select on click and open on Enter or double-click. Backspace from a selected
   row resumes editing. Modified editing keys retain their native behavior.
2. **Links:** Sections/A–Z choice → Add → sections/links → selected-item action.
   Left/Right operates the focused choice or expands/collapses sections. Tab does
   not create a loop isolated from the header. Ctrl+N opens Add; Escape closes its
   menu and returns to Add. Expansion preferences remain persisted.
3. **Add link/section:** Tab follows the visible fields and actions; Ctrl+S saves
   the current form. In-memory drafts survive switching workspaces. Closing the
   panel, changing profile/context, signing out or cancelling clears them. A new
   bookmark does not silently overwrite an existing unfinished form. Passwords
   are cleared when leaving Settings, rather than retained as drafts.
4. **Knowledge:** query → results → inline detail. Result boundaries stay within
   Knowledge. Detail provides Back, source, model-map controls and related items.
   Escape walks the detail history and restores the originating position.
5. **Magnus:** folder toolbar → list → selected actions; previews expose their
   actions and selectable text. Folder return restores the previous cursor and
   scroll. Ctrl+Tab works from preview text. Single-letter commands ignore
   Ctrl/Alt/Meta so they do not intercept clipboard or editing shortcuts.
6. **Confirmations:** Cancel receives initial focus for link/section deletion,
   job triggering, deployment, history clearing, sign-out and profile removal.
   Adjacent buttons support Left/Right and Tab. Enter activates only the focused
   action. Workspace shortcuts are consumed without switching or moving local
   focus. Escape cancels/dismisses the surface; dismissing remote-job status does
   not claim to cancel a job already requested.
7. **Settings and onboarding:** visible controls follow their visual order and
   focused controls scroll into view. Reordering tabs preserves focus on the
   moved entry. Onboarding and confirmations temporarily suspend workspace
   navigation. Settings returns to its initiating workspace rather than forcing
   Search every time.

## Search hints

The People / Groups / More row has been removed. Search uses stable placeholder
examples drawn only from available enabled categories. F1 or Settings exposes
all available prefixes and existing Alt shortcuts, and categories can be chosen
there. There is no timed hint rotation. The accessible input name remains
“Search Rock”; an active scope has a focusable clear control and Alt+0.

## Verification

- `scripts/check-qml`: Qt state, focus-composite and modifier-dispatch tests.
- `scripts/check-keyboard`: loads the current plugin and Omarchy's actual UI
  controls in an isolated offscreen Quickshell process. An inert broker and a
  plain Qt window replace authenticated transport and the layer-shell window.
  QtTest sends real key events across fields, tab buttons, toolbars, lists,
  detail, preview text, drafts, Settings and confirmations. Fixtures contain no
  user data, and the broker performs no operations.
- `scripts/check-socket`: a delayed local server exercises the actual Quickshell
  Socket error/recovery path, without starting an authenticated broker.
- `python -B -m unittest discover -s tests`: broker and distribution regression
  coverage plus the existing QML source contracts.

The offscreen harness verifies Qt interaction and cross-window shortcut scope;
it does not simulate Hyprland's layer-shell focus acquisition or constitute an
accessibility certification. Live installed-panel screenshots verify layout and
loading separately. A physical keyboard walkthrough remains useful for the
compositor-specific experience.

## Design references

The installed Omarchy `Ui/Button.qml`, `Ui/PanelKeyCatcher.qml` and clock-panel
form provide native controls and compact panel conventions. The generic key
catcher is not a complete navigation policy for a multi-workspace plugin.

[WAI keyboard-interface guidance](https://www.w3.org/WAI/ARIA/apg/practices/keyboard-interface/)
and the [tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) inform the
separation of Tab traversal from arrow navigation. These conventions are adapted
to native Qt, rather than presented as ARIA conformance.
[Qt focus](https://doc.qt.io/qt-6/qtquick-input-focus.html) and
[Qt Shortcut](https://doc.qt.io/qt-6/qml-qtquick-shortcut.html) explain the focused
item's key dispatch and application-scoped shortcuts used here.

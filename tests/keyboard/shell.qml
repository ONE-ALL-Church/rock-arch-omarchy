import QtQuick
import Quickshell
import QtTest

ShellRoot {
  Window {
    visible: true
    width: 100; height: 30
    RockArch { id: rock; contextName: "DEV"; Component.onCompleted: open() }
  }
  TestCase {
    id: tester
    name: "InstalledKeyboardComponents"
    when: false
    optional: true
    function expect(value, message) {
      if (!value) throw new Error(message + " " + JSON.stringify(rock.testSnapshot()))
    }
    function press(key, mods) { keyClick(key, mods || Qt.NoModifier); wait(30) }
    function runChecks() {
      rock.testShowWindow(); wait(100)
      expect(rock.viewMode === "search", "Start Search")
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "personal", "Ctrl+Tab from Search input")
      press(Qt.Key_Backtab, Qt.ControlModifier | Qt.ShiftModifier)
      expect(rock.viewMode === "search", "Reverse Ctrl+Tab")
      press(Qt.Key_Backtab, Qt.ShiftModifier)
      expect(rock.testSnapshot().tabs, "Shift+Tab enters tab bar")
      press(Qt.Key_Right)
      expect(rock.viewMode === "personal" && rock.testSnapshot().tabs, "Arrow selects tab")
      press(Qt.Key_Tab)
      expect(rock.viewMode === "personal" && !rock.testSnapshot().tabs, "Tab enters content")
      press(Qt.Key_Backtab, Qt.ShiftModifier)
      expect(rock.testSnapshot().tabs, "Toolbar returns to tabs")
      press(Qt.Key_Home)
      expect(rock.viewMode === "search", "Home selects first tab")
      press(Qt.Key_End)
      expect(rock.viewMode === "magnus", "End selects last tab")
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "search", "Cycle skips Settings")
      rock.openSettings(false); wait(30)
      press(Qt.Key_Escape)
      expect(rock.viewMode === "search", "Settings escape restores")
      press(Qt.Key_F1)
      expect(rock.keyboardHelpVisible, "F1 opens help")
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.keyboardHelpVisible && rock.viewMode === "search", "Help modal")
      press(Qt.Key_Escape)
      expect(!rock.keyboardHelpVisible, "Escape help")

      // Deterministic data only. The broker in this harness is inert.
      rock.query = "fixture"
      rock.resultsQuery = "fixture"
      rock.results = [{title: "Example", category: "People", subtitle: "Fixture", status: "Preview", safeId: "fixture", canOpen: true}]
      rock.testFocusField(); wait(30)
      press(Qt.Key_Down)
      expect(rock.testSnapshot().list && rock.resultCursor === 0, "Down enters results")
      press(Qt.Key_Down)
      expect(rock.viewMode === "search" && rock.resultCursor === 0, "Search boundary")
      press(Qt.Key_Tab, Qt.ControlModifier)
      press(Qt.Key_Backtab, Qt.ControlModifier | Qt.ShiftModifier)
      expect(rock.testSnapshot().list && rock.query === "fixture", "Restore result focus and query")
      press(Qt.Key_Up)
      expect(rock.testSnapshot().field, "Up returns to input")
      press(Qt.Key_A, Qt.ControlModifier)
      press(Qt.Key_Backspace, Qt.ControlModifier)
      expect(rock.query === "", "Native select all and modified deletion")

      rock.openTab("knowledge"); wait(30)
      rock.knowledgeResults = [{title: "Model", kind: "Model Map", summary: "Fixture", safeId: "model"}]
      press(Qt.Key_Down)
      press(Qt.Key_Down)
      expect(rock.viewMode === "knowledge" && rock.knowledgeCursor === 0, "Knowledge boundary")
      rock.knowledgeDetail = {title: "Example", kind: "Model Map", trust: "Public", claimTier: "Reference", version: "1", body: "Fixture", links: [], attribution: "Fixture", canOpenSource: true}
      rock.testFocusDetail(); wait(30)
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "magnus", "Ctrl+Tab from detail")
      rock.magnusBusy = false
      rock.magnusItems = [{title: "file.txt", subtitle: "Fixture", kind: "file", safeId: "file", isDirectory: false, actions: []}]
      rock.focusList(); wait(30)
      press(Qt.Key_Down)
      expect(rock.viewMode === "magnus" && rock.magnusCursor === 0, "Magnus boundary")
      rock.magnusPreview = {title: "file.txt", sha256: "fixture", content: "Example", previewAvailable: true, actions: ["copy", "view"]}
      rock.testFocusMagnusText(); wait(30)
      expect(rock.testSnapshot().magnusText, "Preview text receives focus")
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "search", "Ctrl+Tab from preview text")
      press(Qt.Key_Backtab, Qt.ControlModifier | Qt.ShiftModifier)
      expect(rock.viewMode === "magnus" && rock.magnusPreview !== null, "Preview retained")
      rock.magnusPreview = null
      rock.prepareMagnusBuild("fixture-build", "Fixture app", false); wait(30)
      expect(rock.testSnapshot().buildCancel, "Deploy starts on Cancel")
      press(Qt.Key_Tab, Qt.ControlModifier)
      press(Qt.Key_1, Qt.ControlModifier)
      expect(rock.viewMode === "magnus" && rock.testSnapshot().buildCancel, "All workspace shortcuts blocked by confirmation")
      press(Qt.Key_Tab)
      expect(!rock.testSnapshot().buildCancel, "Tab reaches Deploy")
      press(Qt.Key_Escape)
      expect(rock.pendingMagnusBuildId === "", "Escape cancels Deploy")

      // A private-link draft survives ordinary workspace navigation.
      rock.openTab("personal"); wait(30)
      rock.personalLink.beginSection()
      rock.personalLink.busy = false
      rock.personalLink.name = "Unfinished section"
      wait(30)
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "knowledge" && rock.personalLink.editing, "Draft survives switching")
      press(Qt.Key_Backtab, Qt.ControlModifier | Qt.ShiftModifier)
      expect(rock.viewMode === "personal" && rock.personalLink.name === "Unfinished section" && rock.testSnapshot().name, "Draft focus restored")
      press(Qt.Key_Escape)
      expect(!rock.personalLink.editing, "Escape cancels current form")

      rock.tabOrder = ["knowledge", "search", "personal", "magnus"]
      rock.openTab("knowledge"); wait(30)
      rock.openKnowledge("new query"); wait(30)
      expect(rock.knowledgeDetail === null && rock.knowledgeQuery === "new query", "Explicit knowledge query leaves prior detail")
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "search", "Custom order used by Ctrl+Tab")
      press(Qt.Key_3, Qt.ControlModifier)
      expect(rock.viewMode === "personal", "Custom order used by numbered shortcut")
      rock.openSettings(false); wait(30)
      press(Qt.Key_Escape)
      expect(rock.viewMode === "personal", "Settings returns to previous workspace")
      rock.openTab("search"); wait(30)
      rock.query = ""
      rock.quickReturns = [{title: "Fixture recent", subtitle: "Fixture", kind: "Page", safeId: "recent"}]
      rock.clearRecentLinks(); wait(30)
      expect(rock.testSnapshot().clearCancel, "Clear history starts on Cancel")
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "search", "Clear history blocks switching")
      press(Qt.Key_Escape)
      expect(!rock.pendingClearRecent, "Escape cancels history clear")
      // Account/settings confirmations and job actions use the same guard.
      rock.contextName = "PROD"
      rock.preferenceOnboardingSetupCompleted = true
      rock.rockConfigured = true
      rock.statusLoaded = true
      rock.profilesLoaded = true
      rock.profiles = [{id: "fixture-profile", name: "Fixture Church", domain: "example.invalid", isActive: true, configured: true}]
      rock.openTab("personal"); wait(30)
      press(Qt.Key_N, Qt.ControlModifier)
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "knowledge", "Ctrl+Tab from Add popup")
      rock.openSettings(false); wait(30)
      rock.removeProfile("fixture-profile"); wait(30)
      expect(rock.focusStops().length === 2, "Profile confirmation has Cancel and Remove")
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "settings", "Profile confirmation blocks switching")
      press(Qt.Key_Escape)
      expect(rock.pendingRemoveProfileId === "", "Escape cancels profile removal")
      rock.openTab("search"); wait(30)
      rock.query = ""
      rock.quickReturns = [{title: "Fixture job", kind: "Scheduled Job", safeId: "quick-job"}]
      rock.job.available = true
      rock.selectRecent(0); wait(30)
      expect(rock.testSnapshot().list, "Recent selection focuses list")
      press(Qt.Key_Tab)
      expect(rock.activeFocusItem.text === "Run", "Recent Tab reaches Run")
      press(Qt.Key_Tab)
      expect(rock.activeFocusItem.Accessible.name === "Add bookmark", "Recent Tab reaches Bookmark")
      press(Qt.Key_Tab)
      expect(rock.activeFocusItem.text === "Open", "Recent Tab reaches Open")
      rock.preferenceCloseAfterOpen = false
      press(Qt.Key_Return)
      expect(rock.testRequests().slice(-1)[0].op === "activate_recent", "Recent Enter opens without triggering")
      rock.selectRecent(0); wait(30)
      press(Qt.Key_R)
      expect(rock.job.editing && rock.job.safeId === "quick-job", "R prepares selected recent job")
      expect(rock.testRequests().slice(-1)[0].op === "job_prepare", "Recent Run uses confirmation preparation")
      press(Qt.Key_Escape)
      rock.selectRecent(0); wait(30)
      press(Qt.Key_B, Qt.ControlModifier)
      expect(rock.personalLink.editing && rock.viewMode === "personal", "Ctrl+B bookmarks recent item")
      expect(rock.testRequests().slice(-1)[0].safeId === "quick-job", "Bookmark uses opaque recent reference")
      press(Qt.Key_Escape)
      rock.openTab("search"); wait(30)
      rock.job.available = false
      rock.selectRecent(0); wait(30)
      press(Qt.Key_Tab)
      expect(rock.activeFocusItem.Accessible.name === "Add bookmark", "Denied job access omits Run action")
      rock.job.editing = true
      rock.job.phase = "confirm"
      rock.job.draftId = "fixture-draft"
      rock.job.title = "Fixture job"
      rock.job.confirmationReady(); wait(30)
      expect(rock.testSnapshot().jobCancel, "Job starts on Cancel")
      press(Qt.Key_Tab, Qt.ControlModifier)
      press(Qt.Key_2, Qt.ControlModifier)
      expect(rock.viewMode === "search" && rock.testSnapshot().jobCancel, "Job confirmation blocks all workspace shortcuts")
      press(Qt.Key_Right)
      expect(!rock.testSnapshot().jobCancel, "Right reaches Run")
      press(Qt.Key_Escape)
      expect(!rock.job.editing, "Escape cancels job confirmation")
      rock.rockConfigured = false
      rock.openTab("knowledge")
      expect(rock.viewMode === "search", "Onboarding blocks switching")
      rock.rockConfigured = true
      rock.magnusAvailable = false
      rock.magnusState = "unavailable"
      rock.openTab("personal"); wait(30)
      press(Qt.Key_Tab, Qt.ControlModifier)
      expect(rock.viewMode === "knowledge", "Unavailable Magnus is omitted from cycle")
      console.log("KEYBOARD_INTEGRATION_PASS")
    }
  }
  Timer {
    interval: 500; running: true
    onTriggered: {
      try { tester.runChecks() }
      catch (error) { console.log("KEYBOARD_INTEGRATION_FAIL", error) }
      Qt.quit()
    }
  }
}

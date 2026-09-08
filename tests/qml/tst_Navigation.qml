import QtQuick
import QtTest
import "../../plugin/oneall.rock-arch/RockArchNavigation.js" as Navigation
import "../../plugin/oneall.rock-arch/RockArchSearchScopes.js" as Scopes

TestCase {
  name: "Navigation"

  function test_numbered_shortcuts_follow_custom_visible_order() {
    var order = ["magnus", "knowledge", "search", "personal"]
    var tabs = Navigation.tabs(order, true)
    compare(tabs.map(function(tab) { return tab.key }), order)
    compare(tabs.map(function(tab) { return tab.shortcut }), ["Ctrl+1", "Ctrl+2", "Ctrl+3", "Ctrl+4"])
    tabs = Navigation.tabs(order, false)
    compare(tabs.map(function(tab) { return tab.key }), ["knowledge", "search", "personal"])
    compare(tabs.map(function(tab) { return tab.shortcut }), ["Ctrl+1", "Ctrl+2", "Ctrl+3"])
    compare(order, ["magnus", "knowledge", "search", "personal"])
  }

  function test_tab_cycle_uses_only_visible_workspaces() {
    var tabs = Navigation.tabs(["personal", "magnus", "search", "knowledge"], true)
    compare(Navigation.adjacent(tabs, "knowledge", 1), "personal")
    compare(Navigation.adjacent(tabs, "personal", -1), "knowledge")
    compare(Navigation.adjacent(tabs, "settings", 1), "personal")
    compare(Navigation.adjacent([], "search", 1), "")
    tabs = Navigation.tabs(["personal", "magnus", "search", "knowledge"], false)
    compare(Navigation.adjacent(tabs, "personal", 1), "search")
  }

  function test_reorder_is_bounded_and_preserves_every_tab() {
    var order = Navigation.defaultOrder()
    compare(Navigation.moved(order, "search", -1), order)
    compare(Navigation.moved(order, "magnus", 1), order)
    compare(Navigation.moved(order, "missing", 1), order)
    compare(Navigation.moved(order, "knowledge", -1), ["search", "knowledge", "personal", "magnus"])
    compare(order, Navigation.defaultOrder())
    compare(Navigation.normalize(["knowledge", "knowledge", "invalid"]), ["knowledge", "search", "personal", "magnus"])
  }

  function test_hints_only_expose_enabled_accessible_categories() {
    var options = Scopes.options(["People", "Groups", "Pages"], ["Groups", "Pages", "Jobs"])
    compare(options.map(function(item) { return item.prefix }), ["g", "pg"])
    compare(Scopes.options(["People"], []), [])
  }

  function test_every_displayed_prefix_maps_to_its_category() {
    var categories = ["People", "Groups", "Group Types", "Defined Types", "Workflows", "Jobs", "Pages", "Content Channel Types", "Content Channel Items"]
    for (var option of Scopes.options(categories, categories)) {
      var key = Scopes.keyForQuery(option.prefix + ": query")
      compare(key, option.prefix)
      compare(Scopes.categoryForKey(key), option.category)
      verify(Scopes.labelForKey(key).length > 0)
      compare(Scopes.withoutScope(option.prefix + ": query"), "query")
    }
    for (var definedQuery of ["dt: 1", "definedtype: 1", "definedtypes: 1"])
      compare(Scopes.categoryForKey(Scopes.keyForQuery(definedQuery)), "Defined Types")
    for (var query of ["pg: 1", "page: 1", "pages: 1"])
      compare(Scopes.categoryForKey(Scopes.keyForQuery(query)), "Pages")
  }
}

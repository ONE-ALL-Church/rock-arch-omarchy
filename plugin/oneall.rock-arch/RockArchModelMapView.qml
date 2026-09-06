import QtQml

// Pure reader state: filtering never changes the server result or follows a URL.
QtObject {
  id: view
  property var detail: null
  property string filter: ""
  property var expanded: ["properties"]
  readonly property bool filtering: filter.trim().length > 0
  readonly property var sections: {
    var source = detail && Array.isArray(detail.modelSections) ? detail.modelSections : []
    var terms = filter.toLowerCase().trim().split(/\s+/).filter(function(term) { return term.length > 0 })
    return source.map(function(section) {
      var rows = (section.rows || []).filter(function(row) {
        var text = [row.title, row.subtitle, row.body].join(" ").toLowerCase()
        return terms.every(function(term) { return text.indexOf(term) >= 0 })
      })
      return {key: section.key, title: section.title, total: section.total,
        rows: rows, notice: section.notice || ""}
    })
  }
  onDetailChanged: {
    filter = ""
    expanded = ["properties"]
  }
  function isExpanded(key) { return filtering || expanded.indexOf(key) >= 0 }
  function setExpanded(key, open) {
    expanded = expanded.filter(function(item) { return item !== key }).concat(open ? [key] : [])
  }
}

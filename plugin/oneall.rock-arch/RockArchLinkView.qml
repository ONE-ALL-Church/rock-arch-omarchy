import QtQml

QtObject {
  id: state
  property var links: []
  property var sections: []
  property string mode: "groups"
  property var expandedGroups: []
  property int cursor: -1
  readonly property var groups: grouped()
  readonly property var rows: visibleRows()
  signal expandedChanged(var groups)
  signal openRequested(string safeId)
  signal addLinkRequested(string sectionId)
  signal focusRequested()

  function groupId(link) {
    return String(link.groupId || ("preview:" + JSON.stringify([link.section, !!link.isShared])))
  }
  function linkRow(link) {
    return Object.assign({}, link, {group: false, key: "link:" + (link.deleteId || link.safeId) + ":" + groupId(link), sectionId: groupId(link)})
  }
  function grouped() {
    var result = []
    links.forEach(function(link) {
      var id = groupId(link)
      var group = result.find(function(item) { return item.sectionId === id })
      if (group) group.count++
      else result.push({group: true, key: "group:" + id, sectionId: id,
        title: link.section, isShared: !!link.isShared, count: 1})
    })
    sections.forEach(function(section) {
      var group = result.find(function(item) { return item.sectionId === section.groupId })
      if (group) group.sectionSafeId = section.safeId
      else result.push({group: true, key: "group:" + section.groupId, sectionId: section.groupId,
        title: section.name, isShared: false, count: 0, sectionSafeId: section.safeId})
    })
    return result
  }
  function visibleRows() {
    if (mode === "alpha") {
      return links.map(linkRow).sort(function(a, b) {
        return String(a.title).toLocaleLowerCase().localeCompare(String(b.title).toLocaleLowerCase()) ||
          String(a.section).toLocaleLowerCase().localeCompare(String(b.section).toLocaleLowerCase()) || a.key.localeCompare(b.key)
      })
    }
    var result = []
    groups.forEach(function(group) {
      var expanded = expandedGroups.indexOf(group.sectionId) >= 0
      result.push(Object.assign({}, group, {expanded: expanded}))
      if (expanded) links.forEach(function(link) {
        if (groupId(link) === group.sectionId) result.push(linkRow(link))
      })
      if (expanded && group.count === 0 && group.sectionSafeId)
        result.push({group: false, empty: true, key: "empty:" + group.sectionId, sectionId: group.sectionId,
          title: "Add a link", sectionSafeId: group.sectionSafeId})
    })
    return result
  }
  function deletionTarget(item) {
    if (!item || item.empty || item.isShared) return null
    if (item.group) return item.count === 0 && item.sectionSafeId ? {kind: "section", targetId: item.sectionSafeId} : null
    return item.deleteId && sections.some(function(section) { return section.groupId === item.sectionId })
      ? {kind: "link", targetId: item.deleteId} : null
  }
  function selected() { return cursor >= 0 && cursor < rows.length ? rows[cursor] : null }
  function restoreSelection(item) {
    var index = item ? rows.findIndex(function(row) { return row.key === item.key }) : -1
    if (index < 0 && item) index = rows.findIndex(function(row) { return row.sectionId === item.sectionId })
    cursor = index >= 0 ? index : (rows.length ? 0 : -1)
  }
  function configure(view, expanded) {
    var item = selected()
    mode = view === "alpha" ? "alpha" : "groups"
    var next = Array.isArray(expanded) ? expanded : []
    if (JSON.stringify(expandedGroups) !== JSON.stringify(next)) expandedGroups = next.slice()
    restoreSelection(item)
  }
  function replace(value, saved, catalog) {
    var item = selected()
    links = value
    if (Array.isArray(catalog)) sections = catalog
    if (saved && saved.kind === "section") {
      var section = groups.find(function(candidate) { return candidate.sectionId === saved.groupId })
      if (section) { item = section; expand(section.sectionId, true) }
    } else if (saved) {
      var link = links.find(function(candidate) {
        return candidate.title === saved.name && candidate.section === saved.section && !candidate.isShared
      })
      if (link) {
        item = linkRow(link)
        if (mode === "groups") expand(item.sectionId, true)
      }
    }
    restoreSelection(item)
  }
  function expand(id, open) {
    if ((expandedGroups.indexOf(id) >= 0) === open) return
    var next = expandedGroups.filter(function(value) { return value !== id })
    if (open) next.push(id)
    if (JSON.stringify(next) === JSON.stringify(expandedGroups)) return
    expandedGroups = next
    expandedChanged(next.slice())
  }
  function activate(index) {
    if (index < 0 || index >= rows.length) return
    cursor = index
    var item = rows[index]
    if (item.empty) { addLinkRequested(item.sectionSafeId); return }
    if (!item.group) { openRequested(item.safeId); return }
    expand(item.sectionId, !item.expanded)
    restoreSelection(item)
    focusRequested()
  }
  function horizontal(direction) {
    var item = selected()
    if (mode !== "groups" || !item) return false
    if (direction > 0 && item.group) {
      if (item.expanded && cursor + 1 < rows.length && rows[cursor + 1].sectionId === item.sectionId && !rows[cursor + 1].group) cursor++
      else { expand(item.sectionId, true); restoreSelection(item) }
    } else if (direction < 0) {
      if (item.group) expand(item.sectionId, false)
      restoreSelection({key: "group:" + item.sectionId, sectionId: item.sectionId})
    }
    focusRequested()
    return true
  }
}

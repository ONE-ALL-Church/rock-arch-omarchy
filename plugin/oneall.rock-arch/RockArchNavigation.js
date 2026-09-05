.pragma library

function defaultOrder() { return ["search", "personal", "knowledge", "magnus"] }

function normalize(order) {
  var defaults = defaultOrder()
  var result = []
  if (Array.isArray(order)) {
    for (var key of order)
      if (defaults.indexOf(key) >= 0 && result.indexOf(key) < 0) result.push(key)
  }
  return result.concat(defaults.filter(function(key) { return result.indexOf(key) < 0 }))
}

function label(key) {
  return {search: "Search", personal: "Links", knowledge: "Knowledge", magnus: "Magnus"}[key] || ""
}

function tabs(order, showMagnus) {
  return normalize(order).filter(function(key) {
    return key !== "magnus" || showMagnus
  }).map(function(key, index) {
    return {key: key, label: label(key), shortcut: "Ctrl+" + (index + 1)}
  })
}

function moved(order, key, direction) {
  var result = normalize(order)
  var index = result.indexOf(key)
  var next = index + direction
  if ((direction !== -1 && direction !== 1) || index < 0 || next < 0 || next >= result.length)
    return result
  result.splice(index, 1)
  result.splice(next, 0, key)
  return result
}

function adjacent(tabs, current, direction) {
  var keys = tabs.map(function(tab) { return tab.key }).concat(["settings"])
  var index = keys.indexOf(current)
  return keys[(index + direction + keys.length) % keys.length]
}

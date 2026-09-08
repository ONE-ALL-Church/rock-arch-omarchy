.pragma library

// A composite (tab strip, list, view choice) contributes one stop. Ordinary
// controls follow their visual tree order; hidden/disabled subtrees are skipped.
function stops(item) {
  if (!item || !item.visible || !item.enabled) return []
  if (item.activeFocusOnTab) return [item]
  var result = []
  var children = item.children || []
  for (var index = 0; index < children.length; ++index)
    result = result.concat(stops(children[index]))
  return result
}

function contains(parent, item) {
  for (var current = item; current; current = current.parent)
    if (current === parent) return true
  return false
}

function next(items, current, direction) {
  if (!items.length) return null
  var index = items.findIndex(function(item) { return contains(item, current) })
  if (index < 0) return direction < 0 ? items[items.length - 1] : items[0]
  return items[(index + direction + items.length) % items.length]
}

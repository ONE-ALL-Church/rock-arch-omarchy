.pragma library

function keyForQuery(value) {
  var text = String(value || "")
  var colon = text.indexOf(":")
  if (colon < 1) return ""
  var prefix = text.substring(0, colon).trim().toLowerCase()
  if (prefix === "p" || prefix === "person" || prefix === "people") return "p"
  if (prefix === "g" || prefix === "group" || prefix === "groups") return "g"
  if (prefix === "gt" || prefix === "grouptype" || prefix === "grouptypes") return "gt"
  if (prefix === "w" || prefix === "wt" || prefix === "workflow" ||
      prefix === "workflows" || prefix === "workflowtype" ||
      prefix === "workflowtypes") return "w"
  if (prefix === "j" || prefix === "job" || prefix === "jobs") return "j"
  if (prefix === "pg" || prefix === "page" || prefix === "pages") return "page"
  if (prefix === "ct" || prefix === "contenttype" || prefix === "contenttypes" ||
      prefix === "channeltype" || prefix === "channeltypes") return "ct"
  if (prefix === "c" || prefix === "content" || prefix === "contents" ||
      prefix === "item" || prefix === "items") return "c"
  if (prefix === "kb" || prefix === "knowledge") return "kb"
  return ""
}

function labelForKey(key) {
  if (key === "p") return "People"
  if (key === "g") return "Groups"
  if (key === "gt") return "Group Types"
  if (key === "w") return "Workflow Types"
  if (key === "j") return "Jobs"
  if (key === "page") return "Pages"
  if (key === "ct") return "Content Channel Types"
  if (key === "c") return "Content"
  if (key === "kb") return "Knowledge"
  return ""
}

function categoryForKey(key) {
  if (key === "p") return "People"
  if (key === "g") return "Groups"
  if (key === "gt") return "Group Types"
  if (key === "w") return "Workflows"
  if (key === "j") return "Jobs"
  if (key === "page") return "Pages"
  if (key === "ct") return "Content Channel Types"
  if (key === "c") return "Content Channel Items"
  return ""
}

function withoutScope(value) {
  var text = String(value || "")
  if (!keyForQuery(text)) return text.trim()
  return text.substring(text.indexOf(":") + 1).trim()
}

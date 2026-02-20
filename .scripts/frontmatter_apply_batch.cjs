const fs = require('fs')
const path = require('path')
const yaml = require('js-yaml')

const batchFile = process.argv[2]
if (!batchFile) {
  console.error('Usage: node .scripts/frontmatter_apply_batch.js <batch_file>')
  process.exit(1)
}
const outDir = '.scripts/out/frontmatter'
fs.mkdirSync(outDir, { recursive: true })

const UPDATED = '2026-02-12'

function inferDomain(file) {
  const p = file.toLowerCase()
  if (/databases|database|postgresql|sql server|\bsql\b/.test(p)) return 'Databases'
  if (/data engineering|etl|elt|pipeline|data lake|warehouse|analytics|bigquery|redshift|glue/.test(p)) return 'Data-Engineering'
  if (/system design|architecture/.test(p)) return 'System-Design'
  if (/devops|github actions|docker|kubernetes|bash|powershell|\bcmd\b|cloud sdks|aws|azure|gcp|registry/.test(p)) return 'DevOps'
  return 'Software-Development'
}

function inferType(file) {
  const base = path.basename(file)
  if (/\/mocs\//i.test(file) || /moc/i.test(base)) return 'MOC'
  if (file.startsWith('0-Slipbox/')) return 'Atomic-Note'
  if (file.startsWith('2-Areas/Code/')) {
    if (/^_?readme\.md$/i.test(base)) return 'Guide'
    return 'Pattern'
  }
  return 'Guide'
}

function inferRelatedMoc(domain) {
  const map = {
    'Software-Development': '[[Software Development]]',
    'Data-Engineering': '[[Data Engineering]]',
    'Databases': '[[Databases]]',
    'DevOps': '[[Development]]',
    'System-Design': '[[Development]]',
  }
  return map[domain] || '[[Development]]'
}

function parseFrontmatter(text) {
  if (!text.startsWith('---\n')) return { fm: null, body: text }
  const end = text.indexOf('\n---\n', 4)
  if (end === -1) return { fm: null, body: text }
  const raw = text.slice(4, end)
  const body = text.slice(end + 5)
  try {
    const parsed = yaml.load(raw) || {}
    if (typeof parsed !== 'object' || Array.isArray(parsed)) return { fm: {}, body }
    return { fm: parsed, body }
  } catch {
    return { fm: null, body: text }
  }
}

function asTags(v) {
  if (Array.isArray(v)) return v.map(String)
  if (typeof v === 'string' && v.trim()) return [v.trim()]
  return []
}

const files = fs
  .readFileSync(batchFile, 'utf8')
  .split(/\r?\n/)
  .map((s) => s.trim())
  .filter(Boolean)

let modified = []
let skipped = []

for (const file of files) {
  if (!fs.existsSync(file)) {
    skipped.push(`${file} (missing)`)
    continue
  }
  const original = fs.readFileSync(file, 'utf8')
  const { fm, body } = parseFrontmatter(original)

  if (fm === null && original.startsWith('---\n')) {
    skipped.push(`${file} (unparseable frontmatter)`)
    continue
  }

  const type = inferType(file)
  const domain = inferDomain(file)
  const related = inferRelatedMoc(domain)
  const inferredTags = [`kb/ontology`, `type/${type}`, `domain/${domain}`]

  const next = fm ? { ...fm } : {}
  if (!next.type) next.type = type
  if (!next.domain) next.domain = domain
  const mergedTags = [...new Set([...asTags(next.tags), ...inferredTags])]
  next.tags = mergedTags
  if (!next.status) next.status = 'living'
  if (!next.related_moc) next.related_moc = related
  if (!next.updated) next.updated = UPDATED

  const dumped = yaml.dump(next, {
    lineWidth: -1,
    noRefs: true,
    sortKeys: false,
  })
  const nextText = `---\n${dumped}---\n\n${body.replace(/^\n+/, '')}`

  if (nextText !== original) {
    fs.writeFileSync(file, nextText)
    modified.push(file)
  }
}

const batchName = path.basename(batchFile, '.txt')
fs.writeFileSync(`${outDir}/${batchName}_modified.txt`, modified.join('\n') + (modified.length ? '\n' : ''))
fs.writeFileSync(`${outDir}/${batchName}_skipped.txt`, skipped.join('\n') + (skipped.length ? '\n' : ''))

const summaryRow = `${batchName},${files.length},${modified.length},${skipped.length}\n`
const summaryPath = `${outDir}/batches_summary.csv`
if (!fs.existsSync(summaryPath)) fs.writeFileSync(summaryPath, 'batch,total,modified,skipped\n')
fs.appendFileSync(summaryPath, summaryRow)

console.log(`${batchName}: total=${files.length} modified=${modified.length} skipped=${skipped.length}`)

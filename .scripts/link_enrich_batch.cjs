const fs = require('fs')
const path = require('path')
const yaml = require('js-yaml')

const mode = process.argv[2] // dry-run | apply
const batchFile = process.argv[3]
if (!mode || !batchFile || !['dry-run', 'apply'].includes(mode)) {
  console.error('Usage: node .scripts/link_enrich_batch.cjs <dry-run|apply> <batch_file>')
  process.exit(1)
}

const outDir = '.scripts/out/linking'
fs.mkdirSync(outDir, { recursive: true })

const ontologyLinks = [
  '[[Ontology-Overview]]',
  '[[Document-Types]]',
  '[[Core-Domains]]',
  '[[Glossary-Key-Terms]]',
]

const domainToMoc = {
  'Software-Development': '[[Software Development]]',
  'Data-Engineering': '[[Data Engineering]]',
  'Databases': '[[Databases]]',
  DevOps: '[[Development]]',
  'System-Design': '[[Development]]',
}

const termRules = [
  ['event-driven architecture', '[[Event-Driven Architecture]]'],
  ['cap theorem', '[[CAP Theorem]]'],
  ['consistent hashing', '[[Consistent Hashing]]'],
  ['domain-driven design', '[[Domain-Driven Design]]'],
  ['microservices architecture', '[[Microservices Architecture]]'],
  ['system design', '[[System Design]]'],
  ['api design', '[[API Design]]'],
  ['web application architecture', '[[Web Application Architecture]]'],
  ['data pipeline architecture', '[[Data Pipeline Architecture]]'],
  ['cloud computing', '[[Cloud Computing]]'],
  ['caching', '[[Caching]]'],
  ['observability', '[[Observability]]'],
]

function parseFrontmatter(text) {
  if (!text.startsWith('---\n')) return { fm: {}, body: text, has: false }
  const end = text.indexOf('\n---\n', 4)
  if (end === -1) return { fm: {}, body: text, has: false }
  const raw = text.slice(4, end)
  const body = text.slice(end + 5)
  try {
    const fm = yaml.load(raw) || {}
    return { fm: typeof fm === 'object' && !Array.isArray(fm) ? fm : {}, body, has: true }
  } catch {
    return { fm: {}, body: text, has: false }
  }
}

function serializeFrontmatter(fm, body) {
  return `---\n${yaml.dump(fm, { lineWidth: -1, noRefs: true, sortKeys: false })}---\n\n${body.replace(/^\n+/, '')}`
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function enrichTermsInBlock(block) {
  // protect existing wikilinks
  const stash = []
  let t = block.replace(/\[\[[^\]]+\]\]/g, (m) => {
    const i = stash.push(m) - 1
    return `@@WL${i}@@`
  })

  let changes = 0
  for (const [term, link] of termRules) {
    const re = new RegExp(`\\b${escapeRegExp(term)}\\b`, 'gi')
    t = t.replace(re, (m) => {
      changes++
      return link
    })
  }

  t = t.replace(/@@WL(\d+)@@/g, (_, n) => stash[Number(n)])
  return { text: t, changes }
}

function enrichBody(body, file, fm) {
  const lines = body.split('\n')
  const out = []
  let inFence = false
  let termChanges = 0

  for (const line of lines) {
    if (/^```/.test(line.trim())) {
      inFence = !inFence
      out.push(line)
      continue
    }
    if (inFence) {
      out.push(line)
      continue
    }
    const e = enrichTermsInBlock(line)
    termChanges += e.changes
    out.push(e.text)
  }

  let next = out.join('\n').replace(/\n{3,}/g, '\n\n')

  const hasRelated = /\n##\s*(See also|Related|Knowledge Graph Links)\b/i.test(next)
  if (!hasRelated) {
    const related = []
    const moc = (fm.related_moc && String(fm.related_moc).trim()) || domainToMoc[String(fm.domain || '')] || '[[Development]]'
    related.push(moc)
    for (const l of ontologyLinks) related.push(l)

    const uniq = [...new Set(related)]
    next = `${next.replace(/\s+$/,'')}\n\n## Knowledge Graph Links\n\n${uniq.map((l) => `- ${l}`).join('\n')}\n`
    return { body: next, termChanges, relatedAdded: 1 }
  }

  return { body: next, termChanges, relatedAdded: 0 }
}

const files = fs.readFileSync(batchFile, 'utf8').split(/\r?\n/).map((s) => s.trim()).filter(Boolean)

let modified = []
let details = []

for (const file of files) {
  if (!fs.existsSync(file)) continue
  const orig = fs.readFileSync(file, 'utf8')
  const p = parseFrontmatter(orig)
  const e = enrichBody(p.body, file, p.fm)
  const next = p.has ? serializeFrontmatter(p.fm, e.body) : e.body
  const changed = next !== orig
  if (changed && mode === 'apply') fs.writeFileSync(file, next)
  if (changed) modified.push(file)
  details.push({ file, changed, term_changes: e.termChanges, related_added: e.relatedAdded })
}

const bn = path.basename(batchFile, '.txt')
const jsonPath = `${outDir}/${bn}_${mode}.json`
fs.writeFileSync(jsonPath, JSON.stringify({ batch: bn, mode, total: files.length, modified: modified.length, details }, null, 2))
if (mode === 'apply') {
  fs.writeFileSync(`${outDir}/${bn}_link_modified.txt`, modified.join('\n') + (modified.length ? '\n' : ''))
}

console.log(`${bn} ${mode}: total=${files.length} modified=${modified.length}`)

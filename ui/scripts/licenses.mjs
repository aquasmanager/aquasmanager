// Inventaire des dépendances de l'interface (production, transitives) pour la
// page « Licences ». Lancé à chaque compilation (quasar.config : beforeBuild) ;
// écrit src/assets/licenses-front.json, trié, sans date : sortie reproductible.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(root, 'src/assets/licenses-front.json');

function readPkg(dir) {
  const file = join(dir, 'package.json');
  return existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : null;
}

// Résolution à la node : node_modules du paquet parent, puis ceux au-dessus
function resolve(name, fromDir) {
  let dir = fromDir;
  for (;;) {
    const candidate = join(dir, 'node_modules', name);
    if (existsSync(join(candidate, 'package.json'))) return candidate;
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}

function licenseOf(pkg) {
  if (typeof pkg.license === 'string') return pkg.license;
  if (pkg.license?.type) return pkg.license.type;
  if (Array.isArray(pkg.licenses)) return pkg.licenses.map((l) => l.type ?? l).join(' OR ');
  return 'Voir le paquet';
}

function urlOf(pkg) {
  const repo = typeof pkg.repository === 'string' ? pkg.repository : pkg.repository?.url;
  const url = pkg.homepage || repo || null;
  return url ? url.replace(/^git\+/, '').replace(/\.git$/, '').replace(/^git:\/\//, 'https://') : `https://www.npmjs.com/package/${pkg.name}`;
}

const seen = new Map();
function walk(name, fromDir) {
  const dir = resolve(name, fromDir);
  if (!dir) return;
  const pkg = readPkg(dir);
  const key = `${pkg.name}@${pkg.version}`;
  if (seen.has(key)) return;
  let license = licenseOf(pkg);
  // ApexCharts et co. : licence décrite dans un fichier
  if (/^see license/i.test(license)) license = 'Licence propriétaire (voir le paquet)';
  seen.set(key, { name: pkg.name, version: pkg.version, license, url: urlOf(pkg) });
  for (const dep of Object.keys(pkg.dependencies ?? {})) walk(dep, dir);
}

const app = readPkg(root);
for (const dep of Object.keys(app.dependencies ?? {})) walk(dep, root);

const rows = [...seen.values()].sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version));
const json = `${JSON.stringify(rows, null, 1)}\n`;
const previous = existsSync(out) ? readFileSync(out, 'utf8') : '';
if (json !== previous) writeFileSync(out, json);
console.log(`licences : ${rows.length} paquets de l'interface`);

// Garde-fou : pas de licence à réciprocité forte ou propriétaire dans l'interface livrée
const blocked = rows.filter((r) => /(^|[^L])GPL|AGPL|SSPL|BUSL|propriétaire|UNLICENSED/i.test(r.license));
if (blocked.length) {
  console.error('Licences à vérifier avant publication :', blocked.map((r) => `${r.name} (${r.license})`).join(', '));
  process.exitCode = 1;
}

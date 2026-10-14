#!/usr/bin/env node
// Syntaxe des messages vue-i18n (lancé avant chaque construction) : un « @ »,
// une accolade ou une barre « | » mal placés ne sont sinon signalés qu'à
// l'affichage, par une erreur dans le navigateur. Littéral : {'@'}.
import { build } from 'esbuild';
import { baseCompile } from '@intlify/message-compiler';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const out = await build({
  entryPoints: [`${root}src/i18n/index.ts`],
  bundle: true,
  write: false,
  format: 'esm',
  platform: 'neutral',
  alias: { src: `${root}src` },
  logLevel: 'warning',
});
const url = `data:text/javascript;base64,${Buffer.from(out.outputFiles[0].text).toString('base64')}`;
const messages = (await import(url)).default;

let count = 0;
const errors = [];
function walk(node, path) {
  for (const [key, value] of Object.entries(node)) {
    const p = path ? `${path}.${key}` : key;
    if (typeof value === 'string') {
      count += 1;
      baseCompile(value, { onError: (e) => errors.push(`  ${p} : ${e.message} (« ${value} »)`) });
    } else if (value && typeof value === 'object') walk(value, p);
  }
}
walk(messages, '');

if (errors.length) {
  console.error(`Messages i18n invalides :\n${errors.join('\n')}`);
  process.exit(1);
}
console.log(`i18n : ${count} messages compilés`);

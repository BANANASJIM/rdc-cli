#!/usr/bin/env node
/**
 * Docs site validation tests.
 * Run: node docs/tests/validate.mjs
 * Requires: npm run build first (reads dist/)
 */

import { readFileSync, existsSync, readdirSync, statSync } from 'fs';
import { join, resolve } from 'path';

const DIST = resolve(import.meta.dirname, '..', 'dist');
const SRC = resolve(import.meta.dirname, '..', 'src');
const BASE = '/rdc-cli/';

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  \x1b[32m✓\x1b[0m ${name}`);
    passed++;
  } catch (e) {
    console.log(`  \x1b[31m✗\x1b[0m ${name}`);
    console.log(`    ${e.message}`);
    failed++;
  }
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

function collectFiles(dir, ext) {
  const results = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) results.push(...collectFiles(full, ext));
    else if (entry.name.endsWith(ext)) results.push(full);
  }
  return results;
}

// ── Build output tests ──────────────────────────
console.log('\n\x1b[1mBuild output\x1b[0m');

test('dist/ directory exists', () => {
  assert(existsSync(DIST), `${DIST} not found — run "npm run build" first`);
});

const expectedPages = [
  'index.html',
  'docs/index.html',
  'docs/install/index.html',
  'docs/usage/index.html',
  'docs/commands/index.html',
  'docs/vfs/index.html',
  'docs/ai-integration/index.html',
  'docs/examples/index.html',
];

for (const page of expectedPages) {
  test(`page generated: ${page}`, () => {
    assert(existsSync(join(DIST, page)), `Missing: ${page}`);
  });
}

test('favicon.svg exists', () => {
  assert(existsSync(join(DIST, 'favicon.svg')), 'Missing favicon.svg');
});

test('CSS bundle exists', () => {
  const astroDir = join(DIST, '_astro');
  assert(existsSync(astroDir), 'Missing _astro directory');
  const cssFiles = readdirSync(astroDir).filter(f => f.endsWith('.css'));
  assert(cssFiles.length > 0, 'No CSS bundles in _astro/');
});

test('JS bundles exist (typed.js, gsap)', () => {
  const astroDir = join(DIST, '_astro');
  const jsFiles = readdirSync(astroDir).filter(f => f.endsWith('.js'));
  assert(jsFiles.length >= 4, `Expected >=4 JS bundles, got ${jsFiles.length}`);
});

// ── Link integrity tests ──────────────────────────
console.log('\n\x1b[1mLink integrity\x1b[0m');

const htmlFiles = collectFiles(DIST, '.html');

for (const file of htmlFiles) {
  const content = readFileSync(file, 'utf-8');
  const relPath = file.replace(DIST, '');

  // Extract internal hrefs
  const hrefMatches = content.matchAll(/href="(\/rdc-cli\/[^"#]*)"/g);
  for (const [, href] of hrefMatches) {
    const localPath = href.replace(BASE, '');
    // href like /rdc-cli/docs/ should map to dist/docs/index.html
    let target = join(DIST, localPath);
    if (target.endsWith('/')) target = join(target, 'index.html');
    if (!target.endsWith('.html') && !target.includes('.')) {
      target = join(target, 'index.html');
    }

    test(`${relPath} → ${href}`, () => {
      // Check if it's a file or a directory with index.html
      const exists = existsSync(target) ||
        existsSync(target.replace(/\/$/, '') + '/index.html') ||
        existsSync(target.replace(/\/index\.html$/, ''));
      assert(exists, `Broken link: ${href} (looked for ${target})`);
    });
  }
}

// ── Contrast / accessibility tests ──────────────────────────
console.log('\n\x1b[1mContrast (source audit)\x1b[0m');

const srcFiles = collectFiles(SRC, '.astro');
const badContrastClasses = ['text-gray-600', 'text-gray-700', 'text-gray-800', 'text-gray-900'];

for (const file of srcFiles) {
  const content = readFileSync(file, 'utf-8');
  const relPath = file.replace(resolve(SRC, '..'), '');

  for (const cls of badContrastClasses) {
    test(`${relPath} has no ${cls}`, () => {
      assert(!content.includes(cls), `Found low-contrast class "${cls}" in ${relPath}`);
    });
  }
}

// ── Content tests ──────────────────────────
console.log('\n\x1b[1mContent\x1b[0m');

const indexHtml = readFileSync(join(DIST, 'index.html'), 'utf-8');

test('landing page has typed.js script', () => {
  assert(indexHtml.includes('typed-output'), 'Missing typed.js #typed-output element');
});

test('landing page has GSAP ScrollTrigger bundle', () => {
  // ScrollTrigger is bundled separately as a JS file, referenced via script src
  const astroDir = join(DIST, '_astro');
  const jsFiles = readdirSync(astroDir).filter(f => f.endsWith('.js'));
  const hasScrollTrigger = jsFiles.some(f => f.includes('ScrollTrigger'));
  assert(hasScrollTrigger, 'Missing ScrollTrigger JS bundle in _astro/');
});

test('landing page has dynamic command count from stats.json', () => {
  const statsPath = resolve(import.meta.dirname, '..', 'src', 'data', 'stats.json');
  const stats = JSON.parse(readFileSync(statsPath, 'utf-8'));
  const count = String(stats.command_count);
  assert(indexHtml.includes(count), `Missing "${count}" commands count (from stats.json)`);
});

test('landing page has all 12 command categories', () => {
  const categories = ['Session', 'Inspection', 'GPU State', 'Debug', 'Shader Edit', 'Resources', 'Export', 'Assertions', 'Diff', 'Search', 'VFS', 'Utility'];
  for (const cat of categories) {
    assert(indexHtml.includes(cat), `Missing command category: ${cat}`);
  }
});

test('all external links have rel="noopener noreferrer"', () => {
  for (const file of htmlFiles) {
    const content = readFileSync(file, 'utf-8');
    const relPath = file.replace(DIST, '');
    const externalLinks = content.matchAll(/target="_blank"[^>]*rel="([^"]*)"/g);
    for (const [full, rel] of externalLinks) {
      assert(
        rel.includes('noopener') && rel.includes('noreferrer'),
        `${relPath}: external link missing noreferrer: rel="${rel}"`,
      );
    }
  }
});

test('base URL has trailing slash in all internal links', () => {
  // Check no /rdc-clidocs/ (missing slash between base and path)
  assert(!indexHtml.includes('/rdc-clidocs/'), 'Found /rdc-clidocs/ — base URL missing trailing slash');
  assert(!indexHtml.includes('/rdc-clifavicon'), 'Found broken base URL concatenation');
});

// ── Summary ──────────────────────────
console.log(`\n\x1b[1m${passed + failed} tests: \x1b[32m${passed} passed\x1b[0m, \x1b[${failed ? '31' : '32'}m${failed} failed\x1b[0m\n`);
process.exit(failed > 0 ? 1 : 0);

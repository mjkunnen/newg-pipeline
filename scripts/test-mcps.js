#!/usr/bin/env node

/**
 * MCP Installation Verification Script
 *
 * Test of alle MCP servers correct zijn geïnstalleerd en bereikbaar.
 * Run: node scripts/test-mcps.js
 *
 * NOTE: Dit script test of de npm packages installeerbaar zijn
 * en of de environment variables gezet zijn. De daadwerkelijke
 * MCP connectie wordt door Claude Code zelf afgehandeld.
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const results = [];

function test(name, fn) {
  try {
    fn();
    results.push({ name, status: 'PASS', message: 'OK' });
    console.log(`  ✓ ${name}`);
  } catch (e) {
    results.push({ name, status: 'FAIL', message: e.message });
    console.log(`  ✗ ${name}: ${e.message}`);
  }
}

console.log('\n═══════════════════════════════════════');
console.log('  MCP INSTALLATION VERIFICATION');
console.log('═══════════════════════════════════════\n');

// ─── Prerequisites ───────────────────────────────────────

console.log('Prerequisites:');

test('Node.js version (v18+ required)', () => {
  const version = process.version;
  const major = parseInt(version.slice(1).split('.')[0]);
  if (major < 18) throw new Error(`Node ${version} detected, v18+ required`);
  console.log(`    Node ${version}`);
});

test('npx available', () => {
  execSync('npx --version', { stdio: 'pipe' });
});

// ─── MCP Package Installation ────────────────────────────

console.log('\nMCP Packages (checking if installable):');

const mcpPackages = [
  { name: 'Filesystem MCP', pkg: '@modelcontextprotocol/server-filesystem' },
  { name: 'GitHub MCP', pkg: '@modelcontextprotocol/server-github' },
  { name: 'Brave Search MCP', pkg: '@modelcontextprotocol/server-brave-search' },
  { name: 'Google Drive MCP', pkg: '@modelcontextprotocol/server-gdrive' },
  { name: 'Notion MCP', pkg: '@notionhq/notion-mcp-server' },
];

for (const { name, pkg } of mcpPackages) {
  test(name, () => {
    // Just check if the package info is available via npm
    try {
      execSync(`npm view ${pkg} version`, { stdio: 'pipe', timeout: 15000 });
    } catch {
      throw new Error(`Package ${pkg} not found on npm`);
    }
  });
}

// ─── Configuration Files ─────────────────────────────────

console.log('\nConfiguration Files:');

const configFiles = [
  { name: 'MCP Settings', path: '.claude/settings.json' },
  { name: 'Brand Voice', path: 'config/brand-voice.md' },
  { name: 'Target Audience', path: 'config/target-audience.md' },
  { name: 'Clothing Catalog', path: 'config/clothing-catalog.json' },
  { name: 'Platform Specs', path: 'config/platform-specs.json' },
  { name: 'Automation Settings', path: 'config/automation-settings.json' },
  { name: 'Higgsfield Config', path: 'config/higgsfield-config.json' },
];

const projectRoot = path.resolve(__dirname, '..');

for (const { name, path: filePath } of configFiles) {
  test(name, () => {
    const full = path.join(projectRoot, filePath);
    if (!fs.existsSync(full)) throw new Error(`File not found: ${filePath}`);
  });
}

// ─── API Keys Check ──────────────────────────────────────

console.log('\nAPI Keys (checking if configured):');

// Check settings.json for placeholder values
test('MCP settings loaded', () => {
  const settingsPath = path.join(projectRoot, '.claude', 'settings.json');
  const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
  if (!settings.mcpServers) throw new Error('No mcpServers in settings.json');
});

const settingsPath = path.join(projectRoot, '.claude', 'settings.json');
let settings;
try {
  settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
} catch {
  settings = { mcpServers: {} };
}

const apiChecks = [
  {
    name: 'GitHub Token',
    check: () => {
      const token = settings.mcpServers?.github?.env?.GITHUB_TOKEN;
      if (!token || token === 'VULL_HIER_JE_TOKEN_IN') {
        throw new Error('Not configured — see API-SETUP-GUIDE.md section 1');
      }
    }
  },
  {
    name: 'Brave Search Key',
    check: () => {
      const key = settings.mcpServers?.['brave-search']?.env?.BRAVE_API_KEY;
      if (!key || key === 'VULL_HIER_JE_KEY_IN') {
        throw new Error('Not configured — see API-SETUP-GUIDE.md section 2');
      }
    }
  },
  {
    name: 'Notion API Key',
    check: () => {
      const key = settings.mcpServers?.notion?.env?.NOTION_API_KEY;
      if (!key || key === 'VULL_HIER_JE_KEY_IN') {
        throw new Error('Not configured — see API-SETUP-GUIDE.md section 4');
      }
    }
  },
  {
    name: 'Meta Access Token (.env)',
    check: () => {
      const envPath = path.join(projectRoot, '.env');
      if (!fs.existsSync(envPath)) throw new Error('.env file not found');
      const env = fs.readFileSync(envPath, 'utf8');
      if (!env.includes('META_ACCESS_TOKEN=')) {
        throw new Error('META_ACCESS_TOKEN not found in .env');
      }
    }
  },
  {
    name: 'Higgsfield API Key (.env)',
    check: () => {
      const envPath = path.join(projectRoot, '.env');
      const env = fs.readFileSync(envPath, 'utf8');
      if (!env.includes('HIGGSFIELD_API_KEY=')) {
        throw new Error('HIGGSFIELD_API_KEY not found in .env — see API-SETUP-GUIDE.md section 5');
      }
    }
  }
];

for (const { name, check } of apiChecks) {
  test(name, check);
}

// ─── Folder Structure ────────────────────────────────────

console.log('\nFolder Structure:');

const requiredDirs = [
  'config',
  'research/tiktok-analysis',
  'research/pinterest-trends',
  'research/competitor-analysis',
  'research/insights',
  'content-library/clothing-items',
  'content-library/brand-assets',
  'content-library/inspiration',
  'ad-generation/concepts',
  'ad-generation/copy',
  'ad-generation/visuals',
  'ad-generation/output',
  'scripts',
];

for (const dir of requiredDirs) {
  test(dir, () => {
    const full = path.join(projectRoot, dir);
    if (!fs.existsSync(full)) throw new Error(`Directory not found`);
  });
}

// ─── Summary ─────────────────────────────────────────────

console.log('\n═══════════════════════════════════════');
const passed = results.filter(r => r.status === 'PASS').length;
const failed = results.filter(r => r.status === 'FAIL').length;
console.log(`  RESULTS: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  console.log('\n  Action items:');
  results.filter(r => r.status === 'FAIL').forEach(r => {
    console.log(`  → ${r.name}: ${r.message}`);
  });
}

console.log('═══════════════════════════════════════\n');

process.exit(failed > 0 ? 1 : 0);

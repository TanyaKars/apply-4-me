#!/usr/bin/env node
/**
 * apply4me setup script
 * Run: node scripts/setup.js
 */
const { execSync } = require("child_process")
const fs = require("fs")
const path = require("path")
const os = require("os")

const DATA_DIR = path.join(os.homedir(), ".apply4me")
const CONFIG_FILE = path.join(DATA_DIR, "config.json")
const REPO_ROOT = path.resolve(__dirname, "..")
const SKILL_MD = path.join(REPO_ROOT, ".claude", "skills", "resume", "SKILL.md")

console.log("\n🚀 apply4me setup\n")

// Create ~/.apply4me
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true })
  console.log(`✓ Created ${DATA_DIR}`)
}

// Create default config if missing
if (!fs.existsSync(CONFIG_FILE)) {
  const defaultConfig = {
    skill_md_path: SKILL_MD,
    search: {
      keywords: ["Software Engineer"],
      location: "Remote",
      date_posted: "past_week",
      blacklist_companies: []
    },
    resume: {
      template: "modern",
      include_photo: false
    }
  }
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(defaultConfig, null, 2))
  console.log(`✓ Created ${CONFIG_FILE}`)
}

// Install UI deps
console.log("\nInstalling UI dependencies...")
execSync("npm install", { cwd: path.join(__dirname, "../ui"), stdio: "inherit" })

// Install API deps
console.log("\nInstalling API dependencies...")
try {
  execSync("uv sync", { cwd: path.join(__dirname, "../api"), stdio: "inherit" })
} catch {
  console.log("  (uv not found — install from https://docs.astral.sh/uv/)")
}

// Install PW (Playwright) deps
console.log("\nInstalling PW dependencies...")
try {
  execSync("uv sync", { cwd: path.join(__dirname, "../pw"), stdio: "inherit" })
  execSync("uv run playwright install chromium", { cwd: path.join(__dirname, "../pw"), stdio: "inherit" })
} catch {}

console.log(`
✅ Setup complete!

Next steps:
1. Copy .env.example → .env and add your Anthropic API key
2. Edit SKILL.md in VS Code — fill in your real experience and preferences
3. Run: npm run dev        (starts api + ui)
4. Visit: http://localhost:3000
5. Go to Settings → Set Up Session (LinkedIn auth)
6. Click "Scrape Jobs" on the dashboard

Docs: https://github.com/yourname/apply4me
`)

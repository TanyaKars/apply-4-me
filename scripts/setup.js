#!/usr/bin/env node
/**
 * appy4me setup script
 * Run: node scripts/setup.js
 */
const { execSync } = require("child_process")
const fs = require("fs")
const path = require("path")
const os = require("os")

const DATA_DIR = path.join(os.homedir(), ".appy4me")
const CONFIG_FILE = path.join(DATA_DIR, "config.json")

console.log("\n🚀 appy4me setup\n")

// Create ~/.appy4me
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true })
  console.log(`✓ Created ${DATA_DIR}`)
}

// Create default config if missing
if (!fs.existsSync(CONFIG_FILE)) {
  const defaultConfig = {
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
1. Add your Anthropic API key to .env  (copy .env.example)
2. Run: npm run dev        (starts api + ui)
3. Visit: http://localhost:3000
4. Go to Settings → Set Up Session (LinkedIn auth)
5. Go to Resume → Build your base resume
6. Click "Scrape Jobs" on the dashboard

Docs: https://github.com/yourname/appy4me
`)

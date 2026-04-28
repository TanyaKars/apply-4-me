#!/bin/bash
set -e

if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "Created .env — open it and replace sk-ant-your-key-here with your Anthropic API key, then run this script again."
  echo ""
  exit 1
fi

if ! grep -q "^ANTHROPIC_API_KEY=sk-ant-" .env && ! grep -qP "^ANTHROPIC_API_KEY=sk-ant-api03-" .env 2>/dev/null; then
  if grep -q "your-key-here" .env; then
    echo "Please add your ANTHROPIC_API_KEY to the .env file before starting."
    exit 1
  fi
fi

docker compose up --build

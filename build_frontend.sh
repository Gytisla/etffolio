#!/bin/bash
# Build the ETFfolio frontend and copy to the custom component directory.
# Run from the repo root: ./build_frontend.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
OUTPUT_DIR="$SCRIPT_DIR/custom_components/etffolio/frontend"

echo "📦 Building ETFfolio frontend..."

cd "$FRONTEND_DIR"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📥 Installing dependencies..."
    npm install
fi

# Build the React app
echo "🔨 Running Vite build..."
npm run build

# Copy built files to custom component
echo "📋 Copying to custom component..."
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
cp -r dist/* "$OUTPUT_DIR/"

echo "✅ Frontend built and copied to custom_components/etffolio/frontend/"
echo "   You can now install the custom component in Home Assistant."

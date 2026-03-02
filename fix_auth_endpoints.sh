#!/bin/bash
# Fix all auth endpoints to use backend URL instead of frontend URL
cd "D:\Quantum/frontend/js"

# Create temp file and replace
sed -i.bak "s|'/auth/register|' \`${CONFIG.apiUrl}/register|g" main.js
sed -i.bak2 "s|'/auth/login|' \`${CONFIG.apiUrl}/login|g" main.js

echo "✓ Updated auth endpoints in main.js"
echo "✓ Changes from line 668, 698, 802:"
grep -n "CONFIG.apiUrl.*auth" main.js | head -5

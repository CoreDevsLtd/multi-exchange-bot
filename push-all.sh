#!/bin/bash
# Push to all remotes simultaneously

echo "🚀 Pushing to origin (Dev0-Paklogics)..."
git push origin main

if [ $? -eq 0 ]; then
    echo "✅ Successfully pushed to origin"
else
    echo "❌ Failed to push to origin"
    exit 1
fi

echo ""
echo "🚀 Pushing to backup (omaisali)..."
git push backup main

if [ $? -eq 0 ]; then
    echo "✅ Successfully pushed to backup"
    echo ""
    echo "🎉 All repositories updated!"
else
    echo "❌ Failed to push to backup"
    exit 1
fi


# One-time setup: push to GitHub for free Streamlit hosting
# Usage: .\scripts\setup-github.ps1 -GitHubUsername YOUR_USERNAME

param(
    [Parameter(Mandatory = $true)]
    [string]$GitHubUsername,

    [string]$RepoName = "whatsapp-wedding-invitations"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "`n=== WhatsApp Invitations — GitHub setup ===" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot`n"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git is not installed. Install from https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".git")) {
    git init
    git branch -M main
}

git add .
$status = git status --porcelain
if ($status) {
    git commit -m "Deploy WhatsApp Wedding Invitations app"
    Write-Host "Committed local changes." -ForegroundColor Green
} else {
    Write-Host "Nothing new to commit." -ForegroundColor Yellow
}

$remoteUrl = "https://github.com/$GitHubUsername/$RepoName.git"
$existing = git remote get-url origin 2>$null
if (-not $existing) {
    git remote add origin $remoteUrl
    Write-Host "Added remote: $remoteUrl" -ForegroundColor Green
} else {
    Write-Host "Remote origin already set: $existing" -ForegroundColor Yellow
}

Write-Host @"

NEXT STEPS (manual — needs your GitHub login):

1. Create repo at: https://github.com/new
   Name: $RepoName  |  Public  |  Do NOT add README

2. Push:
   git push -u origin main

   Use Personal Access Token as password if prompted:
   https://github.com/settings/tokens (scope: repo)

3. Deploy free app:
   https://share.streamlit.io → New app → $RepoName → app.py → Deploy

4. Full guide: DEPLOY.md

"@ -ForegroundColor White

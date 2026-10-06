#!/usr/bin/env sh

[ ! -d "node_modules" ] && npm ci

./node_modules/.bin/cspell "docs/**/*.md"
mkdocs build
linkchecker -f linkcheckerrc public || true

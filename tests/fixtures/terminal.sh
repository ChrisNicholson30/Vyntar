#!/bin/bash
# Deliberate terminal acceptance fixture. Diff signs use foreground only.
set -eu
for code in 30 31 32 33 34 35 36 37 90 91 92 93 94 95 96 97; do
    printf '\033[%sm %s Aa \033[0m' "$code" "$code"
done
printf '\n'
for code in 40 41 42 43 44 45 46 47 100 101 102 103 104 105 106 107; do
    printf '\033[%sm  %s  \033[0m' "$code" "$code"
done
printf '\n\033[1mBold\033[0m  \033[7mInverse\033[0m  Reset\n'
printf '\033[38;5;117m256-colour sample\033[0m\n'
printf '\033[38;2;35;243;244mRGB cyan sample\033[0m\n'
printf '\033[31m- removal: foreground only\033[0m\n'
printf '\033[32m+ addition: foreground only\033[0m\n'

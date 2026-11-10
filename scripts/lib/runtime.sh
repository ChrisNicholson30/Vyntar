#!/bin/bash
# Shared lifecycle. macOS Bash 3.2; no Python, network or preference editing.
set -eu
set -o pipefail
umask 077
export LC_ALL=C
VY_STATE=${VYNTAR_DATA_HOME:-"$HOME/Library/Application Support/Vyntar"}
VY_CODEX=${CODEX_HOME:-"$HOME/.codex"}
VY_APPS=${VYNTAR_APPLICATIONS:-/Applications}
VY_DRY=0 VY_PLAIN=0 VY_EXPLICIT=0 VY_LOCKED=0 VY_MUTATING=0
VY_TARGETS=zed,terminal,xcode,codex
VY_BUNDLE=$VY_ROOT
VY_BUNDLE_EXPLICIT=0
TAB=$(printf '\t')

say() { printf '%s\n' "$*"; }
fail() { printf 'ERROR %s\n' "$*" >&2; exit 1; }
usage() {
    say 'Vyntar · Precision in Colour'
    say 'install.sh [--target zed,terminal,xcode,codex] [--dry-run]'
    say 'update.sh --bundle /absolute/path [--target ...] [--dry-run]'
    say 'uninstall.sh [--target ...] [--dry-run]'
    say 'bin/vyntar status | doctor | preview | theme pulse|endurance|auto'
    say 'bin/vyntar restore TRANSACTION [--dry-run]'
    say 'All commands accept --plain and --non-interactive.'
}
valid_path() {
    case "$1" in /*) ;; *) fail "Absolute path required: $1";; esac
    case "$1" in *"$TAB"*|*'
'*|*/../*|*/./*|*/..|*/.) fail "Unsupported path: $1";; esac
}
no_links() {
    valid_path "$1"
    local p=$1
    while [ "$p" != / ]; do
        [ ! -L "$p" ] || fail "Symlink destination/ancestor refused: $p"
        p=${p%/*}; [ -n "$p" ] || p=/
    done
}
hash() {
    if [ -f "$1" ] && [ ! -L "$1" ]; then
        shasum -a 256 "$1" | cut -d ' ' -f 1
    elif [ -e "$1" ] || [ -L "$1" ]; then
        fail "Expected a regular file: $1"
    else
        printf '%s\n' '-'
    fi
}
expected() {
    if [ -f "$VY_STATE/owned.tsv" ]; then
        awk -F '\t' -v path="$1" '$3==path {print $2; exit}' "$VY_STATE/owned.tsv"
    fi
}
app_available() {
    case "$1" in
        zed) [ -d "$VY_APPS/Zed.app" ] || [ -d "$HOME/Applications/Zed.app" ];;
        terminal) [ -d /System/Applications/Utilities/Terminal.app ] || [ -d "$VY_APPS/Terminal.app" ];;
        xcode) [ -d "$VY_APPS/Xcode.app" ] || [ -d "$HOME/Applications/Xcode.app" ];;
        codex) command -v codex >/dev/null 2>&1;;
    esac
}
selected() { case ",$VY_TARGETS," in *",$1,"*) return 0;; *) return 1;; esac; }
artwork() {
    [ "$VY_PLAIN" = 0 ] && [ -t 1 ] && [ "${TERM:-dumb}" != dumb ] && [ -z "${NO_COLOR+x}" ] || return 0
    printf '\033[36m  \\/\033[0m  \033[35mV Y N T A R\033[0m\n'
    printf '      P R E C I S I O N   I N   C O L O U R\n\n'
}
verify_bundle() {
    no_links "$VY_BUNDLE"
    [ -f "$VY_BUNDLE/MANIFEST.sha256" ] && [ -f "$VY_BUNDLE/VERSION" ] || fail 'Bundle needs VERSION and MANIFEST.sha256.'
    VY_VERSION=$(cat "$VY_BUNDLE/VERSION")
    case "$VY_VERSION" in ''|*[!0-9A-Za-z.-]*) fail 'Invalid bundle version';; esac
    local line digest name
    while IFS= read -r line; do
        digest=${line%%  *}; name=${line#*  }
        [ "${#digest}" = 64 ] || fail 'Invalid bundle digest'
        case "$digest" in *[!0-9a-f]*) fail 'Invalid SHA-256';; esac
        case "$name" in ''|/*|*..*|*"$TAB"*) fail 'Invalid bundle path';; esac
        no_links "$VY_BUNDLE/$name"
        [ "$(hash "$VY_BUNDLE/$name")" = "$digest" ] || fail "Bundle integrity mismatch: $name"
    done < "$VY_BUNDLE/MANIFEST.sha256"
    # Every consumed payload must be declared, not merely present.
    for name in VERSION bin/vyntar scripts/lib/runtime.sh scripts/lib/palette-preview.sh palette/palette.json themes/zed/vyntar.json \
      themes/terminal/Vyntar-Pulse.terminal themes/terminal/Vyntar-Endurance.terminal \
      'themes/xcode/workspace/Vyntar Pulse.xcworkspacecolortheme' 'themes/xcode/workspace/Vyntar Endurance.xcworkspacecolortheme' \
      themes/codex/vyntar-pulse.tmTheme themes/codex/vyntar-endurance.tmTheme themes/codex/vyntar-pulse-ansi.tmTheme themes/codex/vyntar-endurance-ansi.tmTheme; do
        awk -v path="$name" 'substr($0,67)==path {found=1} END {exit !found}' "$VY_BUNDLE/MANIFEST.sha256" || fail "Unlisted payload: $name"
    done
}
lock() {
    no_links "$VY_STATE"
    mkdir -p "$VY_STATE"
    [ "$(stat -f '%Su' "$VY_STATE" 2>/dev/null || stat -c '%U' "$VY_STATE")" = "$(id -un)" ] || fail 'State directory belongs to another user'
    chmod 700 "$VY_STATE"
    mkdir "$VY_STATE/lock" 2>/dev/null || fail "Writer lock exists: $VY_STATE/lock. Inspect owner.txt; remove the empty lock only after that process exits."
    VY_LOCKED=1
    printf 'pid=%s\nhost=%s\n' "$$" "$(hostname)" > "$VY_STATE/lock/owner.txt"
    if [ -d "$VY_STATE/pending" ]; then
        say 'RECOVER Reconciling interrupted transaction.'
        if [ -f "$VY_STATE/pending/preparing" ]; then
            # No destination is touched until the complete journal is ready.
            mv "$VY_STATE/pending" "$VY_STATE/recovered-preparation-$(date -u +%Y%m%dT%H%M%S)-$$"
        else
            rollback || fail "Recovery conflict. Keep pending journal and backups: $VY_STATE/pending"
        fi
    fi
}
# Use fixed sidecar names, no wildcards or user-supplied shell evaluation.
atomic_copy() {
    local src=$1 dst=$2 tmp
    no_links "$dst"
    mkdir -p "${dst%/*}"
    tmp=$(mktemp "${dst%/*}/.vyntar.XXXXXX")
    if ! cp -p "$src" "$tmp" || ! mv -f "$tmp" "$dst"; then
        rm -f "$tmp"; return 1
    fi
}
rollback() {
    local target old new path backup current ok=1
    [ -f "$VY_STATE/pending/operations.tsv" ] || return 1
    # Full snapshot exists before mutation, so each path can be reconciled by hash.
    while IFS="$TAB" read -r target old new path backup; do
        no_links "$path"
        current=$(hash "$path")
        if [ "$current" = "$old" ]; then continue; fi
        if [ "$current" != "$new" ]; then
            printf 'CONFLICT Preserved concurrent edit: %s\n' "$path" >&2; ok=0; continue
        fi
        if [ "$old" = - ]; then
            rm -f "$path" || ok=0
        elif [ -f "$VY_STATE/pending/backups/$backup" ] && [ "$(hash "$VY_STATE/pending/backups/$backup")" = "$old" ]; then
            atomic_copy "$VY_STATE/pending/backups/$backup" "$path" || ok=0
        else
            ok=0
        fi
    done < "$VY_STATE/pending/operations.tsv"
    [ "$ok" = 1 ] || return 1
    if [ -f "$VY_STATE/pending/old-owned.tsv" ]; then
        atomic_copy "$VY_STATE/pending/old-owned.tsv" "$VY_STATE/owned.tsv" || return 1
    else
        rm -f "$VY_STATE/owned.tsv"
    fi
    mv "$VY_STATE/pending" "$VY_STATE/recovered-$(date -u +%Y%m%dT%H%M%S)-$$"
}
cleanup() {
    local rc=$?
    trap - EXIT INT TERM HUP
    if [ "$VY_MUTATING" = 1 ] && [ -d "$VY_STATE/pending" ]; then
        if ! rollback; then printf 'CONFLICT Recovery pending at %s/pending\n' "$VY_STATE" >&2; rc=1; fi
    fi
    if [ "$VY_LOCKED" = 1 ]; then
        rm -f "$VY_STATE/lock/owner.txt"
        rmdir "$VY_STATE/lock" || rc=1
    fi
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 1' INT TERM HUP

# Payload list: target, source relative to bundle, absolute destination.
payloads() {
    local target
    for target in zed terminal xcode codex; do
        selected "$target" || continue
        if ! app_available "$target"; then
            if [ "$VY_EXPLICIT" = 1 ]; then fail "Requested application unavailable: $target"; fi
            printf 'SKIP %s is not installed\n' "$target" >&2; continue
        fi
        case "$target" in
          zed) printf 'zed\tthemes/zed/vyntar.json\t%s/.config/zed/themes/vyntar.json\n' "$HOME";;
          terminal)
            printf 'terminal\tthemes/terminal/Vyntar-Pulse.terminal\t%s/imports/Vyntar-Pulse.terminal\n' "$VY_STATE"
            printf 'terminal\tthemes/terminal/Vyntar-Endurance.terminal\t%s/imports/Vyntar-Endurance.terminal\n' "$VY_STATE";;
          xcode)
            printf 'xcode\tthemes/xcode/workspace/Vyntar Pulse.xcworkspacecolortheme\t%s/Library/Developer/Xcode/UserData/FontAndColorThemes/Vyntar Pulse.xcworkspacecolortheme\n' "$HOME"
            printf 'xcode\tthemes/xcode/workspace/Vyntar Endurance.xcworkspacecolortheme\t%s/Library/Developer/Xcode/UserData/FontAndColorThemes/Vyntar Endurance.xcworkspacecolortheme\n' "$HOME";;
          codex)
            local slug
            for slug in pulse endurance pulse-ansi endurance-ansi; do
                printf 'codex\tthemes/codex/vyntar-%s.tmTheme\t%s/themes/vyntar-%s.tmTheme\n' "$slug" "$VY_CODEX" "$slug"
            done;;
        esac
    done
}
management_payloads() {
    printf 'manager\tbin/vyntar\t%s/bin/vyntar\n' "$VY_STATE"
    printf 'manager\tscripts/lib/runtime.sh\t%s/scripts/lib/runtime.sh\n' "$VY_STATE"
    printf 'manager\tscripts/lib/palette-preview.sh\t%s/scripts/lib/palette-preview.sh\n' "$VY_STATE"
    printf 'manager\tVERSION\t%s/VERSION\n' "$VY_STATE"
}
# Plan kept in memory: a dry run never creates temp files, directories or locks.
preflight() {
    local target source path current owned new
    while IFS="$TAB" read -r target source path; do
        [ -n "$target" ] || continue
        no_links "$path"; current=$(hash "$path"); owned=$(expected "$path")
        [ "$current" = - ] || [ "$current" = "$owned" ] || fail "Unmanaged or edited destination: $path"
        # An absent managed file may be repaired by install/update.
        new=$(hash "$VY_BUNDLE/$source")
        [ "$new" != - ] || fail "Missing payload: $source"
        printf '%s\t%s\t%s\t%s\t%s\n' "$target" "$current" "$new" "$path" "$source"
    done <<< "$VY_PAYLOADS"
}
commit_plan() {
    local target old new path source n=0 current txid
    txid=$(date -u +%Y%m%dT%H%M%S)-$$
    mkdir "$VY_STATE/pending"
    : > "$VY_STATE/pending/preparing"
    mkdir "$VY_STATE/pending/backups"
    if [ -f "$VY_STATE/owned.tsv" ]; then cp -p "$VY_STATE/owned.tsv" "$VY_STATE/pending/old-owned.tsv"; fi
    : > "$VY_STATE/pending/operations.tsv"
    # Prepare backups and complete write-ahead journal before the first rename.
    while IFS="$TAB" read -r target old new path source; do
        [ -n "$target" ] || continue
        n=$((n+1)); no_links "$path"
        [ "$(hash "$path")" = "$old" ] || fail "Changed during preflight: $path"
        if [ "$old" != - ]; then
            cp -p "$path" "$VY_STATE/pending/backups/$n"
            [ "$(hash "$VY_STATE/pending/backups/$n")" = "$old" ] || fail "Concurrent edit while backing up: $path"
        fi
        printf '%s\t%s\t%s\t%s\t%s\n' "$target" "$old" "$new" "$path" "$n" >> "$VY_STATE/pending/operations.tsv"
    done <<< "$VY_PLAN"
    mv "$VY_STATE/pending/preparing" "$VY_STATE/pending/ready"
    VY_MUTATING=1
    # Preserve records for unselected targets; replace rows for planned paths.
    if [ -f "$VY_STATE/owned.tsv" ]; then cp "$VY_STATE/owned.tsv" "$VY_STATE/pending/new-owned.tsv"; else : > "$VY_STATE/pending/new-owned.tsv"; fi
    n=0
    while IFS="$TAB" read -r target old new path source; do
        [ -n "$target" ] || continue
        n=$((n+1)); no_links "$path"
        [ "$(hash "$path")" = "$old" ] || fail "Concurrent edit: $path"
        if [ "$old" != "$new" ]; then
            if [ "$new" = - ]; then rm -f "$path"; else atomic_copy "$source" "$path" || fail "Cannot write: $path"; fi
            [ "$(hash "$path")" = "$new" ] || fail "Write verification failed: $path"
        fi
        awk -F '\t' -v path="$path" '$3!=path' "$VY_STATE/pending/new-owned.tsv" > "$VY_STATE/pending/next-owned.tsv"
        mv "$VY_STATE/pending/next-owned.tsv" "$VY_STATE/pending/new-owned.tsv"
        if [ "$new" != - ]; then printf '%s\t%s\t%s\n' "$target" "$new" "$path" >> "$VY_STATE/pending/new-owned.tsv"; fi
        if [ "${VYNTAR_TEST_FAIL_AFTER:-}" = "$n" ]; then fail 'Injected transaction failure'; fi
    done <<< "$VY_PLAN"
    atomic_copy "$VY_STATE/pending/new-owned.tsv" "$VY_STATE/owned.tsv"
    printf '%s\n' "${VY_VERSION:-restored}" > "$VY_STATE/pending/version"
    mkdir -p "$VY_STATE/transactions"
    mv "$VY_STATE/pending" "$VY_STATE/transactions/$txid"
    VY_MUTATING=0
    say "OK Transaction $txid"
}
activation() {
    say 'MANUAL Zed: Theme Selector → Vyntar Pulse / Vyntar Endurance.'
    say "MANUAL Terminal: Settings → Profiles → Import from $VY_STATE/imports."
    say 'MANUAL Xcode: Settings → Appearance → Theme → Choose; reopen if needed.'
    say 'MANUAL Codex: /theme → vyntar-pulse-ansi or vyntar-endurance-ansi.'
    say 'ANSI themes follow the host palette. Import/select the matching terminal theme.'
    say "COMMAND $VY_STATE/bin/vyntar status"
}
install_or_update() {
    verify_bundle
    VY_PAYLOADS=$(payloads)
    [ -n "$VY_PAYLOADS" ] || fail 'No available targets'
    VY_PAYLOADS=$(printf '%s\n%s' "$VY_PAYLOADS" "$(management_payloads)")
    if [ -d "$VY_STATE/pending" ]; then
        [ "$VY_DRY" = 0 ] || fail 'Pending transaction: rerun without --dry-run to reconcile before planning.'
        lock
    fi
    VY_PLAN=$(preflight)
    if [ "$VY_DRY" = 1 ]; then
        while IFS="$TAB" read -r target old new path source; do say "PLAN $target → $path"; done <<< "$VY_PLAN"
        return
    fi
    [ "$VY_LOCKED" = 1 ] || lock
    VY_PLAN=$(preflight)
    if ! printf '%s\n' "$VY_PLAN" | awk -F '\t' '$2!=$3 {changed=1} END {exit !changed}'; then say 'OK Already installed; no changes.'; activation; return; fi
    # Transform relative bundle paths into absolute payload paths after preflight.
    VY_PLAN=$(while IFS="$TAB" read -r target old new path source; do printf '%s\t%s\t%s\t%s\t%s/%s\n' "$target" "$old" "$new" "$path" "$VY_BUNDLE" "$source"; done <<< "$VY_PLAN")
    commit_plan
    activation
}
uninstall() {
    if [ -d "$VY_STATE/pending" ]; then
        [ "$VY_DRY" = 0 ] || fail 'Pending recovery; run without --dry-run first.'
        lock
    fi
    [ -s "$VY_STATE/owned.tsv" ] || { say 'OK Nothing installed.'; return; }
    local target owned path current conflict=0
    VY_PLAN=''
    while IFS="$TAB" read -r target owned path; do
        if [ "$target" = manager ]; then
            [ "$VY_EXPLICIT" = 0 ] && [ "$conflict" = 0 ] || continue
        else selected "$target" || continue; fi
        no_links "$path"; current=$(hash "$path")
        if [ "$current" != - ] && [ "$current" != "$owned" ]; then
            say "CONFLICT Edited file kept: $path"; conflict=1; continue
        fi
        VY_PLAN="${VY_PLAN}$(printf '%s\t%s\t-\t%s\t-' "$target" "$current" "$path")
"
    done < "$VY_STATE/owned.tsv"
    if [ "$VY_DRY" = 1 ]; then say "PLAN Remove unchanged owned files:$VY_PLAN"; return "$conflict"; fi
    [ "$VY_LOCKED" = 1 ] || lock
    # Recheck every path after acquiring lock.
    while IFS="$TAB" read -r target old new path source; do
        [ -n "$target" ] || continue
        [ "$(hash "$path")" = "$old" ] || fail "Concurrent edit: $path"
    done <<< "$VY_PLAN"
    [ -z "$VY_PLAN" ] || commit_plan
    say 'MANUAL Switch apps to another theme. Remove imported Terminal profiles in Settings.'
    say "KEPT Recovery records: $VY_STATE/transactions"
    return "$conflict"
}
restore() {
    if [ -d "$VY_STATE/pending" ]; then
        [ "$VY_DRY" = 0 ] || fail 'Pending recovery; run without --dry-run first.'
        lock
    fi
    case "$VY_ARG" in ''|*[!0-9A-Za-z-]*) fail 'Invalid transaction ID';; esac
    local journal="$VY_STATE/transactions/$VY_ARG" target old new path backup current
    no_links "$journal"
    [ -f "$journal/operations.tsv" ] || fail 'Transaction not found'
    VY_PLAN=''
    while IFS="$TAB" read -r target old new path backup; do
        no_links "$path"; current=$(hash "$path")
        [ "$current" = "$new" ] || fail "Restore would overwrite a later change: $path"
        if [ "$old" != - ]; then
            [ "$(hash "$journal/backups/$backup")" = "$old" ] || fail 'Backup integrity mismatch'
        fi
        VY_PLAN="${VY_PLAN}$(printf '%s\t%s\t%s\t%s\t%s' "$target" "$current" "$old" "$path" "$journal/backups/$backup")
"
    done < "$journal/operations.tsv"
    if [ "$VY_DRY" = 1 ]; then say "PLAN Restore $VY_ARG"; return; fi
    [ "$VY_LOCKED" = 1 ] || lock
    commit_plan
    say 'MANUAL Re-select or re-import app-owned themes if necessary.'
}
status() {
    local target owned path current bad=0
    if [ -d "$VY_STATE/pending" ]; then say 'RECOVER Pending transaction; next write attempts guarded recovery.'; bad=1; fi
    [ ! -d "$VY_STATE/lock" ] || { say "LOCK $VY_STATE/lock"; bad=1; }
    if [ -f "$VY_STATE/preference" ]; then say "PREFERENCE $(cat "$VY_STATE/preference") (guidance only)"; fi
    if [ ! -s "$VY_STATE/owned.tsv" ]; then say 'STATUS Not installed.'; return "$bad"; fi
    while IFS="$TAB" read -r target owned path; do
        no_links "$path"; current=$(hash "$path")
        if [ "$current" != "$owned" ]; then say "DRIFT $target $path"; bad=1
        elif [ "$target" = terminal ]; then say "STAGED $path (import/activation unverified)"
        else say "INSTALLED $target $path (selection unverified)"; fi
    done < "$VY_STATE/owned.tsv"
    if [ "$VY_COMMAND" = doctor ]; then
        for target in zed terminal xcode codex; do
            if app_available "$target"; then say "AVAILABLE $target"; else say "MISSING $target"; fi
        done
    fi
    return "$bad"
}
preview() {
    local rgb_capable=0
    if [ "$VY_PLAIN" = 0 ] && [ -t 1 ] && [ "${TERM:-dumb}" != dumb ] && [ -z "${NO_COLOR+x}" ]; then
        case "${COLORTERM:-}" in truecolor|24bit) rgb_capable=1;; esac
    fi
    . "$VY_ROOT/scripts/lib/palette-preview.sh"
    vyntar_print_palettes "$rgb_capable"
    say 'Vyntar ANSI palette · follows your currently selected host theme'
    local i code
    if [ "$VY_PLAIN" = 1 ] || [ ! -t 1 ] || [ "${TERM:-dumb}" = dumb ] || [ -n "${NO_COLOR+x}" ]; then
        say 'Slots: black red green yellow blue magenta cyan white'
        say 'Bright: black red green yellow blue magenta cyan white'
        say '- removal   + addition   (foreground only)'; return
    fi
    i=0
    while [ "$i" -lt 16 ]; do
        if [ "$i" -lt 8 ]; then code=$((30+i)); else code=$((90+i-8)); fi
        printf '\033[%sm %02d Aa \033[0m' "$code" "$i"
        i=$((i+1)); [ $((i%8)) != 0 ] || printf '\n'
    done
    printf '\033[31m- removal\033[0m\n\033[32m+ addition\033[0m\n'
}
theme() {
    local recommendation=$VY_ARG source
    case "$VY_ARG" in pulse|endurance) ;; auto)
        source=$(pmset -g batt 2>/dev/null | head -n 1 || true)
        case "$source" in *"'AC Power'"*) recommendation=pulse;; *"'Battery Power'"*) recommendation=endurance;; *) recommendation=unknown;; esac;;
        *) printf 'Invalid theme. Use pulse, endurance, or auto.\n' >&2; exit 2;;
    esac
    if [ "$VY_DRY" = 0 ]; then
        lock
        no_links "$VY_STATE/preference"
        local temporary
        temporary=$(mktemp "$VY_STATE/.preference.XXXXXX")
        printf '%s\n' "$VY_ARG" > "$temporary"
        mv "$temporary" "$VY_STATE/preference"
    fi
    say "PREFERENCE $VY_ARG; recommended: $recommendation"
    say 'MANUAL Select the recommended variant in each app; no app selections were changed.'
}
main() {
    VY_COMMAND=${1:-help}; shift || true; VY_ARG=''
    case "$VY_COMMAND" in theme|restore) VY_ARG=${1:-}; [ "$#" = 0 ] || shift;; esac
    while [ "$#" -gt 0 ]; do
        case "$1" in
          --dry-run) VY_DRY=1;; --plain) VY_PLAIN=1;; --non-interactive) :;;
          --target) [ "$#" -ge 2 ] || { usage; exit 2; }; VY_TARGETS=$2; VY_EXPLICIT=1; shift;;
          --bundle) [ "$#" -ge 2 ] || { usage; exit 2; }; VY_BUNDLE=$2; VY_BUNDLE_EXPLICIT=1; shift;;
          --help|-h) usage; return;; *) usage >&2; exit 2;;
        esac; shift
    done
    case "$VY_TARGETS" in ''|,*|*,|*,,*) usage >&2; exit 2;; esac
    local t remaining=$VY_TARGETS
    while :; do
        t=${remaining%%,*}; case "$t" in zed|terminal|xcode|codex) ;; *) usage >&2; exit 2;; esac
        [ "$remaining" != "$t" ] || break; remaining=${remaining#*,}
    done
    no_links "$VY_STATE"; valid_path "$HOME"; valid_path "$VY_CODEX"
    artwork
    case "$VY_COMMAND" in
      install) install_or_update;;
      update) [ "$VY_BUNDLE_EXPLICIT" = 1 ] || fail 'update requires --bundle /absolute/path'; install_or_update;;
      uninstall) uninstall;; status|doctor) status;; preview) preview;; theme) theme;; restore) restore;; help) usage;; *) usage >&2; exit 2;;
    esac
}
main "$@"

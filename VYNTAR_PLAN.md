---
Title: Vyntar Developer Theme Implementation Plan
Subtitle: Precision in Colour
Status: Preview implementation
Version: "1.1"
Created: 2026-11-10
Owner: Christopher Nicholson
Product: Vyntar
Tags: theme, macOS, implementation-plan
---

# Vyntar

**Precision in Colour** · Implementation plan for Zed, Terminal.app, Xcode and Codex CLI

## Implementation review · 2026-11-10

The source plan is implemented as **0.1.0-preview.1**. The shared palette, deterministic generators, nine native theme files, offline installer, update/uninstall, ownership tracking, transaction recovery, guarded restore, previews, tests and on-demand power guidance are present. Four Codex files provide RGB and genuine ANSI-index versions of both variants.

**Brief correction:** additions and removals use coloured text only. Diff background roles are `null`; the proposed Add/Remove/Change tint swatches below have been removed. Codex requires an explicit terminal-default scope marker rather than an omitted background. Current Zed also needs its dedicated hunk and word-diff fill overrides, beyond the published v0.2.0 schema. These are tracked in a source-derived schema overlay.

**Verification:** 23 automated tests pass, including real upgrade/restore, rollback and interrupted-journal scenarios. All 302 contrast pairs pass (minimum 4.77:1); all 42 Terminal NSColor fields decode correctly through AppKit. The generated visual comparison has been rendered and inspected.

**Release cut line:** this is a reviewable preview, not a claim of complete native compatibility. Native theme selection, import/export round trips and screenshots in all four apps remain unchecked. Xcode's modern recipe structure and colour conversion are verified statically; native loading and its app-owned diff styling still need observation. Legacy Xcode, automatic app selection and the resident power helper are deferred. Empty application directories are retained on uninstall; recovery records are retained deliberately. See [compatibility evidence and acceptance steps](docs/COMPATIBILITY.md), [usage](README.md) and [contrast results](docs/contrast.tsv).

## 1. Objective

Ship two cohesive dark themes from one colour system. **Vyntar Pulse** combines electric cyan, ultraviolet and laser blue with deep midnight surfaces. **Vyntar Endurance** keeps the same visual vocabulary with near-black surfaces, softer accents and restrained effects. Both must be readable enough for an ordinary working day.

A release is ready when the two variants can be generated reproducibly, selected through each supported application's normal interface and removed without losing unrelated preferences or local edits. The installer should work offline from a versioned bundle. Adaptive switching is a separate, opt-in milestone.

## 2. Context and implementation route

The original conversation settled the name, visual direction, four targets and two variants. The implementation workspace contains no theme repository or generated assets. The planning Mac reported macOS 27.0, Xcode 27.2 and Codex CLI 0.167.0. Those versions are the first smoke-test candidates. Their presence alone does not establish compatibility.

| Route | Trade-off | Decision |
| --- | --- | --- |
| Shared tokens, generated native files, app-owned activation | One palette change propagates across targets. Export fixtures and native smoke tests take initial effort. | Recommended for release |
| Hand-maintained native files | Fast for a first visual experiment. Eight or more outputs can diverge as the palette changes. | Use only for fixture discovery and prototyping |
| Global preference editing with synchronised switching | Fewer manual clicks, with greater risk from private formats and app-owned settings. | Reserve automation for individually verified adapters |

User-level macOS installation is the baseline. The desktop Codex interface, global macOS appearance, system power settings and remote shell configuration are outside this plan's scope.

## 3. Assumption register

| ID | Assumption | Settling check and consequence |
| --- | --- | --- |
| A1 | The original brief established the colour direction without locking exact implementation values. | Review the proposed swatches on the target display. Adjust tokens before freezing screenshots. |
| A2 | The local Zed build loads a theme family from its documented user directory. | Record the Zed version and test discovery and selection for both entries. Document reload or restart behaviour observed. |
| A3 | A Terminal export can be safely reproduced from a clean, locally created profile. | Change a single swatch, export again, compare decoded fields and re-import. If the encoder cannot reproduce it reliably, use verified native exports and gate generator parity before release. |
| A4 | A generated Xcode workspace theme can be discovered in the documented user directory. | Save a disposable theme in the UI, compare single-field changes and test both generated themes in a clean account. Treat legacy format support as a separate matrix row. |
| A5 | Codex CLI can distinguish both custom theme names and render them adequately in Terminal.app and Zed. | Test `/theme`, restart persistence and sample fenced code and diffs in each host. Record actual colour behaviour and any fallback. |
| A6 | Endurance's visual choices suit battery use, with any energy gain dependent on hardware and workload. | Run the paired measurement protocol before making quantitative claims. |
| A7 | On-demand power detection is adequate for the first Adaptive release. | Test stable AC, battery and unknown readings, then decide whether unattended switching warrants a resident helper. |

## 4. Master palette and semantic contract

Use opaque sRGB `#RRGGBB` in source. The following are proposed implementation values. Store each value once as a swatch within its variant. Semantic roles and ANSI slots reference named swatches. Use canonical names **Vyntar Pulse** and **Vyntar Endurance** in menus, and stable slugs `pulse` and `endurance` in commands.

| Swatch | Pulse | Endurance | Roles and intended use |
| --- | --- | --- | --- |
| Midnight | `#0B1020` | `#090B10` | Editor and terminal background |
| Panel | `#121A2D` | `#101318` | Sidebar, menus, inactive tabs |
| Raised | `#1B2640` | `#191E27` | Hover, popovers, active tab and search chrome |
| Line | `#151E32` | `#12161E` | Current line |
| Edge | `#34425F` | `#303847` | Decorative separators |
| Selection | `#23334F` | `#263140` | Editor and terminal selection fill |
| Ice | `#EAF1FF` | `#E1E8F2` | Primary text, selection text, identifiers |
| Silver | `#B3C1DA` | `#AAB6C8` | Secondary text and active line number |
| Slate | `#99A9C6` | `#97A4B9` | Comments, inactive line numbers and muted text |
| Cyan | `#23F3F4` | `#82DCE2` | Focus, caret, function names |
| Violet | `#B289FF` | `#BCABEF` | Keywords, storage modifiers |
| Blue | `#81AEFF` | `#9ABAF0` | Types, links and informational diagnostics |
| Mint | `#83E5AE` | `#A0D4B0` | Strings, success and additions |
| Orchid | `#E7AEFF` | `#D2B5E5` | Numbers, booleans, constants and attributes |
| Amber | `#FFCB7C` | `#E7C89A` | Warnings, escapes and changed lines |
| Coral | `#FF8C9F` | `#EDA1AD` | Errors and removals |

Diff background roles must be explicit `null` (no coloured fill). Define `ui.background`, `ui.surface`, `ui.surface_raised`, `ui.border`, `ui.focus`, `text.primary`, `text.secondary`, `text.muted`, `editor.current_line`, `editor.selection.bg`, `editor.selection.fg`, `editor.caret`, `syntax.*`, `diagnostic.{error,warning,info,hint}` and `diff.{add,remove,change}.{fg,bg}`. Use Slate for hints and Silver for operators and punctuation. Interpolation should resolve its inner expression normally. Use Cyan for interpolation delimiters where the grammar exposes a separate capture. Keep parameter and local variable text neutral so function names and types stand out.

### ANSI 16

Apply identical slot order to the Zed terminal and the Terminal.app profiles. The normal black slot is deliberately lighter than the background so black foreground text remains legible on Midnight. Test inverse video and applications that use black as a fill, since the lifted slot affects those too. Store the explicit slot values below as swatches only where they differ from a role above.

| Slot | Name | Pulse | Endurance | Conventional use |
| --- | --- | --- | --- | --- |
| 0 | Black | `#7588A8` | `#758298` | Lifted black |
| 1 | Red | `#FF8C9F` | `#EDA1AD` | Error, removal |
| 2 | Green | `#83E5AE` | `#A0D4B0` | Success, addition |
| 3 | Yellow | `#FFCB7C` | `#E7C89A` | Warning |
| 4 | Blue | `#81AEFF` | `#9ABAF0` | Information |
| 5 | Magenta | `#B289FF` | `#BCABEF` | Violet emphasis |
| 6 | Cyan | `#23F3F4` | `#82DCE2` | Accent |
| 7 | White | `#B3C1DA` | `#AAB6C8` | Neutral |
| 8 | Bright black | `#99A9C6` | `#97A4B9` | Muted text |
| 9 | Bright red | `#FFB0BD` | `#F5BEC8` | Emphasised error |
| 10 | Bright green | `#A8F6C6` | `#BBE4C8` | Emphasised success |
| 11 | Bright yellow | `#FFE2A9` | `#F4DDB8` | Emphasised warning |
| 12 | Bright blue | `#A9C9FF` | `#B7CEF4` | Emphasised information |
| 13 | Bright magenta | `#E7AEFF` | `#D2B5E5` | Emphasised violet |
| 14 | Bright cyan | `#A5FBFF` | `#ACE9ED` | Emphasised accent |
| 15 | Bright white | `#EAF1FF` | `#E1E8F2` | High emphasis |

**Contrast gates.** Require at least 4.5:1 for normal text, syntax, comments and actionable status text against every background where the mapping places them, including selected text; diffs use the ordinary editor background. Check ANSI foregrounds against Midnight and test representative foreground/background combinations. Use 3:1 for essential focus, caret or indicator marks against the adjacent surface. Decorative separators can be subtler. Render diagnostics and diffs with native labels, icons, underlines or line markers where supported so meaning survives greyscale. Compute contrast as `(Llighter + 0.05) / (Ldarker + 0.05)` after sRGB linearisation. If a host preserves coloured syntax on a selection and a pair fails, adjust that fill or use a supported foreground override. [W3C contrast guidance](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)

### Battery and visual effects

- Ship both variants opaque and static. Pulse gets its energy from surface separation and small saturated accents. Endurance uses flatter surfaces, softer accents, no profile background image or blur, no gradient where configurable and a steady terminal cursor. Leave unrelated accessibility, rendering and font settings with the app or user.
- On a conventional backlit LCD, drawing black pixels does not switch off the backlight. Mini-LED LCD with local dimming may vary with the content, brightness and dimming behaviour. OLED power can respond to the pixels displayed, with results depending on luminance and content. Record the exact panel and external monitor setup before comparing results.
- Brightness, refresh rate, builds, simulators, indexing and background activity can overwhelm a small theme effect. Keep the battery-mode promise to a calmer visual profile. Low Power Mode is a separate macOS control. [Apple Battery settings](https://support.apple.com/guide/mac-help/change-battery-settings-mchlfc3b7879/mac)
- Measure paired Pulse/Endurance runs on battery at fixed brightness, refresh rate, window layout and workload. Disable automatic brightness for the test session or record how it was controlled, use the same Low Power Mode state, let indexing and temperature settle, and alternate run order across at least three pairs. Run idle reading and a repeatable development workload separately. Record available energy readings, interval length, app versions and variability. Use Activity Monitor Energy Impact as a comparative proxy only. Report an inconclusive result when the difference is within run-to-run noise.

## 5. Repository and generation

```text
vyntar/
├── install.sh
├── update.sh
├── uninstall.sh
├── bin/vyntar
├── palette/
│   ├── palette.json
│   ├── semantics.json
│   └── ansi.json
├── generators/
│   ├── generate-themes.py
│   ├── validate-palette.py
│   ├── adapters/
│   ├── fixtures/
│   └── schemas/
├── themes/
│   ├── zed/vyntar.json
│   ├── terminal/Vyntar-Pulse.terminal
│   ├── terminal/Vyntar-Endurance.terminal
│   ├── xcode/workspace/
│   └── codex/
│       ├── vyntar-pulse.tmTheme
│       └── vyntar-endurance.tmTheme
├── scripts/lib/
│   ├── artwork.sh
│   ├── detect.sh
│   └── transaction.sh
├── tests/{fixtures,shell,snapshots}/
├── assets/previews/
├── README.md
├── CHANGELOG.md
└── LICENSE
```

- [ ] Define strict JSON inputs with shared base swatches and named variant overrides. Resolve each role and ANSI slot to one colour. Reject missing roles, unresolved names, unexpected keys, malformed hex and out-of-range slots.
- [ ] Implement Python 3 generators for contributors and CI. Use JSON and plist serializers, with a narrowly scoped native encoder for colour archives if needed. Use the verified fixture's colour space and representation. Keep version-specific key maps in the adapters and document unsupported roles.
- [ ] Generate into a staging directory. Validate before replacing checked-in outputs. Ensure stable encoding, field order and filenames, with no timestamps, user paths or arbitrary identifiers in the output. Compare clean regeneration with the committed files. Where an OS encoder serialises opaque data non-deterministically, pin the generation environment or prove canonical output before claiming byte reproducibility.
- [ ] Build a versioned release bundle containing the scripts, generated themes and a manifest with the release version and SHA-256 digests of packaged assets. Keep Python, build tooling and downloads out of normal installs. Verify asset integrity before mutating user files. Publish a digest for the bundle through the trusted release channel.

## 6. Integration playbooks

### Zed

- [ ] Generate one theme-family JSON with `name`, `author` and both dark variants. Pin the supported schema revision in validation. Populate editor and UI surfaces, selection, caret, tabs, focus, statuses and diagnostics, Git diff colours, syntax and all ANSI slots using keys confirmed by the schema. [Zed theme schema](https://zed.dev/schema/themes/v0.2.0.json)
- [ ] Map captures used by the fixture languages, including `comment`, `keyword`, `function`, `string`, `type` and `number`. Confirm narrower captures and their fallback behaviour on the supported build.
- [ ] Install to the documented `~/.config/zed/themes/vyntar.json`. Select with the Theme Selector. Keep `settings.json` untouched in the default installer. Zed's system mode follows OS light/dark appearance. Vyntar's variants are both dark, so power-aware selection requires a separate opt-in mechanism. [Zed local themes and selection](https://zed.dev/docs/themes)
- [ ] Verify both variants with open and newly started Zed windows. Check the integrated terminal, search match and selected code. Record whether existing user overrides change the result.

### Terminal.app

- [ ] Create a disposable profile in Terminal and export it. Use the export as the versioned reference for names, cursor, selection, foreground, background and all 16 ANSI fields. Compare separate exports with individual values changed. If colour fields are archived data, reproduce the verified native encoding and check re-import in Terminal. A valid plist is only the first check.
- [ ] Audit fixture settings for commands, keyboard mappings, bell, window and shell behaviour. Retain only verified safe profile settings. Enable ANSI display and test the effect of the profile's bold/bright option with explicit normal and bright escape codes. Check selection, inverse and both cursor appearances. [Terminal profile text settings](https://support.apple.com/guide/terminal/trmltxt/mac)
- [ ] Stage the two .terminal files for manual import via **Terminal → Settings → Profiles → Action → Import**. Before replacing an imported profile, export it and record the startup/default choices. If imports duplicate names, switch away, remove the old profile through the UI and import the replacement. Use the old export to reverse that change. Open a fresh window with the chosen profile and test it. Existing tabs may keep their current settings. [Terminal import and export](https://support.apple.com/guide/terminal/import-and-export-terminal-profiles-trml4299c696/2.15/mac/27)
- [ ] Keep staging status distinct from import status. Uninstall instructions cover selecting a different profile before removing an imported Vyntar profile, and keeping any profile the user customised.

### Xcode

- [ ] Start with the documented modern `.xcworkspacecolortheme` format. Save a native test theme on the target Xcode build and compare exports or saved files after a single change. Generate using the verified structure and colour format. Set explicit syntax colours where supported so palette-derived defaults do not replace them. Preserve default fonts or omit font overrides where supported.
- [ ] Verify placement under `~/Library/Developer/Xcode/UserData/FontAndColorThemes/` and manual selection in **Settings → Appearance → Theme → Choose**. Check workspace-specific selection, Swift editor colours, live issues, console output and selection. Record native limitations and any restart required. [Apple Xcode theme guide](https://developer.apple.com/documentation/xcode/customizing-your-workspace-using-themes)
- [ ] Treat legacy `.xccolortheme` as a separate adapter only after an actual earlier-version fixture and successful round trip. Apple also documents an older import path using `.xcolortheme`. Record the extension and workflow observed for each supported version. Avoid renaming one format into another or claiming control over fonts, diagnostics, breakpoints or chrome that the tested format does not expose.

### Codex CLI

- [ ] Generate two XML TextMate `.tmTheme` plists. Give each a distinct display name, a global settings entry for defaults and supported scope rules such as `comment`, `keyword`, `string`, `constant.numeric`, `entity.name.function` and `entity.name.type`. Exercise representative diff scopes and verify how the actual renderer handles them.
- [ ] Install to the effective Codex home, `${CODEX_HOME:-$HOME/.codex}/themes/` for the proposed default path resolution. Verify custom home handling and picker discovery. Select via `/theme`, which persists to `tui.theme` in the Codex user config. Use the value written by the picker as evidence if automation is added later. The default installer does not edit TOML. [OpenAI Codex CLI customisation](https://learn.chatgpt.com/docs/cli-customization?translationFallback=de-DE#syntax-highlighting-and-themes)
- [ ] Test the two colour paths separately. The TextMate file styles supported syntax in fenced code and diffs. Applications writing ANSI slots use the host palette, while direct RGB, higher indexed colours and app-defined styles can render differently. Verify the full TUI empirically and document those differences. Avoid forcing `TERM` or `COLORTERM` to advertise unsupported capabilities.
- [ ] Test in Terminal.app, Zed's terminal and a reduced-colour environment. Compare standard, bright and bold ANSI, 256-colour output and a 24-bit swatch. When the picker or colour depth is unavailable, retain host ANSI and document that fallback. Switch to a built-in Codex theme via the picker before removing an actively selected Vyntar theme.

## 7. Installer, updates and recovery

Use Bash compatible with macOS's bundled Bash 3.2 and common macOS tools. Put shared detection, rendering and transaction code behind the three public entry points. Require an explicit app subset only when the caller wants one. Use `--dry-run`, `--non-interactive`, `--plain` and a testable `--target zed,terminal,xcode,codex` interface. Skip absent apps with reasons. Return a clear failure when an explicitly requested target is unavailable, when no requested target can be serviced, or when an actionable conflict remains.

| Entry point | Expected behaviour |
| --- | --- |
| `./install.sh` | Preflight the local bundle and detected targets. Copy both variants for supported file-based integrations and stage Terminal imports. Print separate activation instructions. Leave user app selections and shell startup files alone by default. |
| `./update.sh` | Accept an explicit local versioned bundle, validate it and compare its manifest with the installed record. Replace only tracked, unmodified files. Keep the prior installed version recoverable. Give separate Terminal re-import instructions. |
| `./uninstall.sh` | Stop an enabled Adaptive helper if present. Remove only unchanged owned files and staged assets, retain edits and recovery records, and list manual deactivation/removal steps for app-owned selections and imported profiles. |
| `vyntar status` / `doctor` | Report installed versus staged versus manual activation, recorded versions, missing apps and hash mismatches. Avoid dumping application config or credentials. |
| `vyntar preview` | Print both palette previews and the host's 16 ANSI swatches. |
| `vyntar restore <transaction-id>` | Dry-run or restore a recorded state with the same ownership and drift checks used by update. |
| `vyntar theme pulse\|endurance\|auto` | Set the Vyntar preference for status and guidance. Apply only explicitly managed, verified adapters. Clearly list remaining manual steps. |

Install the management command in a Vyntar-owned directory under the user data root. Show its full path and optional PATH instructions. A dry run performs reads and emits a plan with zero persistent filesystem writes. Missing targets on a general install should be marked skipped, while profile imports are marked manual. Use exit `0` for completed/no-op actions with expected manual steps, `1` for runtime failures or conflicts, and `2` for invalid arguments.

### Transaction model

1. Resolve absolute paths, quote arguments and preflight the entire selected set before mutation. Reject symlink destinations and unexpected symlink ancestors unless the effective location is explicitly trusted and verified. Treat a pre-existing unmanaged file as a collision, even if its bytes match. No implicit adoption or blanket force flag.
2. Keep a private state directory under `~/Library/Application Support/Vyntar/`, using mode `0700` and `umask 077`. Use an atomic lock directory for all writers. Store an owner identity and report stale locks with recovery instructions. Recheck ownership and file digests inside the lock before writing. App processes may write independently, so report concurrent changes and preserve them.
3. Write a pending transaction journal before touching any destination. Record action, bundle version, target, expected old/new hashes, previous existence, path and backup metadata. Make private backups of affected files with permissions preserved, or record that a file was absent. Keep the original baseline and the previous release snapshot distinct.
4. Stage temporary files in each destination directory, validate payloads and rename on the same filesystem. Record progress so interruption between rename and journal update can be reconciled by comparing current, old and new hashes. Commit the ownership manifest only after every selected mutation succeeds. Track created directories and remove them only if empty and owned.
5. On failure or catchable interruption, undo completed operations in reverse order. After an uncatchable kill, detect the pending journal on the next run and reconcile by hashes. If a current hash matches neither recorded version, stop and report the conflict and backup path. Keep recovery records until the user explicitly clears them.
6. Treat manual app import and activation as separate operations outside the filesystem transaction. Document how to switch away or re-import from the user's backup. Where a future adapter edits a single managed setting, snapshot its original presence and value and restore only if its current value still matches the last Vyntar write.

### Script artwork

Render once on an interactive terminal using cyan for the emblem, violet for the name, and green, amber or red for status. Use words as well as glyphs. Keep line width under 60 columns and avoid clearing the screen or animating progress.

```text
╭─────────────────────────────────╮
│  ╲╱  V Y N T A R                │
│      P R E C I S I O N           │
│      I N   C O L O U R           │
╰─────────────────────────────────╯
✓ OK       Zed themes installed
◇ MANUAL   Import the Terminal profiles
! CONFLICT Edited file kept
```

Use fixed `printf` format strings, SGR resets per coloured line, and terminfo or a verified TTY capability check. Use 16-colour SGR as the baseline and optional RGB only on confirmed support. Respect `NO_COLOR`, `TERM=dumb`, redirected output and `--plain`. Fall back to ASCII if the locale is not UTF-8, and provide an explicit plain override for fonts with poor glyph coverage. Keep stdout predictable for pipes and put warnings on stderr.

## 8. Optional Vyntar Adaptive

**First release.** Keep Adaptive off by default. On explicit `auto`, resolve power on demand and report the recommended variant. A manual `pulse` or `endurance` takes priority until the user re-enables `auto`. A shell implementation may read the first line of `LC_ALL=C pmset -g batt` and match the reported power source. Use the source label even if the battery status line says discharging. Treat unexpected output, a desktop without a battery, unavailable APIs and UPS readings as unknown. Keep the current selection when uncertain.

**Optional unattended release.** Prefer a small user-level IOKit helper subscribing to power-source notifications, registered only by explicit opt-in. Read current source on start and wake, coalesce transitions for 10 seconds, then read again before applying. Cache the last applied mode, skip identical states and use the installer's lock and drift checks. A resident helper needs an idle-energy check before release. If that check is inconclusive or the helper is disproportionate, keep the on-demand mode. [Apple IOKit power-source notifications](https://developer.apple.com/documentation/iokit/1523868-iopsnotificationcreaterunloopsou)

| Target | Adaptive policy |
| --- | --- |
| Zed | Candidate for a single-key managed change after proving a comment-preserving JSONC edit, current-setting drift detection, effective precedence and reload behaviour. Preserve the existing light branch and mode for dynamic settings. Defer on an unsupported shape or an unrelated theme selection. |
| Terminal.app | Report which imported profile to choose for the next window. Preserve running sessions and user defaults. |
| Xcode | Report the suggested theme for manual selection. Preserve workspace overrides and leave Xcode running. |
| Codex CLI | Report the suggested theme through `/theme`. Consider a next-launch-only adapter after verifying an official per-invocation override and exact picker values. Keep active sessions intact. |

Disabling Adaptive unloads its helper, clears its managed state and offers guarded restoration of any managed setting. Uninstall uses the same path. Test sleep/wake, repeated notifications, rapid cable changes, unknown state, manual overrides, user edits and shutdown during a transition. Adaptive changes theme selection only.

## 9. Phased roadmap and implementation checklist

Effort bands are relative planning estimates. The named directories below are proposed locations. All items are reversible within the guarded install and rollback model.

| Phase and milestone | ID | Implementation checklist | Where | Effort | Depends on | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| 1 · Palette and build contract | VY-01 | Freeze role names, baseline swatches and ANSI mapping | `palette/` | M | — | Validation resolves every role and reports contrast pairs by target |
| 1 · Palette and build contract | VY-02 | Capture native reference files and pin schema and app versions | `generators/fixtures/` | M | — | Single-field diffs explain native structures and each original fixture reloads |
| 2 · Pulse in the four targets | VY-03 | Generate Pulse for Zed and Terminal first | `generators/adapters/`, `themes/` | M | VY-01, VY-02 | Selected Zed theme and imported Terminal profile match ANSI preview |
| 2 · Pulse in the four targets | VY-04 | Generate Pulse for Xcode and Codex CLI | `generators/adapters/`, `themes/` | L | VY-03 | Xcode loads the theme and Codex picker persists it through restart |
| 3 · Both variants and lifecycle | VY-05 | Derive Endurance and capture reference previews | `palette/`, `themes/`, `assets/previews/` | M | VY-04 | Shared role names, both variants pass contrast and native checks |
| 3 · Both variants and lifecycle | VY-06 | Implement transactions, scripts, artwork and management commands | `scripts/`, `bin/`, root scripts | L | VY-05 | Repeated actions are no-ops and injected failures restore prior state |
| 4 · Release candidate | VY-07 | Run compatibility checks, package the release and document manual actions | `tests/`, `README.md`, `CHANGELOG.md` | M | VY-06 | Fresh-user install, activation, update, restore and uninstall pass |
| 5 · Optional Adaptive | VY-08 | Add on-demand detection and decide whether to ship the helper | `bin/vyntar`, `tests/` | M for on-demand | VY-07 | Mock and real transitions pass, manual override wins and idle impact is recorded before enabling a helper |

**Critical path** · VY-01 and VY-02 converge at VY-03 → VY-04 → VY-05 → VY-06 → VY-07. Fixture discovery can proceed alongside palette work. Draft tests and documentation against the public command contract while the lifecycle code is under development.

## 10. Risks, cut line and acceptance

| Failure | Early signal | Response |
| --- | --- | --- |
| A native format changes or silently ignores fields | Plist validation passes but a swatch or theme is missing in the app | Require native round trips per supported version. Narrow the support matrix to verified combinations. |
| A personal theme or setting is overwritten | Destination collision, hash mismatch or unexpected settings diff | Abort the transaction on conflicting writes, preserve both files and surface the backup or manual merge path. |
| The theme looks good in screenshots but hides feedback | Dim comments in selected code, missing diff signs, illegible inverse ANSI | Test actual contexts and revise contrast pairs or mappings before release. |
| Adaptive adds overhead or switches at the wrong time | Frequent callbacks, visible churn or measurable idle impact | Debounce and deduplicate. Release on-demand mode if the helper fails the gate. |

Xcode format verification is the weakest estimate. Start native fixture discovery early. For a time-constrained preview, keep VY-01–VY-05 on the first verified macOS/Xcode combination and ship manual steps only under a preview label. The full release still requires VY-06 and VY-07. Defer Adaptive and legacy format work first. If an adapter cannot round-trip safely, remove its version from the supported matrix. Keep the full release blocked until each of the four integrations has at least one verified route.

### Verification checklist

- [ ] **Build and contract** · Regenerate from a clean checkout twice and compare outputs. Validate Zed JSON against its pinned schema, validate plist containers with `plutil -lint`, and independently verify expected colour keys, channel ranges, named variants and all 16 ANSI values.
- [ ] **Visual acceptance** · On the recorded app versions, review both themes on Swift, TypeScript, Bash, SQL, JSON, Markdown and Git diff samples where each target supports them. Check diagnostics, focused and selected states, comments, hyperlinks, prompts and colour-blind/greyscale legibility. Save one clean screenshot per variant and integration for the compatibility record.
- [ ] **Terminal acceptance** · Exercise SGR foreground 30–37 and 90–97, backgrounds 40–47 and 100–107, bold, inverse, reset, 256-colour and 24-bit samples. Check both hosts with a fresh tab and after profile changes. Confirm that the installer leaves session behaviour and startup/default choices alone.
- [ ] **Lifecycle acceptance** · With isolated user fixtures, test a clean install, repeated install, same-version update, upgrade, rollback to the prior release, uninstall and repeated uninstall. An unmodified target returns to its baseline, while unrelated files and app settings stay byte-identical. Hash the tree before and after a dry run.
- [ ] **Failure and race coverage** · Cover missing apps, paths with spaces, custom Codex home, read-only directories, malformed bundles, edited and unmanaged files, symlink destinations, simultaneous writers and simulated termination before and after a rename. Confirm the lock, recovery path and backup ownership. Test that modified files survive uninstall.
- [ ] **Presentation and accessibility** · Use a pseudo-terminal for snapshots. Check UTF-8, ASCII fallback, redirected output, `NO_COLOR`, narrow terminal widths, clean SGR resets and readable status text without colour.
- [ ] **Real-machine sign-off** · Use a clean macOS user profile for the documented activation and removal flow in all four integrations. Record actual macOS, Terminal, Xcode, Zed and Codex versions, terminal capability, any reload requirement, and any features deferred for compatibility.
- [ ] **Adaptive gate** · If included, record real AC-to-battery and battery-to-AC transitions, the manual override and disable/uninstall path. Verify there are no writes on unchanged or unknown state, no app restarts, and no residual helper after uninstall.

## 11. Open decisions

- **Initial compatibility range.** Start with the planning Mac's toolchain and the installed Zed build. Add earlier Xcode versions only after native fixture tests.
- **Terminal slot 0.** Start with the proposed lifted black and keep it only if both readable black foregrounds and acceptable inverse/fill behaviour survive real terminal fixtures.
- **Automatic switching.** Ship on-demand recommendations first. Promote Zed to managed switching after its JSONC and reload checks, and introduce a resident helper only after the idle-energy gate.
- **Release ownership and licence.** Confirm the publishing account and licence before distributing the bundle.

# Compatibility and verification

Version: **0.1.0-preview.1** · checked 2026-11-10.

This record distinguishes automated checks from native activation. A file parsing successfully is not proof that every setting is honoured.

| Integration | Locally identified version | Evidence | Still requires native acceptance |
| --- | --- | --- | --- |
| Zed | 1.27.0 / 20261104.154313 | Both variants validate against the vendored v0.2.0 schema plus current-source diff overlay; all style keys accounted for; all 16 ANSI slots match Terminal. | Discovery, selection, restart, diff/word fills, selected syntax, diagnostics and integrated terminal. |
| Terminal.app | 2.15 / 488 | Valid XML plist; all 21 NSColor archives decoded using AppKit into intended sRGB channels, including all ANSI slots. No font, shell, command or keyboard-map payload. | Import and re-export, new-window appearance, selection, bold/bright, inverse and cursor. |
| Xcode | 27.2 / 25400.63.5 | Modern workspace JSON structure compared with local files; sRGB OKLCH conversion independently inverted for every generated colour; no font recipe. | File discovery and native load/save round trip; Swift, issues, console, selection and workspace overrides. |
| Codex CLI | 0.167.0 | XML TextMate plists; actual ANSI-index encoding and terminal-default diff marker checked against upstream renderer source; scope contracts tested. | `/theme` discovery and persistence; real fences and diffs in both terminal hosts; reduced colour-depth behaviour. |

macOS/app build identification was read from local application metadata. No app selections or user profiles were changed. Full four-app visual acceptance is pending; this is not a production support matrix.

## Format evidence

- [Zed published theme schema](https://zed.dev/schema/themes/v0.2.0.json), vendored verbatim under `generators/schemas/`.
- Current Zed [serialized fields](https://github.com/zed-industries/zed/blob/main/crates/settings_content/src/theme.rs) and [fallback resolution](https://github.com/zed-industries/zed/blob/main/crates/theme_settings/src/schema.rs). Explicit transparent `editor.diff_hunk.{added,deleted}.{background,hollow_background,hollow_border}` defeats the native tinted fallbacks; `version_control.word_{added,deleted}` also uses transparent fill. Status/gutter foregrounds keep their semantic colours. The overlay records the downloaded declaration file's SHA-256. Source on `main` can move; older installed builds must be checked interactively.
- [Apple workspace themes](https://developer.apple.com/documentation/xcode/customizing-your-workspace-using-themes). The JSON recipe has explicit overrides for verified local keys, uses sRGB gamut and omits fonts. No claim is made that this controls Xcode diff backgrounds, diagnostics or all window chrome. Those remain app-owned where no verified field is available.
- Terminal's system `Pro.terminal` established the outer plist and keyed-archive structure. A new AppKit-created sRGB NSColor established the colour-space archive. Calibrated RGB was replaced with explicit sRGB components; the generated archives decoded to their original channels to ten decimal places.
- [Official Codex theme workflow](https://learn.chatgpt.com/docs/cli-customization), [colour conversion](https://github.com/openai/codex/blob/main/codex-rs/tui/src/render/highlight.rs) and [diff handling](https://github.com/openai/codex/blob/main/codex-rs/tui/src/diff_render.rs). Alpha `00` carries an ANSI index in the red byte; alpha `01` means terminal default. The scope marker is essential: missing diff backgrounds activate hardcoded tints. ANSI-16 mode in the current upstream renderer is foreground-only. Historical releases may differ.

## Acceptance session

For **each variant**, in each app's normal theme interface:

1. Select the theme and open the samples under `tests/fixtures/` (languages that the app supports).
2. Inspect comments, keywords, strings, functions, types, neutral variables, punctuation, links and escapes.
3. Select colourful code and search within it; inspect the caret, line numbers, focus, issue indicators and disabled states.
4. Inspect a real Git diff. `+`/`-` must be readable, with no added/removed line or word fill where the app supports control. Record native limitations instead of claiming suppression.
5. In Terminal and Zed, run `bash tests/fixtures/terminal.sh`. Check foreground/background slots, explicit bright codes, bold, inverse/reset and truecolour. Never change capability environment variables just to pass.
6. Restart/reopen and verify selection persists. Save one screenshot per app and variant, recording app/OS versions and terminal capability.
7. Export/re-save a disposable profile/theme where supported; compare colours, then remove it through the app. Test install/update/restore/uninstall in a clean macOS account before promoting to stable.

## Automated coverage and limits

The test suite covers deterministic regeneration, known Zed keys, malformed colour contracts, all contrast pairs, independent Xcode colour inversion, Terminal archives and cross-host ANSI parity, TextMate diff rules, isolated paths with spaces/custom Codex home, dry runs, no-op install, update/restore, ownership collisions, symlinks, concurrent writer locks, interrupted journal reconciliation, rollback and edited-file preservation. Native AppKit archive decoding is a separate macOS-only verification script.

The SVG is a designed palette/code comparison, visually rendered and inspected, not a screenshot or simulation of an application's exact syntax grammar. Contrast gates verify mapped colours, not arbitrary third-party ANSI foreground/background combinations. No battery measurements, legacy Xcode support, resident power helper, app selection automation, font changes, publishing or real-user installation is included.

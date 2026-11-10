#!/usr/bin/env python3
"""Generate native themes deterministically. Run --check in CI."""
import argparse
import hashlib
import json
import os
import plistlib
import tempfile
from pathlib import Path
from theme_core import ROOT, load, rgb, oklch, contrast_report

# Alpha 01 is Codex's explicit terminal-default marker, NOT transparency.
DEFAULT = '#00000001'
ANSI_NAMES = 'black red green yellow blue magenta cyan white bright_black bright_red bright_green bright_yellow bright_blue bright_magenta bright_cyan bright_white'.split()
SYNTAX = {
 'attribute':'attribute', 'boolean':'constant', 'comment':'comment', 'comment.doc':'comment',
 'constant':'constant', 'constructor':'type', 'embedded':'variable', 'emphasis':'variable',
 'emphasis.strong':'variable', 'enum':'type', 'function':'function', 'function.builtin':'function',
 'function.method':'function', 'hint':'comment', 'keyword':'keyword', 'label':'attribute', 'link_text':'link',
 'link_uri':'link', 'namespace':'type', 'number':'number', 'operator':'operator',
 'predictive':'comment', 'preproc':'keyword', 'primary':'variable', 'property':'variable',
 'punctuation':'punctuation', 'punctuation.bracket':'punctuation', 'punctuation.delimiter':'punctuation',
 'punctuation.special':'interpolation', 'string':'string', 'string.escape':'escape', 'string.regex':'escape',
 'string.special':'interpolation', 'string.special.symbol':'constant', 'tag':'type', 'tag.doctype':'comment',
 'text.literal':'string', 'title':'function', 'type':'type', 'type.builtin':'type',
 'variable':'variable', 'variable.parameter':'variable', 'variable.special':'attribute'}

def json_bytes(obj):
    return (json.dumps(obj, indent=2, ensure_ascii=False) + '\n').encode()

def zed(t):
    r, s = t['roles'], t['swatches']
    style = {}
    groups = {
     'midnight': 'background editor.background editor.gutter.background terminal.background terminal.ansi.background tab.active_background toolbar.background',
     'panel': 'surface.background panel.background status_bar.background title_bar.background title_bar.inactive_background tab_bar.background tab.inactive_background editor.subheader.background element.background element.disabled ghost_element.disabled scrollbar.track.background',
     'raised': 'elevated_surface.background element.hover element.active ghost_element.hover ghost_element.active',
     'edge': 'border border.variant border.disabled pane_group.border editor.active_wrap_guide editor.indent_guide_active panel.indent_guide_active panel.indent_guide_hover scrollbar.thumb.background scrollbar.thumb.border scrollbar.track.border',
     'line': 'editor.active_line.background editor.highlighted_line.background editor.wrap_guide editor.indent_guide panel.indent_guide',
     'selection': 'element.selected ghost_element.selected search.match_background drop_target.background editor.document_highlight.read_background editor.document_highlight.write_background editor.document_highlight.bracket_background scrollbar.thumb.hover_background',
     'ice': 'text icon editor.foreground terminal.foreground terminal.bright_foreground',
     'silver': 'editor.active_line_number icon.placeholder text.placeholder',
     'slate': 'text.muted text.disabled icon.muted icon.disabled editor.line_number editor.invisible terminal.dim_foreground hidden ignored unreachable predictive hint',
     'cyan': 'text.accent icon.accent border.focused border.selected pane.focused_border panel.focused_border',
     'mint': 'created success', 'coral': 'deleted error', 'amber': 'modified conflict warning', 'blue': 'info renamed link_text.hover'}
    for swatch, keys in groups.items():
        style.update({k: s[swatch] for k in keys.split()})
    for name in 'created deleted modified renamed conflict error warning info hint success hidden ignored unreachable predictive'.split():
        style[name + '.background'] = '#00000000'
        style[name + '.border'] = style[name]
    # Current Zed has dedicated hunk and word-diff fills beyond v0.2.0.
    for action in ('added', 'deleted'):
        for suffix in ('background', 'hollow_background', 'hollow_border'):
            style['editor.diff_hunk.' + action + '.' + suffix] = '#00000000'
    for status, swatch in [('added','mint'),('deleted','coral'),('modified','amber'),('renamed','blue'),('conflict','amber'),('ignored','slate')]:
        style['version_control.' + status] = s[swatch]
    style['version_control.word_added'] = '#00000000'
    style['version_control.word_deleted'] = '#00000000'
    style['border.transparent'] = '#00000000'
    style['ghost_element.background'] = '#00000000'
    style['background.appearance'] = 'opaque'
    style['players'] = [{'cursor': s[c], 'background': s[c], 'selection': s['selection']} for c in ['cyan','violet','mint','amber','coral','blue']]
    style['accents'] = [s[c] for c in ['cyan','violet','blue','mint','orchid','amber']]
    style['syntax'] = {k: {'color': r['syntax.' + role], 'font_style': 'normal', 'font_weight': 400} for k, role in SYNTAX.items()}
    for capture, role in [('diff.plus','add'),('diff.minus','remove'),('diff.delta','change')]:
        style['syntax'][capture] = {'color': r['diff.'+role+'.fg'], 'background_color':'#00000000','font_style':'normal','font_weight':400}
    for i, name in enumerate(ANSI_NAMES):
        style['terminal.ansi.' + name] = t['ansi'][i]
    for i, name in enumerate(ANSI_NAMES[:8]):
        style['terminal.ansi.dim_' + name] = t['ansi'][i]
    return {'name': t['name'], 'appearance':'dark', 'style':style}

SCOPES = {
 'comment': 'comment, punctuation.definition.comment',
 'keyword': 'keyword, storage',
 'string': 'string',
 'number': 'constant.numeric',
 'constant': 'constant.language, constant.character, constant.other, support.constant',
 'function': 'entity.name.function, support.function, variable.function',
 'type': 'entity.name.type, entity.name.class, support.type, support.class, entity.name.namespace',
 'attribute': 'entity.other.attribute-name, meta.annotation, entity.name.tag',
 'variable': 'variable, meta.definition.variable',
 'operator': 'keyword.operator, punctuation',
 'escape': 'constant.character.escape',
 'interpolation': 'punctuation.section.interpolation, punctuation.definition.template-expression',
 'link': 'markup.underline.link, markup.underline.link string, meta.link',
}
ANSI_ROLE = {'comment':8,'keyword':5,'string':2,'number':13,'constant':13,'function':6,'type':4,'attribute':13,'variable':15,'operator':7,'escape':3,'interpolation':6,'link':4}

def tmtheme(t, ansi=False):
    def fg(role):
        return '#%02X000000' % ANSI_ROLE[role] if ansi else t['roles']['syntax.'+role]
    settings = [{'settings': {'foreground': DEFAULT if ansi else t['roles']['text.primary'], 'background': DEFAULT, 'caret': '#06000000' if ansi else t['roles']['editor.caret'], 'selection': t['roles']['editor.selection.bg']}}]
    for role, scope in SCOPES.items():
        settings.append({'name':role.title(), 'scope':scope, 'settings':{'foreground':fg(role), 'fontStyle':''}})
    for name, scope, slot in [('add','markup.inserted, diff.inserted',2),('remove','markup.deleted, diff.deleted',1),('change','markup.changed, diff.changed',3)]:
        settings.append({'name':'Diff '+name, 'scope':scope, 'settings':{'foreground':'#%02X000000' % slot if ansi else t['roles']['diff.'+name+'.fg'], 'background':DEFAULT, 'fontStyle':''}})
    settings.extend([
      {'name':'Diff headers','scope':'meta.diff.header, meta.diff.range','settings':{'foreground':fg('type'),'fontStyle':''}},
      {'name':'Invalid','scope':'invalid','settings':{'foreground':'#01000000' if ansi else t['roles']['diagnostic.error'],'fontStyle':''}},
      {'name':'Markdown headings','scope':'markup.heading','settings':{'foreground':fg('function'),'fontStyle':'bold'}},
    ])
    return plistlib.dumps({'name':t['name'] + (' ANSI' if ansi else ''), 'author':'Christopher Nicholson', 'settings':settings}, sort_keys=False)

# Minimal NSKeyedArchiver NSColor calibrated RGB, decoded by AppKit in verification.
def nscolor(hexvalue):
    # Native macOS 27 NSColor archive supplies the sRGB ICC profile. Components
    # are replaced, not archived by an OS encoder, so output stays reproducible.
    archive = plistlib.loads((ROOT/'generators/fixtures/srgb-nscolor.bplist').read_bytes())
    obj = archive['$objects'][1]
    obj['NSComponents'] = (' '.join(format(v, '.10g') for v in (*rgb(hexvalue), 1))).encode()
    obj.pop('NSRGB', None)  # Avoid a stale calibrated-RGB fallback.
    return plistlib.dumps(archive, fmt=plistlib.FMT_BINARY, sort_keys=False)

def terminal(t):
    r = t['roles']
    d = {'name':t['name'],'type':'Window Settings', 'ProfileCurrentVersion':2.07, 'BackgroundBlur':0.0, 'CursorBlink':False, 'CursorType':1, 'UseBrightBold':False, 'ANSIDisplay':True}
    for key, role in {'BackgroundColor':'ui.background','TextColor':'text.primary','TextBoldColor':'text.primary','CursorColor':'editor.caret','SelectionColor':'editor.selection.bg'}.items():
        d[key] = nscolor(r[role])
    for name, colour in zip(ANSI_NAMES, t['ansi']):
        key = 'ANSI' + ''.join(p.title() for p in name.split('_')) + 'Color'
        d[key] = nscolor(colour)
    return plistlib.dumps(d, sort_keys=False)

XCODE = {
 'plainText':'ice','comment':'slate','commentEmphasized':'silver','keyword':'violet','keyword.attribute':'orchid',
 'string':'mint','string.regex':'amber','number':'orchid','number.character':'orchid',
 'typeDeclaration':'blue','memberDeclaration':'cyan','projectType':'blue','otherType':'blue',
 'projectType.class':'blue','otherType.class':'blue','projectType.type':'blue','otherType.type':'blue',
 'projectMember':'ice','otherMember':'ice','projectMember.function':'cyan','otherMember.function':'cyan',
 'projectMember.variable':'ice','otherMember.variable':'ice','projectMember.constant':'orchid','otherMember.constant':'orchid',
 'preprocessor':'violet','preprocessor.macro':'orchid','preprocessor.macroSystem':'orchid',
 'link':'blue','markdown':'silver','debugger':'cyan','consoleBackground':'midnight','insertionPointColor':'cyan','invisibles':'slate'}

def xcode(t):
    s = t['swatches']
    overrides = {k:{'color':oklch(s[v])} for k,v in XCODE.items()}
    overrides.update({k:{'colorWithOpacity':oklch(s[v])} for k,v in [('currentLineHighlight','line'),('selectedTextBackgroundColor','selection')]})
    return json_bytes({'fileVersion':1,'recipe':{'background':{'customColor':oklch(s['midnight'])},'colorScheme':'dark','palette':{'primary':{'hue':{'intensity':.5,'radians':oklch(s['cyan'])['hue']['radians']}},'secondary':{'custom':oklch(s['panel'])},'colorOverrides':overrides}},'showsInAllColorSchemes':False})

def preview(themes):
    # Portable vector artwork, generated from the same tokens as the themes.
    from html import escape
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1040" viewBox="0 0 1440 1040">', '<rect width="1440" height="1040" fill="#06080D"/>']
    for n,(slug,t) in enumerate(themes.items()):
        s=t['swatches']; x=40+n*710
        parts += [f'<g transform="translate({x},40)">', f'<rect width="650" height="960" rx="18" fill="{s["midnight"]}" stroke="{s["edge"]}"/>',f'<path d="M28 30l12 22 12-22" fill="none" stroke="{s["cyan"]}" stroke-width="3"/>',f'<text x="72" y="52" fill="{s["ice"]}" font-family="sans-serif" font-size="25" letter-spacing="5">VYNTAR</text>', f'<text x="28" y="99" fill="{s["silver"]}" font-family="sans-serif" font-size="16">{t["name"]} · Precision in Colour</text>',f'<rect x="16" y="128" width="618" height="438" rx="8" fill="{s["panel"]}"/>']
        lines=[('slate','// A calm surface. A precise signal.'),('violet','import Foundation'),('blue','struct Theme: Sendable {'),('ice','    let name: String'),('ice','    let accents: [String]'),('cyan','    func render() -> String {'),('mint','        "Precision in Colour"'),('silver','    }'),('silver','}'),('orchid','let contrast = 4.5'),('amber','// Warnings stay visible.'),('coral','// Errors stay unmistakable.')]
        for i,(c,line) in enumerate(lines):
            y=164+i*31
            parts += [f'<text x="30" y="{y}" fill="{s["slate"]}" font-family="monospace" font-size="14">{i+1:02}</text>',f'<text x="66" y="{y}" fill="{s[c]}" font-family="monospace" font-size="17">{escape(line)}</text>']
        parts += [f'<text x="28" y="615" fill="{s["silver"]}" font-family="sans-serif" font-size="14" letter-spacing="2">DIFF · FOREGROUND ONLY</text>']
        for i,(c,line) in enumerate([('slate','@@ Theme.swift'),('coral','- let theme = "Before"'),('mint','+ let theme = "Vyntar"'),('ice','  render(theme)')]):
            parts += [f'<text x="28" y="{655+i*30}" fill="{s[c]}" font-family="monospace" font-size="18">{escape(line)}</text>']
        parts += [f'<text x="28" y="825" fill="{s["silver"]}" font-family="sans-serif" font-size="14" letter-spacing="2">ONE PALETTE · FOUR WORKSPACES</text>']
        for i,c in enumerate(t['ansi']):
            parts += [f'<rect x="{28+(i%8)*75}" y="{850+(i//8)*34}" width="65" height="24" rx="4" fill="{c}"/>']
        parts += ['</g>']
    return ('\n'.join(parts+['</svg>'])+'\n').encode()

def shell_preview(themes):
    lines = ['# Generated by Vyntar. Fixed printf formats; foreground colours only.', 'vyntar_print_palettes() {']
    for t in themes.values():
        lines.append("    printf '%s\\n' '" + t['name'] + " · sRGB / ANSI slots'")
        for i, colour in enumerate(t['ansi']):
            r,g,b = (round(c*255) for c in rgb(colour))
            label = '%02d %s' % (i, colour)
            lines.append('    if [ "$1" = 1 ]; then')
            lines.append("        printf '\\033[38;2;%d;%d;%dm %%s \\033[0m' '%s'" % (r,g,b,label))
            lines.append("    else printf ' %%s ' '%s'; fi" % label)
            if i % 4 == 3:
                lines.append("    printf '\\n'")
    lines += ['}', '']
    return '\n'.join(lines).encode()

def outputs(themes):
    out = {'themes/zed/vyntar.json':json_bytes({'$schema':'https://zed.dev/schema/themes/v0.2.0.json','name':'Vyntar','author':'Christopher Nicholson','themes':[zed(t) for t in themes.values()]}), 'assets/previews/vyntar.svg':preview(themes)}
    for slug,t in themes.items():
        out['themes/terminal/Vyntar-'+slug.title()+'.terminal'] = terminal(t)
        out['themes/xcode/workspace/'+t['name']+'.xcworkspacecolortheme'] = xcode(t)
        out['themes/codex/vyntar-'+slug+'.tmTheme'] = tmtheme(t)
        out['themes/codex/vyntar-'+slug+'-ansi.tmTheme'] = tmtheme(t,True)
    out['scripts/lib/palette-preview.sh'] = shell_preview(themes)
    rows = contrast_report(themes)
    failed = [r for r in rows if r[3] < r[4]]
    if failed:
        raise ValueError('Contrast failures: '+repr(failed))
    out['docs/contrast.tsv'] = ('variant\tforeground\tbackground\tratio\trequired\n' + ''.join('%s\t%s\t%s\t%.4f\t%.1f\n'%r for r in rows)).encode()
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); ap.add_argument('--output',type=Path,default=ROOT); args=ap.parse_args()
    out=outputs(load()); drift=[]
    # All payloads resolved and contrast checked before any destination changes.
    for name,data in out.items():
        path=args.output/name
        if args.check:
            if not path.is_file() or path.read_bytes()!=data: drift.append(name)
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
                f.write(data); temporary=f.name
            os.chmod(temporary,0o644); os.replace(temporary,path)
    if drift: raise SystemExit('Regeneration needed: '+', '.join(drift))
    print(('Verified' if args.check else 'Generated')+' %d deterministic assets; all contrast gates pass.'%len(out))
if __name__=='__main__': main()

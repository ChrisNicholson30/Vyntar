import copy
import hashlib
import importlib.util
import json
import math
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'generators'))
from theme_core import load, contrast_report, rgb, oklch
spec = importlib.util.spec_from_file_location('generate',ROOT/'generators/generate-themes.py')
gen=importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)

# The vendored schema uses precisely these draft-07 constructs. Reject unknown
# syntax rather than silently ignoring an added constraint after schema updates.
def validate(value, schema, root, path='$'):
    allowed={'$schema','$ref','title','description','default','definitions','type','properties','required','additionalProperties','items','enum','anyOf'}
    assert set(schema)<=allowed, (path,'Unsupported schema keywords',set(schema)-allowed)
    if '$ref' in schema:
        node=root
        for part in schema['$ref'].split('/')[1:]: node=node[part]
        return validate(value,node,root,path)
    if 'anyOf' in schema:
        errors=[]
        for option in schema['anyOf']:
            try: validate(value,option,root,path); return
            except AssertionError as e: errors.append(str(e))
        raise AssertionError((path,'No anyOf branch matches',errors))
    if 'enum' in schema: assert value in schema['enum'],(path,value,'enum')
    if 'type' in schema:
        types=schema['type']; types=types if isinstance(types,list) else [types]
        actual='null' if value is None else 'boolean' if isinstance(value,bool) else 'object' if isinstance(value,dict) else 'array' if isinstance(value,list) else 'string' if isinstance(value,str) else 'integer' if isinstance(value,int) else 'number'
        assert actual in types or (actual=='integer' and 'number' in types),(path,actual,types)
    if isinstance(value,dict):
        assert set(schema.get('required',[]))<=set(value),(path,'missing fields')
        props=schema.get('properties',{})
        for k,v in value.items():
            if k in props: validate(v,props[k],root,path+'.'+k)
            elif 'additionalProperties' in schema:
                extra=schema['additionalProperties']
                assert extra is not False,(path,'unexpected',k)
                if isinstance(extra,dict): validate(v,extra,root,path+'.'+k)
    if isinstance(value,list) and 'items' in schema:
        for i,v in enumerate(value): validate(v,schema['items'],root,path+'[%d]'%i)

class Themes(unittest.TestCase):
    def test_reproducible(self):
        subprocess.run([sys.executable,str(ROOT/'generators/generate-themes.py'),'--check'],check=True)
        with tempfile.TemporaryDirectory() as d:
            subprocess.run([sys.executable,str(ROOT/'generators/generate-themes.py'),'--output',d],check=True)
            for name,data in gen.outputs(load()).items(): self.assertEqual((Path(d)/name).read_bytes(),data)

    def test_zed_pinned_schema_and_known_keys(self):
        schema=json.loads((ROOT/'generators/schemas/zed-v0.2.0.json').read_text())
        family=json.loads((ROOT/'themes/zed/vyntar.json').read_text())
        overlay=json.loads((ROOT/'generators/schemas/zed-diff-overlay.json').read_text())
        schema['definitions']['ThemeStyleContent']['properties'].update(overlay['properties'])
        validate(family,schema,schema)
        for theme in family['themes']:
            self.assertFalse(set(theme['style'])-set(schema['definitions']['ThemeStyleContent']['properties']))
            for action in ['added','deleted']:
                self.assertEqual(theme['style']['version_control.word_'+action],'#00000000')
                for suffix in ['background','hollow_background','hollow_border']:
                    self.assertEqual(theme['style']['editor.diff_hunk.'+action+'.'+suffix],'#00000000')
            for sign in ['plus','minus','delta']:
                self.assertEqual(theme['style']['syntax']['diff.'+sign]['background_color'],'#00000000')
            for name in ['created','deleted','modified']:
                self.assertEqual(theme['style'][name+'.background'],'#00000000')

    def test_terminal_srgb_and_ansi_parity(self):
        for slug,t in load().items():
            profile=plistlib.loads((ROOT/('themes/terminal/Vyntar-'+slug.title()+'.terminal')).read_bytes())
            self.assertNotIn('CommandString',profile)
            self.assertNotIn('Font',profile)
            self.assertFalse(profile['UseBrightBold'])
            self.assertFalse(profile['CursorBlink'])
            colours={}
            for key,value in profile.items():
                if isinstance(value,bytes):
                    archive=plistlib.loads(value)
                    obj=archive['$objects'][1]
                    channels=list(map(float,obj['NSComponents'].split()))
                    self.assertEqual(channels[3],1)
                    self.assertEqual(archive['$objects'][2]['NSID'],7)
                    colours[key]=tuple(round(c*255) for c in channels[:3])
            self.assertEqual(len(colours),21)
            for name,c in zip(gen.ANSI_NAMES,t['ansi']):
                key='ANSI'+''.join(p.title() for p in name.split('_'))+'Color'
                self.assertEqual(colours[key],tuple(round(v*255) for v in rgb(c)))

    def test_codex_actual_ansi_and_no_diff_fills(self):
        for p in (ROOT/'themes/codex').glob('*.tmTheme'):
            d=plistlib.loads(p.read_bytes()); globals=d['settings'][0]['settings']
            self.assertEqual(globals['background'],gen.DEFAULT)
            found=set()
            for rule in d['settings'][1:]:
                settings=rule['settings']
                if any(s in rule['scope'] for s in ['markup.inserted','markup.deleted','markup.changed']):
                    self.assertEqual(settings['background'],gen.DEFAULT)
                    self.assertEqual(settings['fontStyle'],'')
                    found.add(rule['name'])
                if '-ansi.' in p.name:
                    colour=settings['foreground']
                    self.assertEqual(colour[-2:],'00')
                    self.assertEqual(colour[3:7],'0000')
                    self.assertLess(int(colour[1:3],16),16)
            self.assertEqual(len(found),3)

    def test_contrast_every_placement(self):
        rows=contrast_report(load())
        self.assertGreater(len(rows),300)
        for slug,fg,bg,actual,required in rows:
            self.assertGreaterEqual(actual,required,(slug,fg,bg,actual))

    def test_xcode_roundtrip_srgb_oklab(self):
        # Independent inverse transform catches channel/gamut/hue-unit errors.
        for slug,t in load().items():
            d=json.loads((ROOT/('themes/xcode/workspace/'+t['name']+'.xcworkspacecolortheme')).read_text())
            self.assertEqual(d['fileVersion'],1)
            self.assertNotIn('fonts',d['recipe'])
            colours={'background':d['recipe']['background']['customColor']}
            colours.update({k:v.get('color',v.get('colorWithOpacity')) for k,v in d['recipe']['palette']['colorOverrides'].items()})
            for name,c in colours.items():
                self.assertEqual(c['gamut'],'sRGB')
                L=c['lightness']['exact']; C=c['chroma']['exact']; h=c['hue']['radians']
                a=C*math.cos(h); b=C*math.sin(h)
                l=(L+.3963377774*a+.2158037573*b)**3
                m=(L-.1055613458*a-.0638541728*b)**3
                s=(L-.0894841775*a-1.291485548*b)**3
                channels=[4.0767416621*l-3.3077115913*m+.2309699292*s,-1.2684380046*l+2.6097574011*m-.3413193965*s,-.0041960863*l-.7034186147*m+1.707614701*s]
                decoded=[12.92*v if v<=.0031308 else 1.055*v**(1/2.4)-.055 for v in channels]
                swatch='midnight' if name=='background' else 'line' if name=='currentLineHighlight' else 'selection' if name=='selectedTextBackgroundColor' else gen.XCODE[name]
                for actual,expected in zip(decoded,rgb(t['swatches'][swatch])):
                    self.assertAlmostEqual(actual,expected,places=5)

    def test_invalid_contracts_fail(self):
        for name,mutate in [
            ('palette.json',lambda d:d['base'].update(cyan='#123')),
            ('palette.json',lambda d:d['base'].update(unknown='#FFFFFF')),
            ('semantics.json',lambda d:d.update({'diff.add.bg':'midnight'})),
            ('semantics.json',lambda d:d.update({'syntax.string':'missing'})),
            ('ansi.json',lambda d:d.update({'16':'cyan'})),
        ]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); (root/'palette').mkdir()
                for p in (ROOT/'palette').glob('*.json'):
                    d=json.loads(p.read_text())
                    if p.name==name: mutate(d)
                    (root/'palette'/p.name).write_text(json.dumps(d))
                with self.assertRaises((AssertionError,ValueError,KeyError)): load(root)

if __name__=='__main__': unittest.main()

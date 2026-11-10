import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def tree(root):
    return {str(p.relative_to(root)):(p.stat().st_mode, hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'directory') for p in root.rglob('*')}

class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='vyntar-test-',dir='/private/tmp' if Path('/private/tmp').exists() else None)
        self.root=Path(self.tmp.name).resolve(); self.home=self.root/'Home With Spaces'; self.home.mkdir()
        self.state=self.home/'Library/Application Support/Vyntar'
        self.env=dict(os.environ,HOME=str(self.home),CODEX_HOME=str(self.home/'Custom Codex'),VYNTAR_DATA_HOME=str(self.state),NO_COLOR='1')
        self.zed=self.home/'.config/zed/themes/vyntar.json'
    def tearDown(self): self.tmp.cleanup()
    def run_cmd(self,*args,ok=0,env=None):
        result=subprocess.run([str(ROOT/'bin/vyntar'),*args],env=env or self.env,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        self.assertEqual(result.returncode,ok,result.stdout); return result.stdout
    def install(self): return self.run_cmd('install','--target','zed,codex','--plain')
    def test_dry_run_zero_writes(self):
        before=tree(self.root)
        self.run_cmd('install','--target','zed,codex','--dry-run')
        self.assertEqual(before,tree(self.root))
    def test_install_noop_custom_home_and_uninstall(self):
        self.install(); self.assertTrue(self.zed.is_file())
        self.assertTrue((self.home/'Custom Codex/themes/vyntar-pulse-ansi.tmTheme').is_file())
        previous=tree(self.root); self.assertIn('Already installed',self.install())
        # No-op writes neither ownership nor transactions; lock is transient.
        self.assertEqual(previous,tree(self.root))
        self.run_cmd('doctor')
        self.run_cmd('uninstall'); self.assertFalse(self.zed.exists())
        self.run_cmd('uninstall')
    def test_unmanaged_identical_is_collision(self):
        self.zed.parent.mkdir(parents=True); shutil.copy(ROOT/'themes/zed/vyntar.json',self.zed)
        before=tree(self.root)
        self.run_cmd('install','--target','zed',ok=1)
        self.assertEqual(before,tree(self.root))
    def test_edit_survives_update_and_uninstall(self):
        self.install(); self.zed.write_text('my custom theme\n')
        self.run_cmd('install','--target','zed',ok=1)
        self.run_cmd('status',ok=1)
        self.run_cmd('uninstall',ok=1)
        self.assertEqual(self.zed.read_text(),'my custom theme\n')
        self.assertTrue((self.state/'bin/vyntar').is_file())
    def test_symlink_ancestor_rejected(self):
        outside=self.root/'outside'; outside.mkdir()
        (self.home/'.config').symlink_to(outside,target_is_directory=True)
        self.run_cmd('install','--target','zed',ok=1)
        self.assertEqual(list(outside.iterdir()),[])
    def test_lock_blocks_writer(self):
        self.state.mkdir(parents=True); (self.state/'lock').mkdir()
        self.run_cmd('install','--target','zed',ok=1)
        self.assertFalse(self.zed.exists())
    def test_failure_rolls_back(self):
        env=dict(self.env,VYNTAR_TEST_FAIL_AFTER='2')
        self.run_cmd('install','--target','zed,codex',ok=1,env=env)
        self.assertFalse(self.zed.exists())
        self.assertFalse((self.state/'owned.tsv').exists())
        self.assertFalse((self.state/'pending').exists())
        self.assertFalse((self.state/'lock').exists())
        self.install()
    def test_restore_install_and_drift_guard(self):
        self.install(); tx=next((self.state/'transactions').iterdir()).name
        before=tree(self.root); self.run_cmd('restore',tx,'--dry-run'); self.assertEqual(before,tree(self.root))
        self.run_cmd('restore',tx); self.assertFalse(self.zed.exists())
        self.install(); self.zed.write_text('edited')
        tx=sorted((self.state/'transactions').iterdir(),key=lambda p:p.stat().st_mtime)[-1].name
        self.run_cmd('restore',tx,ok=1); self.assertEqual(self.zed.read_text(),'edited')
    def test_invalid_args_and_absent_app(self):
        self.run_cmd('install','--target','',ok=2)
        self.run_cmd('install','--target','zed,other',ok=2)
        self.run_cmd('install','--bad',ok=2)
        env=dict(self.env,VYNTAR_APPLICATIONS=str(self.root/'no-apps'))
        self.run_cmd('install','--target','zed',ok=1,env=env)
    def test_preference_dry_and_plain(self):
        before=tree(self.root); self.run_cmd('theme','pulse','--dry-run'); self.assertEqual(before,tree(self.root))
        self.run_cmd('theme','endurance'); self.assertEqual((self.state/'preference').read_text(),'endurance\n')
        self.assertNotIn('\x1b',self.run_cmd('preview','--plain'))
    def test_upgrade_restore_previous_release(self):
        self.install(); original=self.zed.read_bytes()
        bundle=self.root/'new release'; shutil.copytree(ROOT,bundle,ignore=shutil.ignore_patterns('.git','dist','__pycache__'))
        (bundle/'VERSION').write_text('0.1.0-preview.2\n')
        (bundle/'themes/zed/vyntar.json').write_bytes(original+b'\n')
        subprocess.run(['python3',str(bundle/'generators/package.py')],check=True,stdout=subprocess.PIPE)
        self.run_cmd('update','--bundle',str(bundle),'--target','zed')
        self.assertEqual(self.zed.read_bytes(),original+b'\n')
        self.assertTrue((self.home/'Custom Codex/themes/vyntar-pulse.tmTheme').is_file())
        tx=max((self.state/'transactions').iterdir(),key=lambda p:p.stat().st_mtime).name
        self.run_cmd('restore',tx)
        self.assertEqual(self.zed.read_bytes(),original)
        self.assertEqual((self.state/'VERSION').read_text(),(ROOT/'VERSION').read_text())

    def test_interrupted_rename_is_reconciled_before_preflight(self):
        self.install()
        journal=next((self.state/'transactions').iterdir())
        shutil.copytree(journal,self.state/'pending')
        # Simulate death after destination renames, before ownership commit.
        (self.state/'owned.tsv').unlink()
        out=self.install()
        self.assertIn('RECOVER',out)
        self.assertTrue(self.zed.exists())
        self.assertFalse((self.state/'pending').exists())
        self.run_cmd('status')

    def test_interrupted_transaction_preserves_concurrent_edit(self):
        self.install(); journal=next((self.state/'transactions').iterdir())
        shutil.copytree(journal,self.state/'pending')
        self.zed.write_text('concurrent edit')
        self.run_cmd('install','--target','zed',ok=1)
        self.assertEqual(self.zed.read_text(),'concurrent edit')
        self.assertTrue((self.state/'pending').exists())
        self.assertFalse((self.state/'lock').exists())

    def test_incomplete_preparation_does_not_touch_destinations(self):
        self.state.mkdir(parents=True); (self.state/'pending').mkdir()
        (self.state/'pending/preparing').write_text('')
        self.install(); self.assertTrue(self.zed.is_file())
        self.assertFalse((self.state/'pending').exists())

    def test_failed_upgrade_restores_previous_bytes_and_permissions(self):
        self.install(); before=self.zed.read_bytes(); mode=self.zed.stat().st_mode
        bundle=self.root/'upgrade'; shutil.copytree(ROOT,bundle,ignore=shutil.ignore_patterns('.git','dist','__pycache__'))
        (bundle/'themes/zed/vyntar.json').write_bytes(before+b'\n')
        subprocess.run(['python3',str(bundle/'generators/package.py')],check=True,stdout=subprocess.PIPE)
        env=dict(self.env,VYNTAR_TEST_FAIL_AFTER='1')
        self.run_cmd('update','--bundle',str(bundle),'--target','zed',ok=1,env=env)
        self.assertEqual(self.zed.read_bytes(),before)
        self.assertEqual(self.zed.stat().st_mode,mode)
        self.run_cmd('status')

    def test_corrupt_bundle_rejected(self):
        bundle=self.root/'bundle'; shutil.copytree(ROOT,bundle,ignore=shutil.ignore_patterns('.git','dist','__pycache__'))
        (bundle/'themes/zed/vyntar.json').write_text('{}')
        self.run_cmd('update','--bundle',str(bundle),'--target','zed',ok=1)
        self.assertFalse(self.zed.exists())

if __name__=='__main__': unittest.main()

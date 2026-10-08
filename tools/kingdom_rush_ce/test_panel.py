"""No GUI, game or CE process is launched by these tests."""
import hashlib,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import build
sys.path.insert(0,str(build.STAGE))
import panel
base=panel.base

class Var:
    def __init__(self,value=''):self.value=value
    def get(self):return self.value
    def set(self,v):self.value=v

class PanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.control=self.root/'save/kr_trainer_ce';self.control.mkdir(parents=True)
        self.ce=self.root/'ce';self.ce.mkdir()
        for name in panel.COMPONENTS:(self.ce/name).write_bytes(b'test only')
        (self.ce/'manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.ce.iterdir()}))
        self.patches=[patch.object(panel,'BUNDLE',self.root),patch.object(base,'CONTROL',self.control),
            patch.object(base,'ROOT',self.root),patch.object(base,'SAVE',self.control.parent),
            patch.object(base,'game_running',return_value=True),patch.object(panel.messagebox,'showerror'),
            patch.object(panel.subprocess,'Popen',return_value=Mock(poll=Mock(return_value=None)))]
        self.mocks=[p.start() for p in self.patches];self.spawn=self.mocks[-1]
        self.p=object.__new__(panel.CEPanel)
        self.p.backend=None;self.p.backend_started=0;self.p.hotkey_down=set()
        self.p.cfg=base.DEFAULTS.copy();self.p.seq=10;self.p.pending=None
        self.p.vars={k:Var(v) for k,v in dict(gold='1000',lives='20',stars='99',gems='999',speed='1',hero_damage='1',soldier_damage='1',tower_damage='1').items()}
        self.p.lock_gold=Var(False);self.p.lock_lives=Var(False);self.p.cooldown=Var(False)
        self.p.note=Var();self.p.status_var=Var();self.p.after=Mock();self.p.destroy=Mock()
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def test_absent_game_never_launches(self):
        base.game_running.return_value=False;self.p.launch();self.assertFalse(self.spawn.called)
    def test_only_ce_can_be_launched(self):
        self.p.launch();self.assertTrue(self.spawn.called)
        args=self.spawn.call_args.args[0]
        self.assertEqual(args,[str(self.ce/'cheatengine-x86_64.exe'),str(self.ce/'attach.CETRAINER'),'NOAUTORUN'])
        self.assertIn('action=reset',(self.control/'control.txt').read_text())
        self.assertTrue(list((self.root/'backups').glob('*/manifest.json')))
    def test_corrupt_component_blocks_connection(self):
        (self.ce/'attach.CETRAINER').write_text('corrupt');self.p.launch();self.assertFalse(self.spawn.called)
    def test_malformed_manifests_never_launch(self):
        for bad in ([],{},None,{'../outside':'0'*64},{n:None for n in panel.COMPONENTS}):
            with self.subTest(manifest=bad):
                (self.ce/'manifest.json').write_text(json.dumps(bad))
                self.p.launch();self.assertFalse(self.spawn.called)
    def test_stale_ready_file_cannot_confirm_new_connection(self):
        (self.control/'bridge_result.txt').write_text('READY')
        self.p.launch();self.assertFalse((self.control/'bridge_result.txt').exists())
        self.assertIn('正在通过 CE',self.p.note.get())
    def test_backup_failure_blocks_connection(self):
        with patch.object(base,'backup',side_effect=OSError('disk full')):self.p.launch()
        self.assertFalse(self.spawn.called)
    def test_reset_failure_blocks_connection(self):
        with patch.object(self.p,'send',side_effect=OSError('disk full')):self.p.launch()
        self.assertFalse(self.spawn.called)
    def test_duplicate_connection_is_blocked(self):
        self.p.launch();self.p.launch();self.assertEqual(self.spawn.call_count,1)
    def test_close_waits_for_interface_restore(self):
        self.p.launch();self.p.close();self.assertFalse(self.p.destroy.called)
    def test_close_resets_temporary_values(self):
        self.p.cfg['hero_damage']=100;self.p.close();self.p.destroy.assert_called_once()
        self.assertEqual(self.p.cfg,base.DEFAULTS)
    def test_backend_error_is_visible(self):
        self.p.backend=Mock(poll=Mock(return_value=0))
        (self.control/'bridge_result.txt').write_text('ERROR version mismatch')
        self.p.refresh();self.assertIn('version mismatch',self.p.note.get());self.assertIsNone(self.p.backend)
    def test_backend_exit_without_ack_not_success(self):
        self.p.backend=Mock(poll=Mock(return_value=0));self.p.refresh()
        self.assertIn('未返回成功',self.p.note.get())
    def test_backup_restore_uses_ce_channel(self):
        (self.control.parent/'slot_1.lua').write_text('old')
        folder=base.backup();(self.control.parent/'slot_1.lua').write_text('new')
        base.game_running.return_value=False;base.restore(folder)
        self.assertEqual((self.control.parent/'slot_1.lua').read_text(),'old')
        self.assertTrue((self.control/'bonus_1.txt').exists())
        self.assertFalse((self.control.parent/'kr_trainer').exists())
    def test_hotkey_is_edge_triggered(self):
        with patch.object(self.p,'connected',return_value=True),patch.object(self.p,'add_gold') as add,patch.object(panel.ctypes.windll.user32,'GetAsyncKeyState',side_effect=lambda k:0x8000 if k in (0x11,0x70) else 0):
            self.p.poll_hotkeys();self.p.poll_hotkeys();add.assert_called_once()

    def ready(self):
        (self.control/'status.txt').write_text(f'time={int(time.time())}\nslot=1\nin_level=0\nce_version={panel.VERSION}\n',encoding='utf8')

    def test_achievement_cancel_never_backs_up_or_sends(self):
        self.ready()
        with patch.object(panel.simpledialog,'askstring',return_value=None),patch.object(base,'backup') as backup:
            self.p.unlock_achievements();backup.assert_not_called()
        self.assertFalse((self.control/'control.txt').exists())

    def test_achievement_confirmation_must_match_exactly(self):
        self.ready()
        for answer in ('', '确认',panel.CONFIRM_PHRASE+' ',panel.CONFIRM_PHRASE+'\n'):
            with patch.object(panel.simpledialog,'askstring',return_value=answer),patch.object(base,'backup') as backup:
                self.p.unlock_achievements();backup.assert_not_called()
            self.assertFalse((self.control/'control.txt').exists())

    def test_achievement_exact_confirmation_backup_then_command(self):
        self.ready()
        with patch.object(panel.simpledialog,'askstring',return_value=panel.CONFIRM_PHRASE) as prompt:
            self.p.unlock_achievements()
        text=(self.control/'control.txt').read_text(encoding='utf8')
        self.assertIn('action=unlock_achievements',text)
        self.assertIn('value=1|'+panel.CONFIRM_PHRASE,text)
        self.assertIn('Steam 成就都会全部解锁',prompt.call_args.args[1])
        self.assertTrue(list((self.root/'backups').glob('*/manifest.json')))

    def test_achievement_backup_failure_never_sends(self):
        self.ready()
        with patch.object(panel.simpledialog,'askstring',return_value=panel.CONFIRM_PHRASE),patch.object(base,'backup',side_effect=OSError('disk full')):
            self.p.unlock_achievements()
        self.assertFalse((self.control/'control.txt').exists())

    def test_achievement_changed_slot_requires_new_confirmation(self):
        with patch.object(self.p,'progression_slot',side_effect=['1','2']),patch.object(panel.simpledialog,'askstring',return_value=panel.CONFIRM_PHRASE),patch.object(base,'backup') as backup:
            self.p.unlock_achievements();backup.assert_not_called()
        self.assertFalse((self.control/'control.txt').exists())

    def test_achievement_disconnected_never_prompts(self):
        with patch.object(panel.simpledialog,'askstring') as prompt:
            self.p.unlock_achievements();prompt.assert_not_called()

    def test_achievement_old_runtime_never_prompts(self):
        self.ready();p=self.control/'status.txt';p.write_text(p.read_text().replace(panel.VERSION,'2.0 RC2'))
        with patch.object(panel.simpledialog,'askstring') as prompt:
            self.p.unlock_achievements();prompt.assert_not_called()

    def test_achievement_unconfirmed_command_blocks_repeat(self):
        self.ready();self.p.pending=(1,time.time(),'unlock_achievements')
        with patch.object(panel.simpledialog,'askstring') as prompt:
            self.p.unlock_achievements();prompt.assert_not_called()

    def test_hero_command_backs_up_slot(self):
        self.ready();(self.control.parent/'slot_1.lua').write_text('heroes={}')
        self.p.unlock_heroes()
        self.assertIn('action=unlock_heroes',(self.control/'control.txt').read_text())
        self.assertEqual(next((self.root/'backups').glob('*/slot_1.lua')).read_text(),'heroes={}')

if __name__=='__main__':unittest.main(verbosity=2)

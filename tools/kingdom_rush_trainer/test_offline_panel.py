import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import trainer

class Var:
    def __init__(self,value=''):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value

class OfflinePanelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.patches=[patch.object(trainer,'ROOT',self.root/'app'),patch.object(trainer,'SAVE',self.root/'save'),
            patch.object(trainer,'CONTROL',self.root/'save/kr_trainer'),patch.object(trainer,'game_running',return_value=False),
            patch.object(trainer.subprocess,'Popen',side_effect=AssertionError('OFFLINE TEST: process launch forbidden')),
            patch.object(trainer.messagebox,'showerror'),patch.object(trainer.messagebox,'showinfo')]
        for p in self.patches:p.start()
        trainer.CONTROL.mkdir(parents=True)
        (trainer.SAVE/'slot_1.lua').write_text('original')
        self.p=object.__new__(trainer.Panel)
        self.p.cfg=trainer.DEFAULTS.copy();self.p.seq=10;self.p.pending=None
        self.p.vars={k:Var(v) for k,v in dict(gold='1000',lives='20',stars='99',gems='999',speed='1',
            hero_damage='1',soldier_damage='1',tower_damage='1').items()}
        self.p.lock_gold=Var(False);self.p.lock_lives=Var(False);self.p.cooldown=Var(False)
        self.p.note=Var();self.p.status_var=Var();self.p.after=Mock()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()

    def status(self,**fields):
        data=dict(time=int(time.time()),seq=0,gold=100,**fields)
        (trainer.CONTROL/'status.txt').write_text(''.join(f'{k}={v}\n' for k,v in data.items()))

    def test_malformed_timestamp_cannot_stop_refresh(self):
        (trainer.CONTROL/'status.txt').write_text('time=garbage\nseq=garbage')
        self.p.refresh();self.p.after.assert_called_once();self.assertFalse(self.p.connected())

    def test_non_utf8_status_is_treated_as_disconnected(self):
        (trainer.CONTROL/'status.txt').write_bytes(b'\xff\xfe')
        self.assertFalse(self.p.connected());self.p.refresh();self.p.after.assert_called_once()

    def test_future_timestamp_is_not_connected(self):
        (trainer.CONTROL/'status.txt').write_text(f'time={int(time.time())+86400}\nseq=0')
        self.assertFalse(self.p.connected())

    def test_invalid_ack_does_not_crash_refresh(self):
        (trainer.CONTROL/'status.txt').write_text(f'time={int(time.time())}\nseq=oops')
        self.p.pending=(10,time.time(),'gems')
        self.p.refresh();self.p.after.assert_called_once()

    def test_pending_value_command_not_overwritten_by_apply(self):
        self.p.send('gems',999)
        before=(trainer.CONTROL/'control.txt').read_bytes()
        self.p.vars['speed'].set('3');self.p.apply()
        self.assertEqual((trainer.CONTROL/'control.txt').read_bytes(),before)
        self.assertEqual(self.p.pending[2],'gems')

    def test_failed_reset_prevents_game_launch(self):
        exe=trainer.ROOT/'game/Kingdom Rush.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'fixture')
        with patch.object(self.p,'send',side_effect=OSError('disk full')),patch.object(trainer.subprocess,'Popen') as launch:
            self.p.launch();self.assertFalse(launch.called,'launch must not occur when reset fails')

    def test_invalid_numeric_settings_leave_control_unchanged(self):
        self.p.send();before=(trainer.CONTROL/'control.txt').read_bytes()
        for invalid in ('nan','inf','-inf','0','6','text'):
            with self.subTest(value=invalid):
                self.p.vars['speed'].set(invalid);self.p.apply()
                self.assertEqual((trainer.CONTROL/'control.txt').read_bytes(),before)

    def test_missing_backup_member_cannot_partly_restore(self):
        b=trainer.backup();(trainer.SAVE/'slot_1.lua').write_text('current')
        (b/'kr_trainer/bonus_3.txt').unlink()
        with self.assertRaises(FileNotFoundError):trainer.restore(b)
        self.assertEqual((trainer.SAVE/'slot_1.lua').read_text(),'current')

    def test_restore_all_slots_and_zero_bonuses(self):
        for i in (2,3):(trainer.SAVE/f'slot_{i}.lua').write_text(f'original{i}')
        b=trainer.backup()
        for i in (1,2,3):
            (trainer.SAVE/f'slot_{i}.lua').write_text('changed')
            (trainer.CONTROL/f'bonus_{i}.txt').write_text('99')
        trainer.restore(b)
        for i in (1,2,3):
            self.assertEqual((trainer.CONTROL/f'bonus_{i}.txt').read_text(),'0')
            self.assertTrue((trainer.SAVE/f'slot_{i}.lua').read_text().startswith('original'))

    def test_invalid_manifests_rejected_without_writes(self):
        b=trainer.backup()
        for contents in ([42],{'slot_1.lua':1},['../outside.lua'],['C:/outside.lua'],['nested/data.lua']):
            with self.subTest(contents=contents):
                (b/'manifest.json').write_text(json.dumps(contents))
                with self.assertRaises(ValueError):trainer.restore(b)
                self.assertEqual((trainer.SAVE/'slot_1.lua').read_text(),'original')

    def test_acknowledged_command_allows_next_setting(self):
        self.p.send('gems',999)
        (trainer.CONTROL/'status.txt').write_text(f'time={int(time.time())}\nseq={self.p.seq}\nmessage=ok:gems')
        self.p.refresh();self.assertIsNone(self.p.pending)
        self.p.vars['speed'].set('2');self.p.apply()
        self.assertIn('speed=2.0',(trainer.CONTROL/'control.txt').read_text())

    def test_timeout_does_not_silently_discard_unconfirmed_command(self):
        self.p.send('gems',999);self.p.pending=(self.p.seq,time.time()-10,'gems')
        self.p.refresh();self.assertIsNotNone(self.p.pending)
        self.p.reset();self.assertEqual(self.p.pending[2],'reset')

    def test_failed_ack_is_reported_as_failure(self):
        self.p.send('gems',999)
        (trainer.CONTROL/'status.txt').write_text(f'time={int(time.time())}\nseq={self.p.seq}\nmessage=error:save failed')
        self.p.refresh();self.assertIn('操作失败',self.p.note.get());self.assertIsNone(self.p.pending)

    def test_close_writes_neutral_settings_without_launch(self):
        self.p.cfg['hero_damage']=100;self.p.destroy=Mock()
        self.p.close();self.p.destroy.assert_called_once()
        self.assertEqual(self.p.cfg,trainer.DEFAULTS)
        self.assertIn('action=reset',(trainer.CONTROL/'control.txt').read_text())

    def test_backup_round_trip_and_restore_preserves_new_slots(self):
        (trainer.SAVE/'settings.lua').write_bytes(b'\x00fixture\xff')
        b=trainer.backup();(trainer.SAVE/'slot_2.lua').write_text('new slot')
        safety=trainer.restore(b)
        self.assertEqual((trainer.SAVE/'settings.lua').read_bytes(),b'\x00fixture\xff')
        self.assertEqual((trainer.SAVE/'slot_2.lua').read_text(),'new slot')
        self.assertTrue((safety/'slot_2.lua').is_file())

    def test_backup_unavailable_blocks_game_launch(self):
        exe=trainer.ROOT/'game/Kingdom Rush.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'fixture')
        with patch.object(trainer,'backup',side_effect=OSError('disk full')),patch.object(trainer.subprocess,'Popen') as launch:
            self.p.launch();self.assertFalse(launch.called)

if __name__=='__main__':unittest.main(verbosity=2)

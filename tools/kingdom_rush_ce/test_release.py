"""Audit the shipped archive and run the real CE backend without a game."""
from pathlib import Path
import ctypes,hashlib,json,os,shutil,subprocess,sys,tempfile,time,xml.etree.ElementTree as ET
import build
sys.path.insert(0,str(build.WORK/'analysis/kingdom-rush/packaging'))
from PyInstaller.archive.readers import CArchiveReader

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    original=Path(os.environ['KR_GAME_DIR'])
    save=Path(os.environ['APPDATA'])/'kingdom_rush'
    def protected():return {str(p):digest(p) for p in [*original.glob('*.dll'),original/'Kingdom Rush.exe',*save.rglob('*')] if p.is_file()}
    before=protected()
    tasks=subprocess.check_output(['tasklist','/FI','IMAGENAME eq Kingdom Rush.exe','/FO','CSV','/NH'],creationflags=subprocess.CREATE_NO_WINDOW)
    assert b'Kingdom Rush.exe' not in tasks,'This test requires the game to remain closed'
    exe=build.OUT/'KingdomRush-CE.exe';reader=CArchiveReader(str(exe))
    names=[n.replace('\\','/') for n in reader.toc]
    assert not any(Path(n).name.lower() in ('kingdom rush.exe','love.dll','lua51.dll') for n in names)
    manifest=json.loads((build.STAGE/'ce/manifest.json').read_text())
    for name,expected in manifest.items():
        key=next(n for n in reader.toc if n.replace('\\','/')=='ce/'+name)
        assert hashlib.sha256(reader.extract(key)).hexdigest()==expected,name
    script=ET.parse(build.STAGE/'ce/attach.CETRAINER').find('LuaScript').text
    assert 'KR_CE_OFFLINE_FIXTURE' not in script
    assert 'fixture.slot' not in script
    with tempfile.TemporaryDirectory(prefix='kr-ce-release-') as tmp:
        root=Path(tmp)/'离线 分享测试';root.mkdir()
        ce=root/'ce';ce.mkdir()
        for name in manifest:
            key=next(n for n in reader.toc if n.replace('\\','/')=='ce/'+name)
            (ce/name).write_bytes(reader.extract(key))
        env=os.environ.copy();env['APPDATA']=str(root)
        env['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
        # Keep the production path code, including its non-ASCII APPDATA handling.
        control=root/'kingdom_rush/kr_trainer_ce';control.mkdir(parents=True)
        table=ET.Element('CheatTable',CheatEngineTableVersion='45')
        ET.SubElement(table,'CheatEntries');ET.SubElement(table,'LuaScript').text=script
        path=root/'no-game.CETRAINER';ET.ElementTree(table).write(path,encoding='utf-8',xml_declaration=True)
        si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
        p=subprocess.run([str(ce/'cheatengine-x86_64.exe'),str(path),'NOAUTORUN'],cwd=ce,env=env,startupinfo=si,timeout=20)
        assert p.returncode==0
        result=(control/'bridge_result.txt').read_text(encoding='utf8')
        assert result.startswith('ERROR ') and 'Steam' in result,result
        assert 'result=ERROR' in (control/'connection_diagnostics.txt').read_text(encoding='utf8')
        # Launch the actual packaged panel with a disposable APPDATA directory.
        # Only close its own window; no connect button or game launch is invoked.
        portable=root/'KingdomRush-CE.exe';shutil.copy2(exe,portable)
        ui=subprocess.Popen([str(portable)],env=env,cwd=root)
        try:
            user=ctypes.windll.user32
            kernel=ctypes.windll.kernel32
            kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_bool,ctypes.c_ulong]
            kernel.OpenProcess.restype=ctypes.c_void_p
            kernel.QueryFullProcessImageNameW.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_ulong)]
            kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            user.GetWindowTextW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_int]
            user.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
            callback_type=ctypes.WINFUNCTYPE(ctypes.c_bool,ctypes.c_void_p,ctypes.c_void_p)
            found=[]
            def collect(hwnd,_):
                title=ctypes.create_unicode_buffer(256);user.GetWindowTextW(hwnd,title,256)
                if title.value=='Kingdom Rush · CE 修改器 2.2 RC2':
                    pid=ctypes.c_ulong();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
                    handle=kernel.OpenProcess(0x1000,False,pid.value)
                    if handle:
                        try:
                            path=ctypes.create_unicode_buffer(32768);size=ctypes.c_ulong(32768)
                            if kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)) and Path(path.value)==portable:
                                found.append(hwnd)
                        finally:kernel.CloseHandle(handle)
                return True
            callback=callback_type(collect)
            deadline=time.monotonic()+15
            while not found and time.monotonic()<deadline and ui.poll() is None:
                user.EnumWindows(callback,0);time.sleep(.1)
            assert len(found)==1,'packaged window failed to initialize or duplicate window'
            user.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p]
            user.PostMessageW(found[0],0x10,None,None)
            assert ui.wait(timeout=10)==0
            control=root/'kingdom_rush/kr_trainer_ce/control.txt'
            assert 'action=reset' in control.read_text(),'packaged panel did not reset its isolated channel'
        finally:
            if ui.poll() is None:ui.terminate();ui.wait(timeout=5)
    assert protected()==before,'Protected files changed'
    report=dict(archive_contains_no_game=True,bundled_ce_hashes_verified=True,fixture_override_absent=True,
        real_ce_no_game_rejection=True,packaged_panel_start_and_close=True,portable_unicode_path_minimal_path=True,game_launched=False,original_game_and_saves_unchanged=True,
        production_game_attachment_tested=False,exe_sha256=digest(exe),exe_size=exe.stat().st_size,
        protected_file_count=len(before),ce_remote_test=json.loads((build.WORK/'analysis/kingdom-rush/ce-fixture/fixture-result.json').read_text()))
    (build.OUT/'release-checks.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

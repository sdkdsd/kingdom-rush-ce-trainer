"""Read-only CE module validation against a disposable DLL host, never the game."""
from pathlib import Path
import ctypes,hashlib,json,os,shutil,struct,subprocess,sys,tempfile,time,xml.etree.ElementTree as ET
WORK=Path(__file__).resolve().parents[2]
GAME=Path(os.environ['KR_GAME_DIR'])
OUT=WORK/'analysis/kingdom-rush/module-diagnosis'
CE=WORK/'analysis/kingdom-rush/ce-dev'

def child(root,source):
    cookie=os.add_dll_directory(str(GAME))
    lua=ctypes.CDLL(str(GAME/'lua51.dll'))
    (root/'ready').write_text(str(os.getpid()))
    library=None
    end=time.monotonic()+45
    while time.monotonic()<end and not (root/'stop').exists():
        if (root/'load').exists() and library is None:
            library=ctypes.CDLL(str(source))
            (root/'loaded').write_text('ok')
        time.sleep(.02)

def literal(s):return '[=====['+str(s)+']=====]'

def main():
    OUT.mkdir(exist_ok=True)
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [GAME/'love.dll',GAME/'lua51.dll',GAME/'Kingdom Rush.exe',* (Path(os.environ['APPDATA'])/'kingdom_rush').rglob('*')] if p.is_file()}
    data=(GAME/'love.dll').read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0]
    print('DLL:',json.dumps({'path':str(GAME/'love.dll'),'size':len(data),'machine':hex(struct.unpack_from('<H',data,pe+4)[0]),'md5':hashlib.md5(data).hexdigest()},ensure_ascii=False),flush=True)
    summaries=[]
    for case in (sys.argv[2:3] if len(sys.argv)>2 and sys.argv[1]=='--case' else ('original','unicode')):
        with tempfile.TemporaryDirectory(prefix='kr-module-') as tmp:
            root=Path(tmp)
            source=GAME/'love.dll'
            if case.startswith('unicode'):
                copy=root/'中文目录 空格';copy.mkdir();source=copy/'LOVE.DLL';shutil.copy2(GAME/'love.dll',source)
            p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--child',str(root),str(source)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            ce=None
            try:
                end=time.monotonic()+8
                while not (root/'ready').exists() and time.monotonic()<end and p.poll() is None:time.sleep(.05)
                assert (root/'ready').exists(),'DLL host failed to initialize'
                script='local B=(function()\n'+(WORK/'tools/kingdom_rush_ce/bridge.lua').read_text(encoding='utf8')+'\nend)()\n'
                script+='local pid='+str(p.pid)+'\nlocal directory='+literal(root.as_posix()+'/')+'\nlocal normalize='+str(case=='unicode-normalized').lower()+'\n'
                script+='''
local realList,realModules,realMD5,realExists=getProcesslist,enumModules,md5file,fileExists
local function pathForMD5(path)
 if normalize and utf8.len(path)==nil then return (ansiToUtf8 or ansiToUTF8)(path) end
 return path
end
-- Test-only identity shim: a Python DLL host is not an authentic game EXE.
-- Module enumeration and both game DLL hashes still use real CE APIs.
getProcesslist=function()local t=realList();t[pid]='Kingdom Rush.exe';return t end
enumModules=function(id)
 local t=realModules(id)
 for _,m in ipairs(t)do m.PathToFile=pathForMD5(m.PathToFile) end
 for _,m in ipairs(t)do if m.Name:lower()=='python.exe' then m.Name='Kingdom Rush.exe';m.PathToFile='fixture-python-exe' end end
 return t
end
md5file=function(path)if path=='fixture-python-exe' then return '5472c2cceaf3e285143f730e04bf88e5' end;return realMD5(path)end
fileExists=function(path)if path=='fixture-python-exe' then return true end;return realExists(path)end
local function file(name,content)local h=assert(io.open(directory..name,'w'));h:write(content or '');h:close()end
local lines={}
local function log(s)lines[#lines+1]=s;file('trace.txt',table.concat(lines,'\\n')) end
local function exists(name)local h=io.open(directory..name,'r');if h then h:close();return true end end
local function check(label,expected)
 log(label..' begin enumeration')
 local mods=realModules(pid);local found=false
 for _,m in ipairs(mods)do if m.Name:lower()=='love.dll' then found=true;log(label..' love='..m.Name..' raw_path_utf8='..tostring(utf8.len(m.PathToFile)~=nil));log(label..' md5='..tostring(realMD5(B.text_path(m.PathToFile)))..' x64='..tostring(m.Is64Bit)) end end
 local ok,a,b=pcall(B.validate,pid)
 log(label..' modules='..#mods..' found='..tostring(found)..' validate='..tostring(ok)..(ok and '' or (' error='..tostring(a))))
 assert(ok==expected,label..' unexpected validation verdict')
 if not expected then assert(tostring(a):find('未识别到模块 love.dll',1,true),'wrong failure') end
end
local phase=0;local ticks=0;local timer=createTimer(nil,false);timer.Interval=50
local function finish(ok,err)
 timer.Enabled=false;log(ok and 'PASS' or ('FAIL '..tostring(err)));file('result.txt',table.concat(lines,'\\n'));createTimer(100,function()closeCE()end)
end
timer.OnTimer=function()
 timer.Enabled=false
 local ok,err=pcall(function()
  ticks=ticks+1;assert(ticks<400,'timeout')
  if phase==0 then
   log('opened_process_before='..getOpenedProcessID());check('before-load',false);file('load');phase=1;timer.Enabled=true
  elseif phase==1 and exists('loaded') then
   check('loaded-before-openProcess',true)
   for i=1,50 do assert(pcall(B.validate,pid),'repeat validation '..i..' failed') end
   log('repeat_validation_before_openProcess=50 PASS')
   assert(openProcess(pid)~=false);check('loaded-after-openProcess',true);finish(true)
  else timer.Enabled=true end
 end)
 if not ok then finish(false,err)end
end
timer.Enabled=true
'''
                table=ET.Element('CheatTable',CheatEngineTableVersion='45');ET.SubElement(table,'CheatEntries');ET.SubElement(table,'LuaScript').text=script
                tablefile=root/'probe.CETRAINER';ET.ElementTree(table).write(tablefile,encoding='utf-8',xml_declaration=True)
                si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
                ce=subprocess.Popen([str(CE/'cheatengine-x86_64.exe'),str(tablefile),'NOAUTORUN'],cwd=CE,startupinfo=si)
                assert ce.wait(timeout=30)==0
                result=(root/'result.txt').read_text(encoding='utf8')
                (OUT/(case+'.txt')).write_text(result,encoding='utf8')
                print(case+':\n'+result,flush=True)
                assert result.endswith('PASS'),result
                summaries.append({'case':case,'passed':True})
            finally:
                for name in ('trace.txt','result.txt','loaded'):
                    if (root/name).exists():
                        value=(root/name).read_text(encoding='utf8',errors='replace')
                        (OUT/(case+'-'+name)).write_text(value,encoding='utf8')
                        if name=='trace.txt':print('TRACE '+case+':\n'+'\n'.join(value.splitlines()[-12:]),flush=True)
                (root/'stop').touch()
                for proc in (p,ce):
                    if proc and proc.poll() is None:
                        try:proc.wait(timeout=3)
                        except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=3)
                stdout,stderr=p.communicate()
                if stderr:print('DLL host stderr:',stderr.decode(errors='replace'),flush=True)
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==value for path,value in before.items())
    report={'cases':summaries,'protected_files_unchanged':len(before),'game_launched':False,'protected_inputs_unchanged':True}
    (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':child(Path(sys.argv[2]),Path(sys.argv[3]))
    else:main()

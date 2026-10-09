from pathlib import Path
import json, subprocess, sys, time, xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
OUT=WORK/'analysis/kingdom-rush/ce-fixture'
CE=WORK/'analysis/kingdom-rush/ce-dev'

def literal(s):return '[=====['+s+']=====]'

def runtime_payload():
    code=(HERE.parent/'kingdom_rush_trainer/runtime.lua').read_text(encoding='utf8').replace("'kr_trainer/'","'kr_trainer_ce/'").replace("'kr_trainer'","'kr_trainer_ce'")
    code=code.replace('tower_damage=1}', 'tower_damage=1,tower_rate=1,soldier_rate=1,hero_rate=1,enemy_gold=1,enemy_speed=1,enemy_damage=1}')
    code=code.replace('speed={0.5,5}', 'speed={0.5,10}')
    code=code.replace('tower_damage={0.1,100}}','tower_damage={0.1,100},tower_rate={1,10},soldier_rate={1,10},hero_rate={1,10},enemy_gold={1,100},enemy_speed={0.1,1},enemy_damage={0,1}}')
    return """assert(type(love)=='table' and type(love.update)=='function' and package.loaded.storage,'not a ready main game state')
if not KR_CE_RUNTIME then
local T=(function()\n"""+code+"""\nend)()
local progression=(function()\n"""+(HERE/'progression.lua').read_text(encoding='utf8')+"""\nend)()
progression(T)
local combat=(function()\n"""+(HERE/'combat.lua').read_text(encoding='utf8')+"""\nend)()
combat(T)
T.install()
KR_CE_RUNTIME=T
end
assert(KR_CE_RUNTIME.ce_version=='2.2 RC2','修改器版本已更新，请退出游戏后重新连接')
KR_CE_RUNTIME.hook();KR_CE_RUNTIME.poll(true);KR_CE_RUNTIME.status()
return 'KR_CE_READY'
"""

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for n in ('stop','pause','paused','fixture.json','fixture-result.json','bridge-result.txt'):
        p=OUT/n
        if p.exists():p.unlink()
    fixture=subprocess.Popen([sys.executable,str(HERE/'fixture.py')],cwd=WORK,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    ce=None
    try:
        deadline=time.monotonic()+10
        while not (OUT/'fixture.json').exists() and time.monotonic()<deadline:time.sleep(.05)
        info=json.loads((OUT/'fixture.json').read_text())
        cases=[("fixture_counter=fixture_counter+1;return 'simple ok'",True,'simple ok'),
            ('not valid lua %%',False,None),("error('deliberate')",False,'deliberate'),
            ("return string.rep('x',3000)",True,'x'*2046),(runtime_payload(),True,'KR_CE_READY'),
            ("KR_CE_RUNTIME.cfg.hero_damage=5;KR_CE_RUNTIME.command({action='reset'});assert(KR_CE_RUNTIME.cfg.hero_damage==1);return 'reset ok'",True,'reset ok'),
            (runtime_payload(),True,'KR_CE_READY'),("return tostring(fixture_counter)",True,'1'),
            ("package.loaded.game={game_gui={},store={player_gold=100}};fixture_seq=os.time()*1000;love.filesystem.write('kr_trainer_ce/control.txt','seq='..fixture_seq..'\\naction=gold\\nvalue=900');"+runtime_payload(),True,'KR_CE_READY'),
            ("KR_CE_RUNTIME.poll();assert(package.loaded.game.store.player_gold==100);return 'stale command skipped'",True,'stale command skipped'),
            ("love.filesystem.write('kr_trainer_ce/control.txt','seq='..(fixture_seq+1)..'\\naction=gold\\nvalue=900');KR_CE_RUNTIME.poll();assert(package.loaded.game.store.player_gold==900);package.loaded.game.store.player_gold=120;KR_CE_RUNTIME.poll();assert(package.loaded.game.store.player_gold==120);return 'new command executed once'",True,'new command executed once')]
        lua='local B=(function()\n'+(HERE/'bridge.lua').read_text(encoding='utf8')+'\nend)()\n'
        lua+='local out='+literal((OUT/'bridge-result.txt').as_posix())+'\n'
        lua+='local tests={'+','.join('{code='+literal(c)+',ok='+str(ok).lower()+(',expected='+literal(expected) if expected is not None else '')+'}' for c,ok,expected in cases)+'}\n'
        lua+='local f={name="KR_CE_OFFLINE_FIXTURE",pid=%d,slot=%d,base=%d}\n'%(info['pid'],info['slot'],info['base'])
        lua+='local failure_tests=(function()\n'+(HERE/'test_bridge_failures.lua').read_text(encoding='utf8')+'\nend)()\n'
        lua+='local fault_step=failure_tests(B,f,'+literal(OUT.as_posix())+')\n'
        lua+='''local function finish(s)
 local h=assert(io.open(out,'w'));h:write(s);h:close();createTimer(100,function()closeCE()end)
end
local ok,err=pcall(function()
 assert(not pcall(B.validate,f.pid),'fixture passed production validation')
 B.start(f.pid,f)
end)
if not ok then finish('FAIL start '..tostring(err));return end
local index=1;local awaiting=false;local ticks=0
local timer=createTimer(nil,false);timer.Interval=25
timer.OnTimer=function()
 ticks=ticks+1
 local ok,err=pcall(function()
  assert(ticks<1200,'timeout')
  if index>#tests then
   if fault_step() then
    timer.Enabled=false;finish('PASS 11 remote payloads + 6 failure/recovery scenarios, IAT restored, production identity gate passed')
   end
   return
  end
  if not awaiting then B.submit(tests[index].code);awaiting=true;return end
  local success,result=B.poll()
  if success==nil then return end
  assert(success==tests[index].ok,'case '..index..' status '..tostring(result))
  if tests[index].expected then
   assert(result:find(tests[index].expected,1,true),'case '..index..' result '..tostring(result))
  end
  index=index+1;awaiting=false
  if index>#tests then
   assert(B.detach())
  end
 end)
 if not ok then timer.Enabled=false;pcall(B.cancel);finish('FAIL case '..index..': '..tostring(err))end
end
timer.Enabled=true
'''
        table=ET.Element('CheatTable',CheatEngineTableVersion='45');ET.SubElement(table,'CheatEntries');ET.SubElement(table,'LuaScript').text=lua
        path=OUT/'bridge-test.CETRAINER';ET.ElementTree(table).write(path,encoding='utf-8',xml_declaration=True)
        si=subprocess.STARTUPINFO();si.dwFlags|=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
        ce=subprocess.Popen([str(CE/'cheatengine-x86_64.exe'),str(path),'NOAUTORUN'],cwd=CE,startupinfo=si)
        code=ce.wait(timeout=40)
        result=(OUT/'bridge-result.txt').read_text();print('CE exit',code,result)
        (OUT/'stop').touch();stdout=fixture.communicate(timeout=5)[0]
        assert fixture.returncode==0,stdout.decode(errors='replace')
        print((OUT/'fixture-result.json').read_text())
        assert result.startswith('PASS')
        assert json.loads((OUT/'fixture-result.json').read_text())['pointer_restored']
    finally:
        (OUT/'stop').touch()
        for p in (fixture,ce):
            if p and p.poll() is None:p.terminate();p.wait(timeout=5)

if __name__=='__main__':main()

"""Package only our code plus the user's CE runtime, never game assets."""
from pathlib import Path
import os,hashlib,json,shutil,xml.etree.ElementTree as ET
from run_bridge_test import runtime_payload,literal
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
STAGE=WORK/'analysis/kingdom-rush/ce-stage'
OUT=WORK/'output/KingdomRushCE-2.2-RC2'
CE=Path(os.environ['KR_CE_DIR'])

def build():
    STAGE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    (STAGE/'ce').mkdir(exist_ok=True)
    shared=(HERE.parent/'kingdom_rush_trainer/trainer.py').read_text(encoding='utf8')
    shared=shared.replace('kr_trainer','kr_trainer_ce')
    shared=shared.replace('请先启动修改版游戏并选择存档。','请先连接原版游戏并选择存档。')
    shared=shared.replace('请检查是否启动修改版、是否停在错误画面。','请检查连接状态、是否停在错误画面。')
    shared=shared.replace('金币 · 生命 · 速度 · 升级星星 · 钻石 · 战斗伤害','金币 · 生命 · 速度 · 星星 · 战斗伤害 · 英雄与成就')
    shared=shared.replace('星星、钻石与说明','星星、解锁与说明')
    shared=shared.replace('星星、钻石和已购买升级保留。','英雄解锁、成就、星星和已购买升级保留。')
    shared=shared.replace("钻石 {s.get('gems','0')} / ",'')
    shared=shared.replace('tower_damage=1)', 'tower_damage=1,tower_rate=1,soldier_rate=1,hero_rate=1,enemy_gold=1,enemy_speed=1,enemy_damage=1)')
    shared=shared.replace('speed=(0.5,5)','speed=(0.5,10)')
    shared=shared.replace('tower_damage=(0.1,100))','tower_damage=(0.1,100),tower_rate=(1,10),soldier_rate=(1,10),hero_rate=(1,10),enemy_gold=(1,100),enemy_speed=(0.1,1),enemy_damage=(0,1))')
    shared=shared.replace("('speed','hero_damage','soldier_damage','tower_damage')", "('speed','hero_damage','soldier_damage','tower_damage','tower_rate','soldier_rate','hero_rate','enemy_gold','enemy_speed','enemy_damage')")
    shared=shared.replace("('0.5','1','2','3','5')","('0.5','1','2','3','5','10')")
    (STAGE/'panel_base.py').write_text(shared,encoding='utf8')
    shutil.copy2(HERE/'panel.py',STAGE/'panel.py')
    for name in ('cheatengine-x86_64.exe','lua53-64.dll','defines.lua'):
        shutil.copy2(CE/name,STAGE/'ce'/name)
    (STAGE/'ce/main.lua').write_text('require("defines")\n',encoding='utf8')
    bridge=(HERE/'bridge.lua').read_text(encoding='utf8')
    # Fixture overrides must never be included in the production backend.
    bridge=bridge.replace('function B.start(pid,fixture)','function B.start(pid)')
    begin=bridge.index(' local slot,base\n')
    end=bridge.index(" assert(openProcess(pid)",begin)
    bridge=bridge[:begin]+' local slot,base=B.validate(pid)\n'+bridge[end:]
    lua='local B=(function()\n'+bridge+'\nend)()\nlocal PAYLOAD='+literal(runtime_payload())+'\n'+(HERE/'backend_entry.lua').read_text(encoding='utf8')
    table=ET.Element('CheatTable',CheatEngineTableVersion='45')
    ET.SubElement(table,'CheatEntries');ET.SubElement(table,'LuaScript').text=lua
    ET.ElementTree(table).write(STAGE/'ce/attach.CETRAINER',encoding='utf-8',xml_declaration=True)
    # Offline-only inputs live outside the bundled ce/ directory.
    (STAGE/'test-payload.lua').write_text(runtime_payload(),encoding='utf8')
    speed_test=(HERE.parent/'kingdom_rush_trainer/test_original_bytecode.lua').read_text(encoding='utf8')
    speed_test=speed_test.replace('{0.5,1,2,3,5}','{0.5,1,2,3,5,10}').replace('T.cfg.speed=5','T.cfg.speed=10')
    (STAGE/'test-ten-speed.lua').write_text(speed_test,encoding='utf8')
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (STAGE/'ce').iterdir() if p.is_file() and p.name!='manifest.json'}
    (STAGE/'ce/manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    assert 'KR_CE_OFFLINE_FIXTURE' not in lua
    assert not any('Kingdom Rush.exe'==p.name or p.name in ('love.dll','lua51.dll') for p in STAGE.rglob('*'))
    print(STAGE)

if __name__=='__main__':build()

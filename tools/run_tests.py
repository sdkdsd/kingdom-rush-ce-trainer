from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parents[1]
runner='tools/kingdom_rush_trainer/lua_runner.py'
jobs=[[runner,'tools/kingdom_rush_trainer/'+n] for n in ('test_runtime.lua','test_regressions.lua','test_original_bytecode.lua')]
jobs += [[runner,'tools/kingdom_rush_ce/test_progression.lua'],
 ['tools/kingdom_rush_trainer/test_offline_panel.py'],['tools/kingdom_rush_ce/test_panel.py'],['tools/kingdom_rush_ce/run_bridge_test.py']]
for job in jobs:subprocess.run([sys.executable,*job],cwd=root,check=True,timeout=60)
print('All offline tests passed. No game launch or real Steam achievement changes.')

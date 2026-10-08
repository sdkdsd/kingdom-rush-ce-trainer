from pathlib import Path
import os,shutil,zipfile
root=Path(__file__).resolve().parents[1]
game=Path(os.environ['KR_GAME_DIR']);ce=Path(os.environ['KR_CE_DIR'])
entries={'lib/klove/simulation.lua':'originals/lib/klove/simulation.lua',
 'lib/middleclass.lua':'originals/lib/middleclass.lua',
 'kr1-desktop/data/map_data.lua':'progression/map_data.lua',
 'kr1/data/achievements_data.lua':'progression/achievements_data.lua',
 'kr1/data/slot_template.lua':'progression/slot_template.lua'}
with zipfile.ZipFile(game/'Kingdom Rush.exe') as z:
 for source,target in entries.items():
  p=root/'analysis/kingdom-rush/offline'/target;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(source))
dev=root/'analysis/kingdom-rush/ce-dev';dev.mkdir(parents=True,exist_ok=True)
for name in ('cheatengine-x86_64.exe','lua53-64.dll','defines.lua'):shutil.copy2(ce/name,dev/name)
(dev/'main.lua').write_text('require("defines")\n',encoding='utf8')
print('Prepared local-only fixtures; no game process launched.')

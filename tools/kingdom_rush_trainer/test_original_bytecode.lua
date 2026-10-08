-- Real shipped simulation and middleclass, loaded in LuaJIT without LÖVE/graphics.
local base='analysis/kingdom-rush/offline/originals/'
local checks=0
local function check(ok,why) assert(ok,why);checks=checks+1 end
local km={clamp=function(lo,hi,x)return math.min(hi,math.max(lo,x))end}
local log=setmetatable({},{__index=function()return function()end end})
package.loaded['klua.log']={new=function()return log end}
package.loaded['klua.macros']=km
local sim=assert(loadfile(base..'lib/klove/simulation.lua'))()
local class=assert(loadfile(base..'lib/middleclass.lua'))()
package.loaded['klove.simulation']=sim
local data={gems=330}
package.loaded.storage={active_slot_idx=1,load_slot=function()return data end}
local files={['kr_trainer/bonus_1.txt']='99'}
love={filesystem={exists=function(p)return files[p]~=nil end,read=function(p)return files[p]end,
    createDirectory=function()end,write=function(p,v)files[p]=v;return true end}}
PowerButton=class('PowerButton')
function PowerButton:update()self.updates=(self.updates or 0)+1 end
function PowerButton:set_mode(mode)self.mode=mode end
local Child=class('Power1Button',PowerButton)
UpgradesView=class('UpgradesView')
package.loaded.screen_map={total_stars=9}
function UpgradesView:set_stars_and_check()
    if self.fail then error('UI failure') end
    self.available=package.loaded.screen_map.total_stars-self.spent
end
function UpgradesView:update()end
local T=dofile('tools/kingdom_rush_trainer/runtime.lua')
T.hook()
local original_wrapper=PowerButton.update
for i=1,10 do T.hook() end
check(PowerButton.update==original_wrapper,'middleclass hook stacked')
local b=Child:new();b.mode='cooldown';T.cfg.cooldown=1;b:update(0.016)
check(b.mode=='ready' and b.updates==1,'child did not inherit patched cooldown')
b.mode='locked';b:update(0.016);check(b.mode=='locked','locked power unlocked')
T.cfg.cooldown=0;b.mode='cooldown';b:update(0.016);check(b.mode=='cooldown','disabled cooldown still active')
local view=UpgradesView:new();view.spent=7;view:set_stars_and_check()
check(view.available==101 and package.loaded.screen_map.total_stars==9,'bonus or restoration failed')
view.fail=true;check(not pcall(view.set_stars_and_check,view),'expected UI error')
check(package.loaded.screen_map.total_stars==9,'map stars not restored after exception')
package.loaded.storage.active_slot_idx=2;view.fail=false;view:set_stars_and_check()
check(view.available==2,'bonus leaked across slots')
for _,speed in ipairs({0.5,1,2,3,5}) do
    for _,fps in ipairs({60,120,144}) do
        local s={};sim:init(s,{}, {},1/60);T.cfg.speed=speed
        for i=1,10*fps do sim:update(1/fps)end
        check(math.abs(s.tick-speed*600)<=1.01,'tick drift '..speed..'x @'..fps..'fps: '..s.tick)
    end
end
-- Seeded frame jitter at high enough render rate to exercise all speeds.
math.randomseed(42)
for _,speed in ipairs({0.5,1,2,3,5})do
    local s={};sim:init(s,{}, {},1/60);T.cfg.speed=speed;local elapsed=0
    for i=1,1500 do local dt=(2+math.random()*5)/1000;elapsed=elapsed+dt;sim:update(dt)end
    check(math.abs(s.tick-elapsed*speed*60)<1.01,'jitter time drift '..speed)
end
local s={};sim:init(s,{}, {},1/60);s.paused=true;T.cfg.speed=5
sim:update(0.1);check(s.tick==0,'pause advanced simulation')
s.step=true;sim:update(0.1);check(s.tick==1 and not s.step,'paused step did not advance exactly once')
s._kr_sources[1]='hero';T.counts.hero=100;sim:init(s,{}, {},1/60)
check(next(s._kr_sources)==nil and T.counts.hero==0,'restart leaked source cache')
local e={id=123,hero={}};sim:insert_entity(e)
check(s._kr_sources[123]=='hero','insert did not record source')
print('ORIGINAL BYTECODE CHECKS PASS: '..checks)

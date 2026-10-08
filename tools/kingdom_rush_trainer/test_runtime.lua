local files={}
love={filesystem={exists=function(p) return files[p]~=nil end,
    read=function(p) return files[p] end, createDirectory=function() end,
    write=function(p,v) files[p]=v; return true end}}
local T=dofile('tools/kingdom_rush_trainer/runtime.lua')
local total=0
local function eq(a,b) assert(a==b,tostring(a)..' ~= '..tostring(b)); total=total+1 end
local function near(a,b) assert(math.abs(a-b)<0.00001); total=total+1 end
local hero,soldier,tower={id=1,hero={}}, {id=2,soldier={}}, {id=3,tower={}}
local enemy,projectile={id=4,enemy={}}, {id=5,bullet={source_id=1}}
local s={entities={[1]=hero,[2]=soldier,[3]=tower,[4]=enemy,[5]=projectile},damage_queue={}}
eq(T.classify(hero,s),'hero');eq(T.classify(soldier,s),'soldier');eq(T.classify(tower,s),'tower')
eq(T.classify(enemy,s),nil);eq(T.classify(projectile,s),'hero')
local cycle={id=6,source_id=6};s.entities[6]=cycle;eq(T.classify(cycle,s),nil)
T.cfg.hero_damage=3;T.cfg.soldier_damage=4;T.cfg.tower_damage=5
for i=1,5 do s.damage_queue[i]={source_id=i,target_id=4,value=10,damage_type=2} end
s.damage_queue[6]={source_id=1,target_id=2,value=10,damage_type=2}
s.damage_queue[7]={source_id=1,target_id=4,value=10,damage_type=256}
s.damage_queue[8]={source_id=1,target_id=4,value=10,damage_type=2,damage_applied=0}
T.scale_damage(s)
for i,v in ipairs({30,40,50,10,30,10,10,10}) do eq(s.damage_queue[i].value,v) end
T.scale_damage(s);eq(s.damage_queue[1].value,30)
s._kr_sources={[8]='hero'};s.damage_queue={{source_id=8,target_id=4,value=10,damage_type=1}}
T.scale_damage(s);eq(s.damage_queue[1].value,30)
local simulated=0
local sim={store={tick_length=1/30},update=function(self,dt) simulated=simulated+dt end,
    insert_entity=function(self,e) self.store.entities[e.id]=e end,init=function() end}
local sys={health={on_update=function() end},goal_line={on_update=function(_,_,_,st) st.lives=0 end},level={on_update=function() end}}
package.loaded['klove.simulation']=sim;package.loaded.systems=sys
PowerButton={update=function() end,set_mode=function(self,v) self.mode=v end}
UpgradesView={set_stars_and_check=function(self) self.value=package.loaded.screen_map.total_stars-self.spent_stars end,update=function() end}
package.loaded.screen_map={total_stars=9}
package.loaded.storage={active_slot_idx=1}
files['kr_trainer/bonus_1.txt']='99'
T.hook(); local hook=sim.update;local pb=PowerButton.update;T.hook();eq(hook,sim.update);eq(pb,PowerButton.update)
for _,speed in ipairs({0.5,1,2,3,5}) do
    simulated=0;T.cfg.speed=speed;sim:update(0.02);near(simulated,0.02*speed)
end
sim.store.paused=true;simulated=0;sim:update(0.02);near(simulated,0.02)
T.cfg.lives_lock=20;sys.goal_line:on_update(0,0,s);eq(s.lives,20)
local button=setmetatable({mode='cooldown'},{__index=PowerButton})
T.cfg.cooldown=1;button:update(0);eq(button.mode,'ready')
button.mode='locked';button:update(0);eq(button.mode,'locked')
local view=setmetatable({spent_stars=7},{__index=UpgradesView})
view:set_stars_and_check();eq(view.value,101);eq(package.loaded.screen_map.total_stars,9)
package.loaded.storage.active_slot_idx=2;view:set_stars_and_check();eq(view.value,2)
package.loaded.game={game_gui={},store=s}
T.command({action='gold',value='1234'});eq(s.player_gold,1234)
eq(pcall(T.command,{action='lives',value='0'}),false)
T.command({action='stars',value='15'});eq(files['kr_trainer/bonus_2.txt'],'15')
files['kr_trainer/control.txt']='seq=123\naction=gold\nvalue=999\nhero_damage=nan\nspeed=999'
T.poll();eq(s.player_gold,999);eq(T.cfg.hero_damage,3)
s.player_gold=500;T.poll();eq(s.player_gold,500)
T.command({action='reset'});eq(T.cfg.hero_damage,1);eq(T.cfg.lives_lock,0);eq(T.cfg.speed,1)
print('RUNTIME TESTS PASS: '..total)

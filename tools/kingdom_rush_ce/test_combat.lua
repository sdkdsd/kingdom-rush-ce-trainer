local files={}
love={update=function()end,filesystem={exists=function(p)return files[p]~=nil end,
 read=function(p)return files[p]end,write=function(p,v)files[p]=v;return true end,createDirectory=function()end}}
package.loaded.storage={load_slot=function()end}
dofile('analysis/kingdom-rush/ce-stage/test-payload.lua')
local T=KR_CE_RUNTIME;local n=0
local function eq(a,b)assert(math.abs(a-b)<1e-6,tostring(a)..' ~= '..tostring(b));n=n+1 end
local function check(v,m)assert(v,m);n=n+1 end
local function unit(id,kind)
 return {id=id,[kind]={},health={},attacks={min_cooldown=.4,list={{ts=0,cooldown=1,shoot_time=.2,hit_times={.1,.2},animation='shoot'}}},render={sprites={{name='shoot',animated=true},{name='walk'}}}}
end
local tower,soldier,hero,enemy=unit(1,'tower'),unit(2,'soldier'),unit(3,'hero'),unit(4,'enemy')
soldier.tower={} -- direct soldier classification wins over its tower component.
enemy.enemy.gold=7
local s={entities={[1]=tower,[2]=soldier,[3]=hero,[4]=enemy},damage_queue={},tick_ts=1,player_gold=0}
local sys={main_script={on_update=function()end},health={on_update=function(_,dt,ts,store)
 for _,e in pairs(store.entities)do if e.enemy and e.health.hp==0 and not e.health.dead then
  store.player_gold=store.player_gold+e.enemy.gold;e.health.dead=true
 end end
end},goal_line={on_update=function(_,dt,ts,store)store.player_gold=store.player_gold+enemy.enemy.gold end},
level={on_update=function()end},render={on_update=function()
 eq(tower.render.sprites[1].fps,150);eq(soldier.render.sprites[1].fps,60)
 check(tower.render.sprites[2].fps==nil,'walk animation accelerated')
end}}
package.loaded.systems=sys
local seen_dt
package.loaded.utils={walk=function(e,dt)seen_dt=dt;return 'walked' end}
T.cfg.tower_rate=5;T.cfg.soldier_rate=2;T.cfg.hero_rate=3
sys.main_script.on_update=function()
 eq(tower.attacks.list[1].ts,-.4);eq(soldier.attacks.list[1].ts,-.1);eq(hero.attacks.list[1].ts,-.2)
 eq(enemy.attacks.list[1].ts,0);eq(tower.attacks.list[1].shoot_time,.04)
 eq(tower.attacks.list[1].hit_times[2],.04)
 eq(tower.attacks.list[1].cooldown,1) -- original buffs/cooldowns are not overwritten.
end
T.hook();sys.main_script:on_update(.1,1,s)
eq(tower.attacks.list[1].shoot_time,.2);eq(tower.attacks.list[1].hit_times[2],.2)
sys.render:on_update(.1,1,s)
check(tower.render.sprites[1].fps==nil,'temporary fps leaked')
T.cfg.enemy_speed=.25
check(package.loaded.utils.walk(enemy,.2)=='walked','walk return changed');eq(seen_dt,.05)
package.loaded.utils.walk(soldier,.2);eq(seen_dt,.2)
T.cfg.enemy_gold=3;enemy.health.hp=0
sys.health:on_update(.1,1,s);eq(s.player_gold,21);eq(enemy.enemy.gold,7)
sys.health:on_update(.1,1,s);eq(s.player_gold,21)
sys.goal_line:on_update(.1,1,s);eq(s.player_gold,28) -- leak refunds unchanged.
local bullet={id=5,bullet={source_id=4}};s.entities[5]=bullet
local aura={id=6,aura={source_id=5}};s.entities[6]=aura
T.cfg.enemy_damage=.25;T.cfg.hero_damage=2
s.damage_queue={{source_id=6,target_id=3,value=40,damage_type=1},
 {source_id=3,target_id=4,value=40,damage_type=1},
 {source_id=4,target_id=3,value=40,damage_type=256},
 {source_id=4,target_id=4,value=40,damage_type=1}}
sys.health:on_update(.1,1,s)
eq(s.damage_queue[1].value,10);eq(s.damage_queue[2].value,80)
eq(s.damage_queue[3].value,40);eq(s.damage_queue[4].value,40)
sys.health:on_update(.1,1,s);eq(s.damage_queue[1].value,10)
-- Sources survive shooter removal, but reused IDs must respect live entities.
s.entities[4]=nil
check(T.enemy_source(s,6),'removed enemy source lost')
s.entities[4]=hero;check(not T.enemy_source(s,6),'live friendly ID treated as stale enemy')
s.entities[4]=enemy
T.cfg.enemy_damage=0;s.damage_queue={{source_id=4,target_id=3,value=40,damage_type=1}}
sys.health:on_update(.1,1,s);eq(s.damage_queue[1].value,0)
files['kr_trainer_ce/control.txt']='seq=10\nspeed=10\ntower_rate=10\nenemy_gold=100\nenemy_speed=0.1\nenemy_damage=0'
T.poll();eq(T.cfg.speed,10);eq(T.cfg.tower_rate,10);eq(T.cfg.enemy_gold,100)
files['kr_trainer_ce/control.txt']='seq=11\nspeed=11\ntower_rate=11\nenemy_speed=0\nenemy_damage=-1'
T.poll();eq(T.cfg.speed,10);eq(T.cfg.tower_rate,10);eq(T.cfg.enemy_speed,.1);eq(T.cfg.enemy_damage,0)
T.command{action='reset'}
for _,k in ipairs({'speed','tower_rate','soldier_rate','hero_rate','enemy_gold','enemy_speed','enemy_damage'})do eq(T.cfg[k],1)end
-- Exception recovery for temporary gold, attack timing and animation fields.
package.loaded.systems={health={on_update=function()error('health failure')end},goal_line={on_update=function()end},level={on_update=function()end},
 main_script={on_update=function()error('script failure')end},render={on_update=function()error('render failure')end}}
T.cfg.tower_rate=4;T.cfg.enemy_gold=4;T.hook();sys=package.loaded.systems
check(not pcall(sys.health.on_update,sys.health,.1,1,s),'missing health error');eq(enemy.enemy.gold,7)
check(not pcall(sys.main_script.on_update,sys.main_script,.1,1,s),'missing script error');eq(tower.attacks.list[1].shoot_time,.2)
check(not pcall(sys.render.on_update,sys.render,.1,1,s),'missing render error');check(tower.render.sprites[1].fps==nil,'fps leaked on exception')
local hook=sys.health.on_update;T.hook();check(hook==sys.health.on_update,'hooks stacked')
print('COMBAT CHECKS PASS: '..n)

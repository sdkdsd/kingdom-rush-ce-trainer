local root='analysis/kingdom-rush/offline/progression/'
local function dummy()return setmetatable({},{__index=function(t,k)local v=dummy();rawset(t,k,v);return v end})end
package.preload['klua.vector']=function()return {v=function(x,y)return{x=x,y=y}end,r=function(...)return{...}end}end
package.preload['map_decos_functions']=dummy
package.preload['data.map_animations_paths']=dummy
package.preload['i18n']=function()return {cjk=function(_,v)return v end}end
GGLabel={static={ref_h=768}};REF_H=768
local mapdata=dofile(root..'map_data.lua')
local entries=dofile(root..'achievements_data.lua')
local template=dofile(root..'slot_template.lua')
package.loaded['data.achievements_data']=entries
local class=dofile('analysis/kingdom-rush/offline/originals/lib/middleclass.lua')
local extension=dofile('tools/kingdom_rush_ce/progression.lua')
local function clone(t)if type(t)~='table'then return t end;local c={};for k,v in pairs(t)do c[k]=clone(v)end;return c end
local count=0
local function check(b,message)assert(b,message);count=count+1 end
local function fixture()
 local slots={clone(template),clone(template)}
 for _,slot in ipairs(slots)do slot.levels={{stars=0}} end
 local env={saves=0,sets=0,stores=0,ready=true,remote={}}
 local st={active_slot_idx=1,load_slot=function(self)return slots[self.active_slot_idx]end,
  save_slot=function(self,data,slot)
   env.saves=env.saves+1;if env.savefail then return false end
   slots[slot]=data;return true
  end}
 local room={hidden=true,get_child_by_id=function()return {set_image=function()end}end}
 local map={window={},user_data=slots[1],hero_data=clone(mapdata.hero_data),hero_room=room,achievements={hidden=true}}
 local steam={inited=true,name='steam',userstats_ptr=1,ids={achievements={FIRST_BLOOD='MAPPED_FIRST'}},lib={}}
 steam.lib.SteamAPI_ISteamUserStats_GetAchievement=function(_,id,out)out[0]=env.remote[id] or false;return env.ready end
 steam.lib.SteamAPI_ISteamUserStats_SetAchievement=function(_,id)
  env.sets=env.sets+1;if env.setfail==id then return false end;env.remote[id]=true;return true
 end
 steam.lib.SteamAPI_ISteamUserStats_StoreStats=function()env.stores=env.stores+1;return not env.storefail end
 package.loaded.storage=st;package.loaded.screen_map=map;package.loaded.game=nil
 package.loaded.platform_services={services={achievements=steam}}
 package.loaded.achievements={ach={},dirty=false}
 HeroRoomViewKR1=class('TestHeroRoom')
 HeroRoomViewKR1.initialize=function(self)self.limit=map.hero_data[1].available_level end
 HeroRoomViewKR1.show_hero=function(self)return map.hero_data[1].available_level end
 UpgradesView=nil;PowerButton=nil
 local T=dofile('tools/kingdom_rush_trainer/runtime.lua');extension(T)
 return T,env,st,map,slots
end
check(#mapdata.hero_data==13,'original hero count')
check(#entries==74,'original achievement count')
local T,e,st,map,slots=fixture()
local first=map.hero_data[1].available_level;local levelcount=#slots[1].levels
T.command{action='unlock_heroes',value='1'}
check(slots[1]._kr_ce_all_heroes and e.saves==1,'hero flag persisted')
check(#slots[1].levels==levelcount and slots[1].levels[1].stars==0,'no false progression')
for _,h in ipairs(map.hero_data)do check(h.available_level==1,'hero unlocked: '..h.name)end
T.hook();local wrapper=HeroRoomViewKR1.initialize;T.hook()
check(wrapper==HeroRoomViewKR1.initialize,'no repeated class wrapping')
check(HeroRoomViewKR1:new().limit==1,'original middleclass initializer applies unlock')
st.active_slot_idx=2;map.user_data=slots[2];T.hook()
check(map.hero_data[1].available_level==first,'slot isolation restores requirements')
check(HeroRoomViewKR1:new():show_hero()==first,'other slot remains locked')
st.active_slot_idx=1;map.user_data=slots[1];T.hook()
check(map.hero_data[1].available_level==1,'return to unlocked slot')
T,e,st,map,slots=fixture();e.savefail=true
check(not pcall(T.command,{action='unlock_heroes',value='1'}),'hero save failure reported')
check(not slots[1]._kr_ce_all_heroes and map.hero_data[1].available_level==first,'hero save failure has no cached mutation')
T,e,st,map,slots=fixture()
check(not pcall(T.command,{action='unlock_heroes',value='2'}),'stale slot rejected')
package.loaded.game={game_gui={}}
check(not pcall(T.command,{action='unlock_heroes',value='1'}),'battle rejects progression edit')
package.loaded.game=nil;map.hero_room.hidden=false
check(not pcall(T.command,{action='unlock_heroes',value='1'}),'open hero UI rejected')
local cmd={action='unlock_achievements',value='1|我确认解锁全部成就'}
T,e,st,map,slots=fixture()
check(not pcall(T.command,{action=cmd.action,value='1|确认'}),'runtime rejects wrong confirmation')
check(e.saves==0 and e.sets==0,'confirmation failure no writes')
e.ready=false
check(not pcall(T.command,cmd),'unready Steam rejected')
check(e.saves==0 and e.sets==0,'preflight failure before local save')
e.ready=true;e.savefail=true
check(not pcall(T.command,cmd),'achievement save failure reported')
check(e.sets==0 and e.stores==0 and not slots[1].achievements[entries[1].name],'save failure never touches Steam')
T,e,st,map,slots=fixture();T.command(cmd)
check(e.sets==74 and e.stores==1,'74 Steam changes batched in one submission')
check(e.remote.MAPPED_FIRST==true,'Steam identifier mapping honored')
for _,a in ipairs(entries)do check(slots[1].achievements[a.name]==true,'local achievement: '..a.name)end
check(package.loaded.achievements.ach==map.user_data.achievements,'achievement caches synchronized')
check(#slots[1].levels==levelcount and not slots[2].achievements[entries[1].name],'other slot and levels preserved')
T.command(cmd);check(e.sets==74 and e.stores==2,'already unlocked achievements not set again')
T,e,st,map,slots=fixture();e.setfail='MAPPED_FIRST'
local ok,err=pcall(T.command,cmd)
check(not ok and tostring(err):find('部分失败',1,true),'partial Steam failure explicit')
check(e.stores==1 and slots[1].achievements.FIRST_BLOOD,'partial failure state retained honestly')
T,e,st,map,slots=fixture();e.storefail=true
ok,err=pcall(T.command,cmd)
check(not ok and tostring(err):find('Steam 提交失败',1,true),'Steam store failure explicit')
check(slots[1].achievements.FIRST_BLOOD,'no false rollback of saved state')
check(not pcall(T.command,{action='gems',value=999}),'unsupported gems rejected')
print('PROGRESSION CHECKS PASS: '..count..'; original 13 heroes / 74 achievements; Steam fully mocked')

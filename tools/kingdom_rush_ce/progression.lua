-- Installed only in the CE edition. No command is executed during installation.
return function(T)
 local VERSION='2.1 RC1'
 local PHRASE='我确认解锁全部成就'
 local originals=setmetatable({},{__mode='k'})
 local last_room,last_slot,last_enabled
 local function clone(t)
  if type(t)~='table' then return t end
  local c={};for k,v in pairs(t)do c[k]=clone(v)end;return c
 end
 local function context(slot)
  local st=assert(package.loaded.storage,'storage unavailable')
  assert(st.active_slot_idx==slot and slot>=1 and slot<=3,'存档已切换，请重新确认')
  local game=package.loaded.game
  assert(not (game and game.game_gui),'请先返回地图')
  local map=assert(package.loaded.screen_map,'请先进入地图')
  assert(map.window and map.user_data,'请先进入地图')
  assert(not map.hero_room or map.hero_room.hidden,'请先关闭英雄选择窗口')
  assert(not map.achievements or map.achievements.hidden,'请先关闭成就窗口')
  return st,map
 end
 function T.sync_heroes(refresh)
  local st=package.loaded.storage
  local map=package.loaded.screen_map
  if not st or not st.active_slot_idx or not map or not map.hero_data then return end
  local data=st:load_slot()
  local enabled=data and data._kr_ce_all_heroes==true
  refresh=refresh or map.hero_room~=last_room or st.active_slot_idx~=last_slot or enabled~=last_enabled
  for _,h in ipairs(map.hero_data)do
   if originals[h]==nil then originals[h]=h.available_level end
   h.available_level=enabled and 1 or originals[h]
   if refresh and enabled and map.hero_room and map.user_data then
    local thumb=map.hero_room:get_child_by_id(h.name)
    if thumb then
     local unlocked=h.available_level<=#map.user_data.levels
     thumb:set_image(string.format(unlocked and 'heroroom_thumbs_%04d' or 'heroroom_thumbs__off_%04d',h.thumb))
    end
   end
  end
  last_room,last_slot,last_enabled=map.hero_room,st.active_slot_idx,enabled
 end
 local hook=T.hook
 T.hook=function()
  hook();T.sync_heroes(false)
  if HeroRoomViewKR1 and not HeroRoomViewKR1._kr_ce_progression then
   HeroRoomViewKR1._kr_ce_progression=true
   local init,show=HeroRoomViewKR1.initialize,HeroRoomViewKR1.show_hero
   HeroRoomViewKR1.initialize=function(self,...)
    T.sync_heroes(false);return init(self,...)
   end
   HeroRoomViewKR1.show_hero=function(self,...)
    T.sync_heroes(false);return show(self,...)
   end
  end
 end
 local command=T.command
 T.command=function(c)
  if c.action=='unlock_heroes' then
   local slot=assert(tonumber(c.value),'missing save slot')
   local st,map=context(slot)
   assert(map.hero_data and #map.hero_data>0,'英雄数据尚未就绪')
   local data=clone(map.user_data);data._kr_ce_all_heroes=true
   assert(st:save_slot(data,slot),'保存失败，英雄状态未修改')
   map.user_data._kr_ce_all_heroes=true
   T.sync_heroes(true)
   T.progress_result='英雄已解锁 '..#map.hero_data..' 位；此存档连接修改器后生效'
  elseif c.action=='unlock_achievements' then
   local slot,phrase=tostring(c.value):match('^(%d+)|(.+)$')
   assert(phrase==PHRASE,'缺少完整的成就解锁确认')
   local st,map=context(tonumber(slot))
   local ps=package.loaded.platform_services
   local steam=ps and ps.services and ps.services.achievements
   assert(steam and steam.name=='steam' and steam.inited and steam.userstats_ptr,'Steam 成就服务未就绪')
   local entries=require('data.achievements_data')
   assert(#entries>0,'成就列表为空')
   local ffi=require('ffi');local flags=ffi.new('bool[1]')
   local names={};local seen={}
   for _,a in ipairs(entries)do
    assert(type(a.name)=='string' and not seen[a.name],'成就数据异常')
    seen[a.name]=true
    local id=steam.ids and steam.ids.achievements and steam.ids.achievements[a.name] or a.name
    assert(steam.lib.SteamAPI_ISteamUserStats_GetAchievement(steam.userstats_ptr,id,flags),'Steam 数据未就绪：'..id)
    names[#names+1]={local_id=a.name,steam_id=id,achieved=flags[0]}
   end
   local data=clone(map.user_data)
   local A=package.loaded.achievements
   data.achievements=clone(data.achievements or {})
   if A and A.ach then for k,v in pairs(A.ach)do data.achievements[k]=v end end
   if A and A.counters and P_LIFETIME and A.counters[P_LIFETIME] then
    data.achievement_counters=clone(A.counters[P_LIFETIME])
   end
   for _,n in ipairs(names)do data.achievements[n.local_id]=true end
   assert(st:save_slot(data,tonumber(slot)),'保存失败，未向 Steam 发送解锁')
   map.user_data.achievements=data.achievements
   map.user_data.achievement_counters=data.achievement_counters
   if A then A.ach=data.achievements;A.dirty=false end
   local failures={}
   for _,n in ipairs(names)do
    if not n.achieved then
     local ok,accepted=pcall(steam.lib.SteamAPI_ISteamUserStats_SetAchievement,steam.userstats_ptr,n.steam_id)
     if not ok or not accepted then failures[#failures+1]=n.steam_id end
    end
   end
   local ok,stored=pcall(steam.lib.SteamAPI_ISteamUserStats_StoreStats,steam.userstats_ptr)
   assert(ok and stored,'本地成就已解锁，Steam 提交失败；请恢复连接后重新确认重试')
   assert(#failures==0,'本地成就已解锁，Steam 部分失败：'..table.concat(failures,','))
   T.progress_result='本地 '..#names..' 项成就已解锁，Steam 已提交；请在 Steam 查看同步结果'
  elseif c.action=='gems' then
   error('当前 Steam PC 版未启用钻石商店')
  else return command(c)end
 end
 local poll=T.poll
 T.poll=function(...)
  T.progress_result=nil;poll(...)
  if T.progress_result then T.message='ok:'..T.progress_result end
 end
 local status=T.status
 T.status=function()
  status()
  local path='kr_trainer_ce/status.txt'
  local text=love.filesystem.read(path) or ''
  assert(love.filesystem.write(path,text..'\nce_version='..VERSION))
 end
 T.ce_version=VERSION
end

-- Extra combat controls. Temporary fields are restored even on script errors.
return function(T)
 local function rate(e)
  if e.enemy then return 1 end
  if e.hero then return T.cfg.hero_rate end
  if e.soldier then return T.cfg.soldier_rate end
  if e.tower then return T.cfg.tower_rate end
  return 1
 end
 local function groups(e)return {e.attacks or {},e.melee or {},e.ranged or {}}end
 local function edits()return {}end
 local function set(log,t,k,value)
  log[#log+1]={t,k,t[k],value};t[k]=value
 end
 local function multiply(log,t,k,f)
  if type(t[k])=='number' then set(log,t,k,t[k]*f)end
 end
 local function restore(log)
  for i=#log,1,-1 do local x=log[i];if x[1][x[2]]==x[4]then x[1][x[2]]=x[3]end end
 end
 local function invoke(log,fn,...)
  local ok,result=pcall(fn,...);restore(log)
  if not ok then error(result)end;return result
 end
 function T.enemy_source(store,id,seen)
  seen=seen or {};if not id or seen[id]then return false end;seen[id]=true
  local e=store.entities[id]
  if not e then return (store._kr_enemy_sources or {})[id]==true end
  if e.enemy then return true end
  if e.hero or e.soldier or e.tower then return false end
  local src=e.source_id or e.owner_id
  for _,key in ipairs({'bullet','modifier','aura','spawner'})do
   local part=e[key];if part and (part.source_id or part.owner_id)then src=part.source_id or part.owner_id;break end
  end
  return T.enemy_source(store,src,seen)
 end
 function T.combat_before(store,dt,ts)
  local log=edits();local seen={}
  store._kr_enemy_sources=store._kr_enemy_sources or {}
  for id,e in pairs(store.entities)do
   store._kr_enemy_sources[id]=T.enemy_source(store,id)
   local f=rate(e) or 1
   if f>1 and not (e.health and e.health.dead)then
    for _,group in ipairs(groups(e))do
     local list={group};for _,a in ipairs(group.list or group.attacks or {})do list[#list+1]=a end
     for _,a in ipairs(list)do
      if not seen[a]then
       seen[a]=true
       -- Advance cooldown progress without modifying buffed cooldown values.
       for _,key in ipairs({'ts','forced_ts'})do
        if type(a[key])=='number' and a[key]<=ts then a[key]=a[key]-dt*(f-1)end
       end
       for _,key in ipairs({'shoot_time','hit_time','min_cooldown'})do multiply(log,a,key,1/f)end
       for _,key in ipairs({'shoot_times','hit_times'})do
        if type(a[key])=='table'then for i in ipairs(a[key])do multiply(log,a[key],i,1/f)end end
       end
      end
     end
    end
   end
  end
  return log
 end
 local function attack_animation(e,name)
  if type(name)~='string'then return false end
  for _,g in ipairs(groups(e))do
   for _,a in ipairs(g.list or g.attacks or {})do
    local names=type(a.animation)=='table' and a.animation or {a.animation}
    for _,n in ipairs(names)do
     if type(n)=='string' and (name==n or name:sub(1,#n+1)==n..'_')then return true end
    end
   end
  end
  return false
 end
 local hook=T.hook
 T.hook=function()
  hook()
  local U=package.loaded.utils
  if U and U.walk and not U._kr_ce_slow then
   U._kr_ce_slow=true;local walk=U.walk
   U.walk=function(e,dt,...)
    return walk(e,dt*(e.enemy and T.cfg.enemy_speed or 1),...)
   end
  end
  local sim=package.loaded['klove.simulation']
  if sim and not sim._kr_ce_enemy_sources then
   sim._kr_ce_enemy_sources=true;local insert=sim.insert_entity;local init=sim.init
   sim.insert_entity=function(self,e)
    local result=insert(self,e)
    if self.store.entities[e.id]then
     self.store._kr_enemy_sources=self.store._kr_enemy_sources or {}
     self.store._kr_enemy_sources[e.id]=T.enemy_source(self.store,e.id)
    end
    return result
   end
   sim.init=function(self,...)
    local result=init(self,...);self.store._kr_enemy_sources={};return result
   end
  end
  local sys=package.loaded.systems
  if not sys or sys._kr_ce_combat then return end
  sys._kr_ce_combat=true
  if sys.main_script then
   local update=sys.main_script.on_update
   sys.main_script.on_update=function(self,dt,ts,store)
    return invoke(T.combat_before(store,dt,ts),update,self,dt,ts,store)
   end
  end
  if sys.render then
   local update=sys.render.on_update
   sys.render.on_update=function(self,dt,ts,store)
    local log=edits()
    for _,e in pairs(store.entities)do
     local f=rate(e) or 1
     if f>1 and e.render then for _,s in ipairs(e.render.sprites)do
      if attack_animation(e,s.name)then set(log,s,'fps',(s.fps or FPS or 30)*f)end
     end end
    end
    return invoke(log,update,self,dt,ts,store)
   end
  end
  local health=sys.health.on_update
  sys.health.on_update=function(self,dt,ts,store)
   local bit=require('bit');local log=edits()
   for _,e in pairs(store.entities)do
    if e.enemy and type(e.enemy.gold)=='number' and T.cfg.enemy_gold~=1 then
     set(log,e.enemy,'gold',math.floor(e.enemy.gold*T.cfg.enemy_gold+0.5))
    end
   end
   for _,d in ipairs(store.damage_queue or {})do
    local target=store.entities[d.target_id]
    if not d._kr_scaled and d.damage_applied==nil and target and not target.enemy
     and type(d.value)=='number' and d.value>0 and T.enemy_source(store,d.source_id)
     and bit.band(d.damage_type or 0,255)~=0
     and bit.band(d.damage_type or 0,256+512+1024+2048+4096+8192+16384)==0 then
      d.value=d.value*T.cfg.enemy_damage;d._kr_scaled=true
    end
   end
   return invoke(log,health,self,dt,ts,store)
  end
 end
end

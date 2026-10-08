-- Local trainer for the user's installed KR1 desktop build. No network listener.
local T = { cfg = {speed=1, gold_lock=0, lives_lock=0, cooldown=0,
    hero_damage=1, soldier_damage=1, tower_damage=1}, seq=0, message='ready',
    bonuses={}, clock=0, hud=false, counts={hero=0,soldier=0,tower=0} }
local function number(v, lo, hi)
    v=tonumber(v)
    if not v or v~=v or v<lo or v>hi then return nil end
    return v
end
local function read(name)
    if love.filesystem.exists('kr_trainer/'..name) then
        return love.filesystem.read('kr_trainer/'..name)
    end
end
local function write(name, data)
    love.filesystem.createDirectory('kr_trainer')
    assert(love.filesystem.write('kr_trainer/'..name, data))
end
local function parse(s)
    local out={}
    for k,v in (s or ''):gmatch('([%w_]+)=([^\r\n]+)') do out[k]=v end
    return out
end
local function storage() return package.loaded.storage end
local function slot_index() return storage() and storage().active_slot_idx end
local function bonus()
    local idx=slot_index()
    if not idx then return 0 end
    if T.bonuses[idx]==nil then T.bonuses[idx]=number(read('bonus_'..idx..'.txt'),0,999) or 0 end
    return T.bonuses[idx]
end
local function current_store()
    local g=package.loaded.game
    -- game.store survives a return to the map: require the live game GUI too.
    return g and g.game_gui and g.store
end
local function source_kind(id,store,seen)
    local e=store.entities[id]
    if e then return T.classify(e,store,seen) end
    return (store._kr_sources or {})[id]
end
function T.classify(e, store, seen)
    if not e or e.enemy then return nil end
    if e.hero then return 'hero' end
    if e.soldier then return 'soldier' end
    if e.tower then return 'tower' end
    seen=seen or {}
    if seen[e] then return nil end
    seen[e]=true
    local src=e.source_id or e.owner_id
    for _,key in ipairs({'bullet','modifier','aura','spawner'}) do
        local part=e[key]
        if part and (part.source_id or part.owner_id) then src=part.source_id or part.owner_id; break end
    end
    if src then
        return source_kind(src,store,seen)
    end
end
function T.scale_damage(store)
    local bit=require('bit')
    for _,d in ipairs(store.damage_queue or {}) do
        if d.damage_applied==nil and not d._kr_scaled then
            local target=store.entities[d.target_id]
            if target and target.enemy and type(d.value)=='number' and d.value>0
                and bit.band(d.damage_type or 0,255)~=0
                and bit.band(d.damage_type or 0,256+512+1024+2048+4096+8192+16384)==0 then
                local kind=source_kind(d.source_id,store)
                local factor=kind and T.cfg[kind..'_damage'] or 1
                if kind and factor~=1 then
                    d.value=d.value*factor
                    T.counts[kind]=T.counts[kind]+1
                end
            end
            d._kr_scaled=true
        end
    end
end
local function apply_locks(store)
    if T.cfg.gold_lock>0 then store.player_gold=T.cfg.gold_lock end
    if T.cfg.lives_lock>0 then store.lives=T.cfg.lives_lock end
end
function T.command(c)
    local s=current_store()
    local value=tonumber(c.value)
    if c.action=='gold' or c.action=='lives' then
        assert(s and not s.game_outcome,'enter an active level first')
        local hi=c.action=='gold' and 999999 or 10000
        assert(number(value,1,hi),'value out of range')
        s[c.action=='gold' and 'player_gold' or 'lives']=math.floor(value)
    elseif c.action=='gems' then
        local st=assert(storage(),'storage unavailable')
        assert(slot_index(),'select a save slot first')
        assert(number(value,0,999999),'value out of range')
        assert(not s,'return to the map before editing gems')
        local data=assert(st:load_slot(),'save unavailable')
        local old=data.gems
        data.gems=math.floor(value)
        local ok,saved=pcall(st.save_slot,st,data)
        if not ok or not saved then data.gems=old; error('save failed') end
        local map=package.loaded.screen_map
        if map and map.user_data then map.user_data.gems=data.gems end
        if map and map.window then map:update_gems() end
    elseif c.action=='stars' then
        local idx=assert(slot_index(),'select a save slot first')
        assert(number(value,0,999),'value out of range')
        write('bonus_'..idx..'.txt',tostring(math.floor(value)))
        T.bonuses[idx]=math.floor(value)
    elseif c.action=='reset' then
        T.cfg={speed=1,gold_lock=0,lives_lock=0,cooldown=0,hero_damage=1,soldier_damage=1,tower_damage=1}
    else error('unknown command') end
end
local bounds={speed={0.5,5},gold_lock={0,999999},lives_lock={0,10000},cooldown={0,1},
    hero_damage={0.1,100},soldier_damage={0.1,100},tower_damage={0.1,100}}
function T.poll(skip_command)
    local c=parse(read('control.txt'))
    -- Panel sequences are epoch milliseconds. A corrupt huge value must not
    -- permanently block all subsequent legitimate commands in this session.
    local seq=number(c.seq,1,math.min(9007199254740991,(os.time()+60)*1000))
    if not seq or seq~=math.floor(seq) or seq<=T.seq then return end
    for k,b in pairs(bounds) do
        local v=number(c[k],b[1],b[2])
        if v and (k~='cooldown' or v==0 or v==1) then
            T.cfg[k]=(k=='gold_lock' or k=='lives_lock') and math.floor(v) or v
        end
    end
    T.seq=seq
    T.message='ok:settings'
    if not skip_command and c.action and c.action~='none' then
        local ok,err=pcall(T.command,c)
        T.message=ok and ('ok:'..c.action) or ('error:'..tostring(err):gsub('[\r\n]',' '))
    end
end
function T.hook()
    local sim=package.loaded['klove.simulation']
    if sim and not sim._kr_hooked then
        sim._kr_hooked=true
        local update=sim.update
        sim.update=function(self,dt)
            local s=self.store
            if not s then return update(self,dt) end
            apply_locks(s)
            local speed=T.cfg.speed
            if speed==1 or s.paused then return update(self,dt) end
            local total=math.min(dt,0.25)*speed
            local step=math.min(1/120,s.tick_length/2)
            while total>0.00000001 do
                local chunk=math.min(step,total)
                update(self,chunk); total=total-chunk
            end
        end
        local insert=sim.insert_entity
        sim.insert_entity=function(self,e)
            local result=insert(self,e)
            if self.store.entities[e.id] then
                self.store._kr_sources=self.store._kr_sources or {}
                self.store._kr_sources[e.id]=T.classify(e,self.store)
            end
            return result
        end
        local init=sim.init
        sim.init=function(self,...)
            local result=init(self,...)
            self.store._kr_sources={}
            T.counts={hero=0,soldier=0,tower=0}
            return result
        end
    end
    local sys=package.loaded.systems
    if sys and not sys._kr_hooked then
        sys._kr_hooked=true
        local health=sys.health.on_update
        sys.health.on_update=function(self,dt,ts,s)
            T.scale_damage(s)
            return health(self,dt,ts,s)
        end
        local goal=sys.goal_line.on_update
        sys.goal_line.on_update=function(self,dt,ts,s)
            local result=goal(self,dt,ts,s)
            apply_locks(s)
            return result
        end
        local level=sys.level.on_update
        sys.level.on_update=function(self,dt,ts,s)
            apply_locks(s)
            return level(self,dt,ts,s)
        end
    end
    if PowerButton and not PowerButton._kr_hooked then
        PowerButton._kr_hooked=true
        local update=PowerButton.update
        PowerButton.update=function(self,dt)
            if T.cfg.cooldown==1 and self.mode=='cooldown' then self:set_mode('ready') end
            return update(self,dt)
        end
    end
    if UpgradesView and not UpgradesView._kr_hooked then
        UpgradesView._kr_hooked=true
        local check=UpgradesView.set_stars_and_check
        UpgradesView.set_stars_and_check=function(self,...)
            local map=package.loaded.screen_map
            local original=map.total_stars
            map.total_stars=original+bonus()
            local ok,result=pcall(check,self,...)
            map.total_stars=original
            if not ok then error(result) end
            return result
        end
        local update=UpgradesView.update
        UpgradesView.update=function(self,dt)
            local result=update(self,dt)
            self:set_stars_and_check()
            return result
        end
    end
end
function T.status()
    local s=current_store()
    local st=storage()
    local data=slot_index() and st:load_slot()
    local lines={'version=1','time='..os.time(),'seq='..T.seq,'message='..T.message,
        'slot='..tostring(slot_index() or 0),'in_level='..(s and 1 or 0),
        'gold='..tostring(s and s.player_gold or 0),'lives='..tostring(s and s.lives or 0),
        'gems='..tostring(data and data.gems or 0),'bonus='..bonus(),
        'tick='..tostring(s and s.tick or 0),
        'hero_hits='..T.counts.hero,'soldier_hits='..T.counts.soldier,'tower_hits='..T.counts.tower,
        'hook_sim='..tostring(package.loaded['klove.simulation'] and package.loaded['klove.simulation']._kr_hooked or false),
        'hook_health='..tostring(package.loaded.systems and package.loaded.systems._kr_hooked or false),
        'hook_cooldown='..tostring(PowerButton and PowerButton._kr_hooked or false),
        'hook_stars='..tostring(UpgradesView and UpgradesView._kr_hooked or false)}
    for k,v in pairs(T.cfg) do lines[#lines+1]=k..'='..v end
    write('status.txt',table.concat(lines,'\n'))
end
function T.install()
    local load=love.load
    love.load=function(...)
        load(...)
        -- Do not replay a previous session's one-shot command.
        T.hook(); T.poll(true); T.status()
    end
    local update=love.update
    love.update=function(dt)
        T.clock=T.clock+dt
        if T.clock>=0.2 then
            T.clock=0
            local ok,err=pcall(function() T.poll(); T.hook(); T.status() end)
            if not ok then T.message='error:'..tostring(err) end
        end
        return update(dt)
    end
    local draw=love.draw
    love.draw=function(...)
        draw(...)
        if T.hud then
            local g=love.graphics
            g.push('all'); g.origin(); g.setScissor()
            g.setColor(15,20,30,220); g.rectangle('fill',10,10,460,66)
            g.setColor(255,255,255,255)
            g.print('KR Trainer | speed '..T.cfg.speed..'x | F8 hide',20,18)
            g.print('Hero '..T.cfg.hero_damage..'x  Soldiers '..T.cfg.soldier_damage..'x  Towers '..T.cfg.tower_damage..'x',20,43)
            g.pop()
        end
    end
    local key=love.keypressed
    love.keypressed=function(k,...)
        if k=='f8' then T.hud=not T.hud; return end
        return key(k,...)
    end
    local errhand=love.errhand
    love.errhand=function(msg)
        pcall(write,'error.txt',tostring(msg)..'\n'..debug.traceback())
        return errhand(msg)
    end
    _G.KR_TRAINER=T
end
return T

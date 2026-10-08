local failures,checks={},0
local function check(name,fn)
    checks=checks+1
    local ok,err=pcall(fn)
    if not ok then failures[#failures+1]=name..': '..tostring(err) end
end
local files={}
love={filesystem={exists=function(p) return files[p]~=nil end,
    read=function(p) return files[p] end,createDirectory=function() end,
    write=function(p,v) files[p]=v;return true end}}
local function fresh()
    files={};package.loaded.game=nil;package.loaded.storage=nil;package.loaded.screen_map=nil
    return dofile('tools/kingdom_rush_trainer/runtime.lua')
end
check('stale configuration must not revert current speed',function()
    local t=fresh()
    files['kr_trainer/control.txt']='seq=20\naction=none\nspeed=3';t.poll()
    files['kr_trainer/control.txt']='seq=19\naction=none\nspeed=1';t.poll()
    assert(t.cfg.speed==3)
end)
check('configuration without valid sequence is ignored',function()
    local t=fresh()
    files['kr_trainer/control.txt']='speed=5\ncooldown=1';t.poll()
    assert(t.cfg.speed==1 and t.cfg.cooldown==0)
end)
check('gem save exception restores cached slot value',function()
    local t=fresh();local data={gems=330}
    package.loaded.storage={active_slot_idx=1,load_slot=function()return data end,
        save_slot=function()error('disk full')end}
    assert(not pcall(t.command,{action='gems',value=999}))
    assert(data.gems==330)
end)
check('live enemy overrides stale friendly source cache',function()
    local t=fresh();t.cfg.hero_damage=10
    local d={source_id=1,target_id=2,value=10,damage_type=2}
    t.scale_damage({entities={[1]={enemy={}},[2]={enemy={}}},_kr_sources={[1]='hero'},damage_queue={d}})
    assert(d.value==10)
end)
for _,flag in ipairs({256,512,1024,2048,4096,8192,16384}) do
    check('special damage bypass '..flag,function()
        local t=fresh();t.cfg.hero_damage=10
        local d={source_id=1,target_id=2,value=10,damage_type=flag+1}
        t.scale_damage({entities={[1]={hero={}},[2]={enemy={}}},damage_queue={d}})
        assert(d.value==10)
    end)
end
for _,kind in ipairs({'hero','soldier','tower'}) do
    for _,factor in ipairs({0.1,0.5,1,2,100}) do
        for _,part in ipairs({'bullet','modifier','aura','spawner'}) do
            check(kind..' '..part..' '..factor,function()
                local t=fresh();t.cfg[kind..'_damage']=factor
                local source={[kind]={}}
                local d={source_id=3,target_id=4,value=10,damage_type=2}
                local s={entities={[1]=source,[2]={[part]={source_id=1}},[3]={source_id=2},[4]={enemy={}}},damage_queue={d}}
                t.scale_damage(s);assert(math.abs(d.value-10*factor)<1e-7)
                t.scale_damage(s);assert(math.abs(d.value-10*factor)<1e-7)
            end)
        end
    end
end
check('unknown source, friendly target, and negative damage unchanged',function()
    local t=fresh();t.cfg.hero_damage=10
    local s={entities={[1]={hero={},soldier={}},[2]={enemy={}},[3]={soldier={}}},damage_queue={
        {source_id=999,target_id=2,value=10,damage_type=2},
        {source_id=1,target_id=3,value=10,damage_type=2},
        {source_id=1,target_id=2,value=-10,damage_type=2}}}
    t.scale_damage(s)
    assert(s.damage_queue[1].value==10 and s.damage_queue[2].value==10 and s.damage_queue[3].value==-10)
    assert(t.classify(s.entities[1],s)=='hero')
end)
check('one-shot failure is acknowledged and not retried',function()
    local t=fresh()
    files['kr_trainer/control.txt']='seq=50\naction=gold\nvalue=100'
    t.poll();assert(t.seq==50 and t.message:find('error:'))
    package.loaded.game={game_gui={},store={player_gold=5}}
    t.poll();assert(package.loaded.game.store.player_gold==5)
end)
check('game over forbids one-shot lives edit',function()
    local t=fresh();package.loaded.game={game_gui={},store={game_outcome='defeat',lives=0}}
    assert(not pcall(t.command,{action='lives',value=20}))
    assert(package.loaded.game.store.lives==0)
end)
check('failed stars write does not change bonus cache',function()
    local t=fresh();package.loaded.storage={active_slot_idx=1}
    local write=love.filesystem.write;love.filesystem.write=function()return false end
    local ok=pcall(t.command,{action='stars',value=99})
    love.filesystem.write=write
    assert(not ok and t.bonuses[1]==nil)
end)
check('startup applies settings without replaying one-shot action',function()
    local t=fresh();local s={player_gold=10}
    package.loaded.game={game_gui={},store=s}
    files['kr_trainer/control.txt']='seq=123\naction=gold\nvalue=999\nspeed=2'
    t.poll(true);assert(t.cfg.speed==2 and t.seq==123 and s.player_gold==10)
    t.poll();assert(s.player_gold==10)
end)
for _,value in ipairs({'-1','nan','inf','1.5','9007199254740991','9007199254740992'})do
    check('invalid sequence ignored '..value,function()
        local t=fresh();files['kr_trainer/control.txt']='seq='..value..'\nspeed=5'
        t.poll();assert(t.seq==0 and t.cfg.speed==1)
    end)
end
check('gem successful save updates current map cache',function()
    local t=fresh();local data={gems=330};local saved=0
    package.loaded.storage={active_slot_idx=1,load_slot=function()return data end,
        save_slot=function(_,d)saved=saved+1;return d==data end}
    package.loaded.screen_map={user_data={gems=330},window={},update_gems=function()end}
    t.command({action='gems',value=12345})
    assert(saved==1 and data.gems==12345 and package.loaded.screen_map.user_data.gems==12345)
end)
check('gem false return rolls back cached slot',function()
    local t=fresh();local data={gems=330}
    package.loaded.storage={active_slot_idx=1,load_slot=function()return data end,save_slot=function()return false end}
    assert(not pcall(t.command,{action='gems',value=999}))
    assert(data.gems==330)
end)
check('gem write prohibited during battle',function()
    local t=fresh();package.loaded.storage={active_slot_idx=1,load_slot=function()error('must not access save')end}
    package.loaded.game={game_gui={},store={}}
    local ok,err=pcall(t.command,{action='gems',value=999})
    assert(not ok and tostring(err):find('return to the map'))
end)
check('bonus clear and reset preserve level progress and gems',function()
    local t=fresh();local data={gems=330,levels={[1]={stars=3}}}
    package.loaded.storage={active_slot_idx=1,load_slot=function()return data end}
    t.command({action='stars',value=99});t.command({action='stars',value=0});t.command({action='reset'})
    assert(t.bonuses[1]==0 and files['kr_trainer/bonus_1.txt']=='0')
    assert(data.gems==330 and data.levels[1].stars==3)
end)
print('REGRESSION CHECKS: '..checks..', FAILED: '..#failures)
for _,f in ipairs(failures)do print('FAIL '..f)end
assert(#failures==0,'offline regressions failed')

-- B and PAYLOAD are provided by the deterministic build script.
local directory=os.getenv('APPDATA')..'\\kingdom_rush\\kr_trainer_ce\\'
local output=directory..'bridge_result.txt'
local function finish(message)
 pcall(function()
  local stream=createMemoryStream()
  stream.writeString(message)
  local ok,err=pcall(function()stream.saveToFile(output)end)
  stream.destroy()
  if not ok then error(err)end
 end)
 createTimer(100,function()closeCE()end)
end
local function recover(message)
 if B.mem then
  local called,restored,why=pcall(B.cancel)
  if not called or not restored then
   message=message..'；接口恢复未确认，请重启游戏：'..tostring(called and why or restored)
  end
 end
 finish('ERROR '..message)
end
local ok,err=pcall(function()
 local pid=nil
 for id,name in pairs(getProcesslist())do
  if name:lower()=='kingdom rush.exe' then
   assert(not pid,'检测到多个游戏进程，请只保留一个原版游戏')
   pid=id
  end
 end
 assert(pid,'请先从 Steam 启动原版 Kingdom Rush，再点击连接')
 B.start(pid)
 B.submit(PAYLOAD)
end)
if not ok then
 recover(tostring(err));return
end
local ticks=0
local timer=createTimer(nil,false);timer.Interval=50
timer.OnTimer=function()
 ticks=ticks+1
 local ok,err=pcall(function()
  local ready,result=B.poll()
  if ready~=nil then
   local detached,why=B.detach()
   assert(detached,'接口恢复失败：'..tostring(why))
   timer.Enabled=false
   finish(ready and 'READY' or ('ERROR '..tostring(result)))
  elseif ticks>300 then
   timer.Enabled=false
   recover('接入超时。正在执行的脚本不会被强制终止；请重启游戏后重试。')
  end
 end)
 if not ok then timer.Enabled=false;recover(tostring(err))end
end
timer.Enabled=true

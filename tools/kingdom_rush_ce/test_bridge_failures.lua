-- Actual CE / disposable process failure-path tests. Never shipped.
return function(B,f,directory)
 local state=0;local busy,status;local passed=0
 local function file(name)return directory..'/'..name end
 local function exists(name)local h=io.open(file(name),'r');if h then h:close();return true end end
 local function touch(name)local h=assert(io.open(file(name),'w'));h:close()end
 local function pointer(value)
  assert(autoAssemble(string.format('%X:\ndq %X',f.slot,value)))
 end
 local original=f.base+0x7A20
 return function()
  if state==0 then touch('pause');state=1
  elseif state==1 and exists('paused') then
   B.start(f.pid,f)
   B.submit("fixture_counter=fixture_counter+100;return 'should never execute'")
   assert(not B.detach(),'pending request detached as completed')
   assert(B.cancel());assert(readQword(f.slot)==original)
   os.remove(file('pause'));state=2;passed=passed+1
  elseif state==2 and not exists('paused') then
   B.start(f.pid,f);B.submit('return tostring(fixture_counter)');state=3
  elseif state==3 then
   local ok,value=B.poll();if ok==nil then return end
   assert(ok and value=='1','cancelled request was replayed');assert(B.detach())
   passed=passed+1
   B.start(f.pid,f)
   B.submit("local ffi=require('ffi');ffi.cdef[[void Sleep(unsigned long);]];ffi.C.Sleep(800);return 'long payload returned'")
   busy,status=B.busy,B.status;state=4
  elseif state==4 and readInteger(busy)==1 then
   assert(B.cancel());assert(readQword(f.slot)==original)
   state=5;passed=passed+1
  elseif state==5 and readInteger(busy)==0 then
   assert(readInteger(status)==2,'running payload could not return safely')
   local aa=autoAssemble
   autoAssemble=function(code,...)
    local ok,info=aa(code,...)
    if code:find('[ENABLE]',1,true) and ok then return false,'simulated post-publication error' end
    return ok,info
   end
   local ok,err=pcall(B.start,f.pid,f);autoAssemble=aa
   assert(not ok and tostring(err):find('simulated',1,true))
   assert(B.mem and readQword(f.slot)==B.mem,'published allocation lost')
   assert(B.cancel());assert(readQword(f.slot)==original)
   state=6;passed=passed+1
  elseif state==6 then
   B.start(f.pid,f)
   -- A second valid forwarding stub represents another tool owning the slot.
   local other=assert(allocateMemory(4096))
   assert(autoAssemble(string.format('%X:\nmov rax,%X\njmp rax',other,original)))
   pointer(other)
   assert(not B.cancel(),'overwrote another tool interface')
   assert(readQword(f.slot)==other)
   pointer(original);assert(B.cancel())
   state=7;passed=passed+1
  elseif state==7 then
   B.start(f.pid,f)
   assert(not pcall(B.submit,string.rep('x',65536)),'oversize request accepted')
   assert(readInteger(B.request)==0);assert(B.detach())
   passed=passed+1
   assert(passed==6)
   return true
  end
  return false
 end
end

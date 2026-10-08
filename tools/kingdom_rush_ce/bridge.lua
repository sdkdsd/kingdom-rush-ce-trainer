-- CE 7.6 backend. Patches one checked LÖVE IAT slot, never game files.
local B={}
local EXPECTED={
 ['kingdom rush.exe']='5472c2cceaf3e285143f730e04bf88e5',
 ['love.dll']='aafedf4301ac1cde8fdd17bff7996382',
 ['lua51.dll']='9b80f16e1797b5d56d3756ef29ccf5f6'}
local function hex(n)return string.format('%X',n)end
local function bytes64(n)
 local t={};for i=1,8 do t[i]=string.format('%02X',n%256);n=n//256 end
 return table.concat(t,' ')
end
function B.validate(pid)
 local names=getProcesslist()
 assert(names[pid] and names[pid]:lower()=='kingdom rush.exe','请选择原版 Kingdom Rush.exe 进程')
 local modules={}
 for _,m in ipairs(enumModules(pid))do modules[m.Name:lower()]=m end
 for name,hash in pairs(EXPECTED)do
  local m=assert(modules[name],'缺少模块 '..name)
  assert(m.Is64Bit,'只支持 64 位版本')
  local actual=md5file(m.PathToFile)
  assert(type(actual)=='string' and actual:lower()==hash,'版本不匹配或文件无法读取：'..name..'。停止写入。')
 end
 return modules['love.dll'].Address+0x1D3048,modules['lua51.dll'].Address
end
function B.start(pid,fixture)
 assert(not B.mem,'接入已经开始')
 local slot,base
 if fixture then
  -- Only called by the repository's explicitly supplied offline test harness.
  assert(fixture.pid==pid and fixture.name=='KR_CE_OFFLINE_FIXTURE')
  slot,base=fixture.slot,fixture.base
 else slot,base=B.validate(pid) end
 assert(openProcess(pid)~=false,'无法打开进程')
 assert(targetIs64Bit(),'目标进程必须为 64 位')
 local orig=base+0x7A20
 assert(readQword(slot)==orig,'接口已被其他工具修改；请关闭其他修改工具并重启游戏')
 local signature=readBytes(orig,13,true)
 local expected={0x48,0x8b,0x41,0x18,0x48,0x2b,0x41,0x10,0x48,0xc1,0xf8,0x03,0xc3}
 for i,v in ipairs(expected)do assert(signature and signature[i]==v,'LuaJIT 接口签名不匹配')end
 local mem=assert(allocateMemory(0x13000),'分配内存失败')
 B.mem=mem;B.slot=slot;B.orig=orig;B.pid=pid
 B.request=mem+0x800;B.busy=mem+0x804;B.status=mem+0x808;B.length=mem+0x80C
 B.payload=mem+0x1000;B.result=mem+0x11000
 local a=string.format([[
%s:
push rbx
push rsi
push rdi
sub rsp,20
mov rbx,rcx
mov rdi,%s
mov eax,1
xchg eax,[rdi+4]
test eax,eax
jne kr_return
cmp dword ptr [rdi],1
jne kr_release
mov rax,%s
call rax
mov esi,eax
mov rcx,rbx
mov rdx,%s
mov r8d,[rdi+C]
mov r9,%s
mov rax,%s
call rax
test eax,eax
jne kr_error
mov rcx,rbx
xor edx,edx
mov r8d,1
xor r9d,r9d
mov rax,%s
call rax
test eax,eax
jne kr_error
mov dword ptr [rdi+8],2
jmp kr_copy
kr_error:
mov dword ptr [rdi+8],3
kr_copy:
mov rcx,rbx
mov edx,FFFFFFFF
xor r8d,r8d
mov rax,%s
call rax
mov rdx,%s
xor ecx,ecx
test rax,rax
je kr_copy_end
kr_copy_loop:
mov r8b,[rax+rcx]
test r8b,r8b
je kr_copy_end
mov [rdx+rcx],r8b
inc ecx
cmp ecx,7FE
jb kr_copy_loop
kr_copy_end:
mov byte ptr [rdx+rcx],0
mov rcx,rbx
mov edx,esi
mov rax,%s
call rax
mov dword ptr [rdi],0
kr_release:
mov dword ptr [rdi+4],0
kr_return:
mov rcx,rbx
add rsp,20
pop rdi
pop rsi
pop rbx
mov rax,%s
jmp rax
]],hex(mem),hex(B.request),hex(orig),hex(B.payload),hex(mem+0x900),hex(base+0x316D0),
 hex(base+0x7E40),hex(base+0x8B20),hex(B.result),hex(base+0x8940),hex(orig))
 local labels='label(kr_return)\nlabel(kr_release)\nlabel(kr_error)\nlabel(kr_copy)\nlabel(kr_copy_loop)\nlabel(kr_copy_end)\n'
 local ok,err=autoAssemble(labels..a)
 if not ok then deAlloc(mem);B.mem=nil;error('汇编失败：'..tostring(err))end
 if not writeString(mem+0x900,'@KR_CE_Bridge') then
  deAlloc(mem);B.mem=nil;error('写入脚本名称失败')
 end
 B.patch=string.format('[ENABLE]\nassert(%s,%s)\n%s:\ndq %s\n[DISABLE]\nassert(%s,%s)\n%s:\ndq %s',
  hex(slot),bytes64(orig),hex(slot),hex(mem),hex(slot),bytes64(mem),hex(slot),hex(orig))
 local patched,info=autoAssemble(B.patch)
 if not patched then
  -- An assembler failure is not proof that the pointer was never published.
  -- Keep executable memory alive if publication cannot be ruled out.
  error('接口写入失败：'..tostring(info))
 end
 B.disableInfo=info
 assert(readQword(slot)==mem,'接口读回验证失败')
end
function B.submit(code)
 assert(B.mem,'尚未连接')
 assert(#code<0x10000,'脚本超出容量')
 assert(readInteger(B.request)==0 and readInteger(B.busy)==0,'上一条脚本仍在执行')
 local data={code:byte(1,#code)}
 assert(writeBytes(B.payload,data),'写入脚本失败')
 assert(writeInteger(B.length,#code),'写入脚本长度失败')
 assert(writeInteger(B.status,0),'写入状态失败')
 assert(writeInteger(B.request,1),'发送请求失败')
end
function B.poll()
 if not B.mem or readInteger(B.request)~=0 or readInteger(B.busy)~=0 then return nil end
 local status=readInteger(B.status)
 if status~=2 and status~=3 then return nil end
 return status==2,readString(B.result,2047,false) or ''
end
local function restore()
 if not B.mem then return true end
 -- The allocation stays alive until process exit, so an in-flight return can
 -- never execute freed code. Only the IAT pointer is restored.
 local pointer=readQword(B.slot)
 if pointer~=B.orig then
  if pointer~=B.mem then return false,'接口被其他工具修改或目标已退出，不能覆盖' end
  local script=string.format('assert(%s,%s)\n%s:\ndq %s',
   hex(B.slot),bytes64(B.mem),hex(B.slot),hex(B.orig))
  local ok,err=autoAssemble(script)
  if not ok then return false,tostring(err)end
 end
 if readQword(B.slot)~=B.orig then return false,'接口恢复验证失败'end
 B.mem=nil
 return true
end
function B.detach()
 if not B.mem then return true end
 if readInteger(B.request)~=0 or readInteger(B.busy)~=0 then return false,'请求尚未完成，不能断开' end
 return restore()
end
function B.cancel()
 if not B.mem then return true end
 -- Cancel an unconsumed request; a running payload is never killed. Restoring
 -- the IAT while busy is safe because the allocation remains until target exit.
 local cancelled=writeInteger(B.request,0)
 local restored,why=restore()
 if not restored then return false,why end
 if not cancelled then return false,'接口已恢复，但未能取消请求；请重启游戏' end
 return true
end
return B

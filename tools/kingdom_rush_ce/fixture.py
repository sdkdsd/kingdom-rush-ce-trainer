"""Own isolated LuaJIT process. Not the game; no game executable is launched."""
import ctypes, json, os, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]
OUT=WORK/'analysis/kingdom-rush/ce-fixture'
OUT.mkdir(parents=True,exist_ok=True)
folder=Path(os.environ['KR_GAME_DIR'])
cookie=os.add_dll_directory(str(folder))
l=ctypes.CDLL(str(folder/'lua51.dll'))
for name,args,restype in [
 ('luaL_newstate',[],ctypes.c_void_p),('luaL_openlibs',[ctypes.c_void_p],None),
 ('luaL_loadstring',[ctypes.c_void_p,ctypes.c_char_p],ctypes.c_int),
 ('lua_pcall',[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int],ctypes.c_int),
 ('lua_gettop',[ctypes.c_void_p],ctypes.c_int),('lua_pushinteger',[ctypes.c_void_p,ctypes.c_longlong],None),
 ('lua_tointeger',[ctypes.c_void_p,ctypes.c_int],ctypes.c_longlong),('lua_close',[ctypes.c_void_p],None)]:
 f=getattr(l,name);f.argtypes=args;f.restype=restype
state=l.luaL_newstate();l.luaL_openlibs(state)
mock=b'''main={handler={}};local files={};love={
 filesystem={exists=function(p)return files[p]~=nil end,read=function(p)return files[p]end,
 write=function(p,v)files[p]=v;return true end,createDirectory=function()return true end},
 load=function()end,update=function()end,draw=function()end,keypressed=function()end,errhand=function()end}
package.loaded.storage={load_slot=function()return nil end}
fixture_counter=0
'''
assert l.luaL_loadstring(state,mock)==0 and l.lua_pcall(state,0,0,0)==0
l.lua_pushinteger(state,42)
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.c_ulong];k.VirtualAlloc.restype=ctypes.c_void_p
k.VirtualProtect.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong)]
slot=k.VirtualAlloc(None,4096,0x3000,0x04)
original=ctypes.cast(l.lua_gettop,ctypes.c_void_p).value
ctypes.c_void_p.from_address(slot).value=original
old=ctypes.c_ulong();assert k.VirtualProtect(slot,4096,0x02,ctypes.byref(old))
meta=dict(name='KR_CE_OFFLINE_FIXTURE',pid=os.getpid(),slot=slot,base=original-0x7a20)
(OUT/'fixture.json').write_text(json.dumps(meta))
Call=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p)
calls=0;deadline=time.monotonic()+60
while time.monotonic()<deadline and not (OUT/'stop').exists():
 if (OUT/'pause').exists():
  (OUT/'paused').touch();time.sleep(.005);continue
 if (OUT/'paused').exists():(OUT/'paused').unlink()
 pointer=ctypes.c_void_p.from_address(slot).value
 assert Call(pointer)(state)==1,'Lua stack top changed'
 assert l.lua_tointeger(state,1)==42,'Lua stack argument corrupted'
 calls+=1;time.sleep(.005)
(OUT/'fixture-result.json').write_text(json.dumps(dict(calls=calls,stack_preserved=True,pointer_restored=ctypes.c_void_p.from_address(slot).value==original)))
l.lua_close(state)

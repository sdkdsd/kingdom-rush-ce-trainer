"""Run validation regression tests in CE's Lua 5.3 DLL, without CE or game processes."""
import ctypes,sys
from pathlib import Path
import build
from run_bridge_test import literal
bridge=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else build.HERE/'bridge.lua'
lua=ctypes.CDLL(str(build.CE/'lua53-64.dll'))
for name,args,result in (
 ('luaL_newstate',[],ctypes.c_void_p),('luaL_openlibs',[ctypes.c_void_p],None),
 ('luaL_loadstring',[ctypes.c_void_p,ctypes.c_char_p],ctypes.c_int),
 ('lua_pcallk',[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_longlong,ctypes.c_void_p],ctypes.c_int),
 ('lua_tolstring',[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p],ctypes.c_char_p),('lua_close',[ctypes.c_void_p],None)):
 f=getattr(lua,name);f.argtypes=args;f.restype=result
state=lua.luaL_newstate();lua.luaL_openlibs(state)
try:
 code='local checks=dofile('+literal((build.HERE/'test_bridge_validation.lua').as_posix())+')(function()return dofile('+literal(bridge.as_posix())+')end);return tostring(checks)'
 assert lua.luaL_loadstring(state,code.encode('utf8'))==0
 status=lua.lua_pcallk(state,0,1,0,0,None)
 message=lua.lua_tolstring(state,-1,None).decode('utf8')
 if status:raise AssertionError(message)
 print('BRIDGE VALIDATION CHECKS PASS:',message)
finally:lua.lua_close(state)

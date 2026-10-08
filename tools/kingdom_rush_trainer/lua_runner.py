"""Run a Lua test using the game's own LuaJIT 2.0.4 DLL, without launching the game."""
import ctypes
import os
from pathlib import Path
import sys

def run(code):
    folder=os.environ['KR_GAME_DIR']
    cookie=os.add_dll_directory(folder)
    lua=ctypes.CDLL(folder+r'\lua51.dll')
    lua.luaL_newstate.restype=ctypes.c_void_p
    lua.luaL_openlibs.argtypes=[ctypes.c_void_p]
    lua.luaL_loadbuffer.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_size_t,ctypes.c_char_p]
    lua.lua_pcall.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int]
    lua.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p]
    lua.lua_tolstring.restype=ctypes.c_char_p
    lua.lua_close.argtypes=[ctypes.c_void_p]
    state=lua.luaL_newstate();lua.luaL_openlibs(state)
    try:
        code=code.encode('utf8') if isinstance(code,str) else code
        error=lua.luaL_loadbuffer(state,code,len(code),b'@trainer_test') or lua.lua_pcall(state,0,0,0)
        if error:raise RuntimeError(lua.lua_tolstring(state,-1,None).decode('utf8',errors='replace'))
    finally:lua.lua_close(state);cookie.close()

if __name__=='__main__':run(Path(sys.argv[1]).read_bytes())

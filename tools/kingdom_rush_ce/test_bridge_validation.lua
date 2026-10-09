-- Validation-only contract tests; no actual process or memory access.
return function(factory)
 local saved={getProcesslist=getProcesslist,enumModules=enumModules,md5file=md5file,fileExists=fileExists,ansiToUtf8=ansiToUtf8}
 local entries,hashes,exists,calls,enumeration_error;local checks=0
 local ansi=string.char(0xD6,0xD0)..'/love.dll'
 local unicode='中文/love.dll'
 local function check(value,message)assert(value,message);checks=checks+1 end
 local function reset()
  entries={{Name='Kingdom Rush.exe',Is64Bit=true,PathToFile='exe',Address=0x100000},
   {Name='love.dll',Is64Bit=true,PathToFile='love',Address=0x200000},
   {Name='lua51.dll',Is64Bit=true,PathToFile='lua',Address=0x300000}}
  hashes={exe='5472c2cceaf3e285143f730e04bf88e5',love='aafedf4301ac1cde8fdd17bff7996382',lua='9b80f16e1797b5d56d3756ef29ccf5f6'}
  exists={exe=true,love=true,lua=true};calls={};enumeration_error=nil
 end
 getProcesslist=function()return {[123]='Kingdom Rush.exe'}end
 enumModules=function(id)assert(id==123);if enumeration_error then error(enumeration_error)end;return entries end
 fileExists=function(path)return exists[path] or false end
 ansiToUtf8=function(path)if path==ansi then return unicode end;return path end
 md5file=function(path)assert(exists[path],'hashing a nonexistent path');calls[path]=true;return hashes[path]end
 local function run(label,prepare,expected)
  reset();prepare();local B=factory();local ok,a,b=pcall(B.validate,123)
  if expected then check(not ok and tostring(a):find(expected,1,true),label..': '..tostring(a))
  else check(ok,label..': '..tostring(a));check(a==0x200000+0x1D3048 and b==0x300000,label..': wrong addresses')end
  return B
 end
 local ok,err=pcall(function()
  run('missing-love',function()table.remove(entries,2)end,'未识别到模块 love.dll')
  run('empty-list',function()entries={}end,'未读取到任何游戏模块')
  run('enumeration-error',function()enumeration_error='access denied'end,'无法读取游戏模块列表')
  run('nil-list',function()entries=nil end,'无法读取游戏模块列表')
  local B=run('normal',function()end)
  check(table.concat(B.diagnostics,'\n'):find('module_count=3',1,true),'missing module count')
  check(table.concat(B.diagnostics,'\n'):find('path=exe',1,true),'missing process path')
  run('upper-case',function()for _,m in ipairs(entries)do m.Name=m.Name:upper()end end)
  run('ansi-path',function()entries[2].PathToFile=ansi;exists[unicode]=true;hashes[unicode]=hashes.love end)
  check(calls[unicode] and not calls[ansi],'ANSI path was not normalized for hashing')
  run('utf8-path',function()entries[2].PathToFile=unicode;exists[unicode]=true;hashes[unicode]=hashes.love end)
  check(calls[unicode],'UTF-8 path was not preserved')
  run('missing-file',function()exists.love=false end,'无法读取模块文件路径')
  check(not calls.love,'nonexistent file sent to md5file')
  run('wrong-hash',function()hashes.love='wrong'end,'版本不匹配或文件无法读取：love.dll')
  run('32-bit',function()entries[1].Is64Bit=false end,'只支持 64 位版本')
 end)
 for name,value in pairs(saved)do _G[name]=value end
 if not ok then error(err)end
 return checks
end

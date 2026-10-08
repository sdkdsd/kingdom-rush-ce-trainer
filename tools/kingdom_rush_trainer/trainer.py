"""Chinese local control panel. Standard library only; no remote access."""
from pathlib import Path
import datetime as dt
import json
import math
import os
import re
import subprocess
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

ROOT = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
SAVE = Path(os.environ['APPDATA']) / 'kingdom_rush'
CONTROL = SAVE / 'kr_trainer'
DEFAULTS = dict(speed=1, gold_lock=0, lives_lock=0, cooldown=0,
                hero_damage=1, soldier_damage=1, tower_damage=1)
LIMITS = dict(speed=(0.5,5), gold_lock=(0,999999), lives_lock=(0,10000), cooldown=(0,1),
              hero_damage=(0.1,100), soldier_damage=(0.1,100), tower_damage=(0.1,100))
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

def read_status():
    try:
        return dict(line.split('=', 1) for line in (CONTROL/'status.txt').read_text(encoding='utf8').splitlines() if '=' in line)
    except (OSError, ValueError, UnicodeError):
        return {}

def status_number(s,key,default=0):
    try:
        value=float(s.get(key,default))
        return value if math.isfinite(value) else default
    except (TypeError,ValueError):
        return default

def is_connected(s):
    age=time.time()-status_number(s,'time')
    return 0<=age<4

def game_running():
    result = subprocess.run(['tasklist.exe', '/FI', 'IMAGENAME eq Kingdom Rush.exe', '/FO', 'CSV', '/NH'],
                            capture_output=True, creationflags=NO_WINDOW)
    return b'Kingdom Rush.exe' in result.stdout

def backup():
    target = ROOT/'backups'/dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    target.mkdir(parents=True)
    paths=list(SAVE.glob('*.lua')) + list(CONTROL.glob('bonus_*.txt'))
    manifest=[]
    for p in paths:
        rel=p.relative_to(SAVE)
        data=p.read_bytes()
        if data!=p.read_bytes():
            raise RuntimeError('存档正在写入，请稍后重试。')
        dest=target/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
        manifest.append(str(rel))
    # A snapshot from before extra stars existed must also restore zero bonus.
    for idx in (1,2,3):
        rel=Path('kr_trainer')/f'bonus_{idx}.txt'
        if str(rel) not in manifest:
            (target/rel).parent.mkdir(parents=True,exist_ok=True)
            (target/rel).write_text('0',encoding='utf8')
            manifest.append(str(rel))
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    return target

def restore(folder):
    if game_running():
        raise RuntimeError('请先退出游戏，再恢复存档。')
    folder=Path(folder).resolve()
    files=json.loads((folder/'manifest.json').read_text(encoding='utf8'))
    if not isinstance(files,list) or not files or any(not isinstance(n,str) for n in files):
        raise ValueError('备份清单格式无效。')
    if len(files)!=len(set(files)):raise ValueError('备份清单包含重复路径。')
    checked=[]
    for name in files:
        rel=Path(name)
        allowed_save=rel.parent==Path('.') and (rel.name in ('settings.lua','global.lua') or re.fullmatch(r'slot_[0-9]+\.lua',rel.name))
        allowed_bonus=rel.parent==Path('kr_trainer') and re.fullmatch(r'bonus_[0-9]+\.txt',rel.name)
        if rel.is_absolute() or '..' in rel.parts or not (allowed_save or allowed_bonus):
            raise ValueError('备份清单包含无效路径。')
        src=(folder/rel).resolve()
        if not src.is_relative_to(folder): raise ValueError('备份路径无效。')
        checked.append((SAVE/rel,src.read_bytes()))
    safety=backup()
    for dest,data in checked:
        dest.parent.mkdir(parents=True,exist_ok=True)
        tmp=dest.with_suffix(dest.suffix+'.restore.tmp')
        tmp.write_bytes(data)
        tmp.replace(dest)
    return safety

class Panel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Kingdom Rush · 本地修改器 1.1')
        self.geometry('820x740')
        self.minsize(780,700)
        self.configure(bg='#f4f6fa')
        style=ttk.Style(self)
        style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',10))
        style.configure('TFrame',background='#f4f6fa')
        style.configure('TLabel',background='#f4f6fa')
        style.configure('TLabelframe',background='#f4f6fa')
        style.configure('TLabelframe.Label',background='#f4f6fa',font=('Microsoft YaHei UI',11,'bold'))
        style.configure('TButton',padding=(10,7))
        self.cfg=DEFAULTS.copy()
        self.seq=int(time.time()*1000)
        self.pending=None
        self.vars={}
        self.status_var=tk.StringVar(value='未连接 · 请用下方按钮启动修改版游戏')
        self.note=tk.StringVar(value='启动会自动备份存档。原版 Steam 安装文件保持原样。')
        outer=ttk.Frame(self,padding=20);outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='KINGDOM RUSH',font=('Segoe UI',21,'bold')).pack(anchor='w')
        ttk.Label(outer,text='金币 · 生命 · 速度 · 升级星星 · 钻石 · 战斗伤害',foreground='#596579').pack(anchor='w',pady=(0,12))
        bar=ttk.Frame(outer);bar.pack(fill='x')
        ttk.Button(bar,text='启动修改版游戏',command=self.launch).pack(side='left')
        ttk.Button(bar,text='备份存档',command=self.make_backup).pack(side='left',padx=8)
        ttk.Button(bar,text='恢复备份…',command=self.restore_ui).pack(side='left')
        ttk.Label(outer,textvariable=self.status_var,foreground='#1f658b',wraplength=750).pack(anchor='w',pady=12)
        book=ttk.Notebook(outer);book.pack(fill='both',expand=True)
        battle=ttk.Frame(book,padding=16);profile=ttk.Frame(book,padding=16)
        book.add(battle,text='  关卡与战斗  ');book.add(profile,text='  星星、钻石与说明  ')
        self.make_value(battle,0,'关卡金币','gold','1000',1,999999)
        self.make_value(battle,1,'基地生命','lives','20',1,10000)
        self.lock_gold=tk.BooleanVar();self.lock_lives=tk.BooleanVar()
        ttk.Checkbutton(battle,text='锁定金币为上方数值',variable=self.lock_gold,command=self.apply).grid(row=2,column=0,columnspan=2,sticky='w',pady=7)
        ttk.Checkbutton(battle,text='锁定基地生命为上方数值',variable=self.lock_lives,command=self.apply).grid(row=2,column=2,columnspan=2,sticky='w',pady=7)
        self.make_factor(battle,3,'游戏速度','speed',('0.5','1','2','3','5'))
        self.cooldown=tk.BooleanVar()
        ttk.Checkbutton(battle,text='火雨／援军技能立即冷却',variable=self.cooldown,command=self.apply).grid(row=4,column=0,columnspan=4,sticky='w',pady=8)
        ttk.Separator(battle).grid(row=5,column=0,columnspan=4,sticky='ew',pady=10)
        self.make_factor(battle,6,'英雄伤害倍率','hero_damage',('0.5','1','2','5','10','100'))
        self.make_factor(battle,7,'兵营／友方士兵伤害倍率','soldier_damage',('0.5','1','2','5','10','100'))
        self.make_factor(battle,8,'其他防御塔伤害倍率','tower_damage',('0.5','1','2','5','10','100'))
        ttk.Label(battle,text='伤害仅对敌人生效；倍率作用于伤害结算，面板基础攻击数值保持原值。\n士兵包含援军；英雄独立计算。无来源标记的特殊伤害暂不放大。',foreground='#596579',wraplength=690).grid(row=9,column=0,columnspan=4,sticky='w',pady=12)
        ttk.Button(battle,text='应用速度／锁定／伤害设置',command=self.apply).grid(row=10,column=0,columnspan=2,sticky='w')
        ttk.Button(battle,text='关闭全部临时效果',command=self.reset).grid(row=10,column=2,columnspan=2,sticky='e')
        self.make_value(profile,0,'额外升级星星（当前存档）','stars','99',0,999)
        self.make_value(profile,1,'商店钻石（返回地图后）','gems','9999',0,999999)
        text=('星星采用额外升级点：在升级树中可用，不修改关卡星级或通关记录。\n'
              '额外星星按存档保存，只有修改版会读取。设置为 0 可取消额外点数。\n'
              '已购买的升级和修改后的钻石会保存；关闭临时效果不会回滚它们。\n\n'
              '操作顺序：启动修改版 → 选择存档 → 进入地图／关卡 → 应用设置。\n'
              'F8：显示／隐藏游戏内英文状态条。面板可随时切回修改。\n'
              '速度和战斗效果每次启动默认关闭；关闭面板也会恢复普通倍率。\n\n'
              '恢复备份前请退出游戏。恢复前会再备份一次当前存档。\n'
              '备份只恢复清单里的文件，之后新建的其他存档不会删除。\n'
              'Steam 云存档可能同步持久修改；需要回退时使用本地备份。\n\n'
              '适配版本：Steam Build 24662480。游戏更新后应重新检查兼容性。')
        ttk.Label(profile,text=text,justify='left',wraplength=710).grid(row=2,column=0,columnspan=4,sticky='nw',pady=20)
        for frame in (battle,profile): frame.columnconfigure(0,weight=1)
        ttk.Label(outer,textvariable=self.note,wraplength=760,foreground='#596579').pack(anchor='w',pady=(12,0))
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.after(400,self.refresh)

    def make_value(self,parent,row,label,key,default,lo,hi):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',pady=9)
        var=tk.StringVar(value=default);self.vars[key]=var
        ttk.Entry(parent,textvariable=var,width=12).grid(row=row,column=1,padx=10)
        ttk.Button(parent,text='设置',command=lambda:self.set_value(key,lo,hi)).grid(row=row,column=2,padx=5)
        if key=='gold':ttk.Button(parent,text='+1000',command=self.add_gold).grid(row=row,column=3)

    def make_factor(self,parent,row,label,key,values):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',pady=8)
        var=tk.StringVar(value='1');self.vars[key]=var
        box=ttk.Combobox(parent,textvariable=var,values=values,width=10)
        box.grid(row=row,column=1,padx=10)
        ttk.Label(parent,text='倍').grid(row=row,column=2,sticky='w')

    def send(self,action='none',value=0):
        if action!='reset' and self.pending and self.pending[2] not in ('none','reset'):
            s=read_status()
            if not is_connected(s) or status_number(s,'seq')<self.pending[0]:
                raise RuntimeError('上一条数值修改尚未确认，请等待，或先关闭全部临时效果取消待处理操作。')
        CONTROL.mkdir(parents=True,exist_ok=True)
        self.seq=max(self.seq+1,int(time.time()*1000))
        data=dict(self.cfg,seq=self.seq,action=action,value=value)
        temp=CONTROL/'control.tmp'
        temp.write_text(''.join(f'{k}={v}\n' for k,v in data.items()),encoding='utf8')
        temp.replace(CONTROL/'control.txt')
        self.pending=(self.seq,time.time(),action)

    def apply(self):
        try:
            cfg=DEFAULTS.copy()
            for key in ('speed','hero_damage','soldier_damage','tower_damage'):
                v=float(self.vars[key].get());lo,hi=LIMITS[key]
                if not lo<=v<=hi:raise ValueError(f'{key} 范围为 {lo}–{hi}')
                cfg[key]=v
            cfg['gold_lock']=int(self.vars['gold'].get()) if self.lock_gold.get() else 0
            cfg['lives_lock']=int(self.vars['lives'].get()) if self.lock_lives.get() else 0
            for key in ('gold_lock','lives_lock'):
                if not LIMITS[key][0]<=cfg[key]<=LIMITS[key][1]:raise ValueError('锁定数值超出范围')
            cfg['cooldown']=int(self.cooldown.get())
            previous=self.cfg;self.cfg=cfg
            try:self.send()
            except (OSError,RuntimeError):self.cfg=previous;raise
            self.note.set('设置已发送，等待游戏确认。')
        except (ValueError,OSError,RuntimeError) as e:messagebox.showerror('设置失败',str(e))

    def connected(self):
        s=read_status()
        return is_connected(s)

    def set_value(self,key,lo,hi):
        try:
            if not self.connected():raise ValueError('请先启动修改版游戏并选择存档。')
            if self.pending and time.time()-self.pending[1]<2:raise ValueError('上一条操作等待确认，请稍后再试。')
            val=int(self.vars[key].get())
            if not lo<=val<=hi:raise ValueError(f'请输入 {lo}–{hi} 的整数。')
            if key in ('gems','stars'):backup()
            self.send(key,val)
            self.note.set('操作已发送，等待游戏确认。')
        except (ValueError,OSError,RuntimeError) as e:messagebox.showerror('操作失败',str(e))

    def add_gold(self):
        self.vars['gold'].set(str(min(999999,int(status_number(read_status(),'gold'))+1000)))
        self.set_value('gold',1,999999)

    def reset(self,strict=False):
        self.cfg=DEFAULTS.copy()
        for key in ('speed','hero_damage','soldier_damage','tower_damage'):self.vars[key].set('1')
        self.lock_gold.set(False);self.lock_lives.set(False);self.cooldown.set(False)
        try:self.send('reset');self.note.set('临时效果已关闭；星星、钻石和已购买升级保留。')
        except OSError as e:
            if strict:raise
            messagebox.showerror('写入失败',str(e))

    def launch(self):
        try:
            if game_running():raise RuntimeError('游戏已经运行。请先退出，再用本按钮启动修改版。')
            exe=ROOT/'game'/'Kingdom Rush.exe'
            if not exe.is_file():raise RuntimeError('缺少修改版游戏文件，请重新构建。')
            folder=backup()
            self.reset(strict=True)
            for name in ('status.txt','error.txt'):
                p=CONTROL/name
                if p.exists():p.unlink()
            env=os.environ.copy();env['SteamAppId']='246420'
            subprocess.Popen([str(exe)],cwd=exe.parent,env=env)
            self.note.set(f'已启动；备份：{folder.name}')
        except (OSError,RuntimeError) as e:messagebox.showerror('启动失败',str(e))

    def make_backup(self):
        try:self.note.set(f'备份完成：{backup()}')
        except (OSError,RuntimeError) as e:messagebox.showerror('备份失败',str(e))

    def restore_ui(self):
        folder=filedialog.askdirectory(title='选择含 manifest.json 的备份文件夹',initialdir=ROOT/'backups')
        if not folder:return
        if not messagebox.askyesno('恢复备份','恢复此备份中的存档文件？恢复前会自动备份当前文件。'):return
        try:self.note.set(f'恢复完成。恢复前的备份：{restore(folder).name}')
        except (OSError,ValueError,RuntimeError) as e:messagebox.showerror('恢复失败',str(e))

    def refresh(self):
        s=read_status()
        if is_connected(s):
            where='关卡中' if s.get('in_level')=='1' else '菜单／地图'
            self.status_var.set(f"已连接 · 存档 {s.get('slot','0')} · {where}   金币 {s.get('gold','0')} / 生命 {s.get('lives','0')}\n钻石 {s.get('gems','0')} / 额外升级星星 {s.get('bonus','0')} · 倍率 {s.get('speed','1')}×")
            if self.pending and status_number(s,'seq')>=self.pending[0]:
                msg=s.get('message','')
                self.note.set(('操作失败：'+msg) if msg.startswith('error:') else ('游戏已确认设置。' if self.pending[2]=='none' else ('游戏已确认：'+msg)))
                self.pending=None
        else:
            self.status_var.set('未连接 · 请使用本面板启动修改版游戏')
        if self.pending and time.time()-self.pending[1]>5:
            self.note.set('尚未收到游戏确认；请检查是否启动修改版、是否停在错误画面。')
            # Keep the command protected until acknowledged or explicitly cancelled.
        self.after(500,self.refresh)

    def close(self):
        self.reset()
        self.destroy()

if __name__=='__main__':
    # One panel owns the local command channel.
    import ctypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
    mutex=kernel.CreateMutexW(None,False,'Local\\KingdomRushTrainerPanel')
    if ctypes.get_last_error()==183:
        messagebox.showinfo('修改器','修改器已经打开。')
    else:
        Panel().mainloop()

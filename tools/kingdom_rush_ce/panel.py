"""Standalone front end; CE performs the checked in-memory attachment."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import panel_base as base

BUNDLE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
COMPONENTS={'cheatengine-x86_64.exe','lua53-64.dll','defines.lua','main.lua','attach.CETRAINER'}
VERSION='2.1 RC1'
CONFIRM_PHRASE='我确认解锁全部成就'

def verify_components():
    manifest=json.loads((BUNDLE/'ce/manifest.json').read_text(encoding='utf8'))
    if not isinstance(manifest,dict) or set(manifest)!=COMPONENTS:
        raise ValueError('接入组件清单不完整或格式损坏。')
    for name,expected in manifest.items():
        if not isinstance(expected,str) or len(expected)!=64:
            raise ValueError('接入组件哈希格式损坏：'+name)
        with (BUNDLE/'ce'/name).open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
        if actual!=expected:raise ValueError('接入组件校验失败：'+name)

class CEPanel(base.Panel):
    def make_value(self,parent,row,label,key,default,lo,hi):
        if key=='gems':
            self.vars[key]=tk.StringVar(value=default)
            return
        return super().make_value(parent,row,label,key,default,lo,hi)

    def __init__(self):
        self.backend=None
        self.backend_started=0
        self.hotkey_down=set()
        self.pending_ce_note=None
        super().__init__()
        self.title('Kingdom Rush · CE 修改器 '+VERSION)
        self.note.set('先从 Steam 启动原版游戏，再点击连接。当前为离线验证候选版。')
        def children(w):
            for c in w.winfo_children():
                yield c
                yield from children(c)
        for widget in children(self):
            try:text=str(widget.cget('text'))
            except tk.TclError:continue
            if text=='启动修改版游戏':widget.configure(text='连接原版游戏')
            elif text.startswith('星星采用额外升级点：'):
                profile=widget.master
                ttk.Button(profile,text='一键解锁全部英雄（当前存档）',command=self.unlock_heroes).grid(row=1,column=0,columnspan=4,sticky='w',pady=8)
                ttk.Button(profile,text='解锁全部成就…（游戏内 + Steam）',command=self.unlock_achievements).grid(row=2,column=0,columnspan=4,sticky='w',pady=8)
                ttk.Label(profile,text='成就操作需要输入确认文字；Steam 成就无法通过恢复存档撤销。',foreground='#b42318',wraplength=690).grid(row=3,column=0,columnspan=4,sticky='w',pady=6)
                widget.grid_configure(row=4,pady=10)
                widget.configure(text=(
                    '使用：通过 Steam 启动原版 → 点击连接 → 选择存档 → 使用修改功能。\n'
                    '此 EXE 自带 CE 接入组件；不需要安装 CE，也不附带游戏。\n'
                    '适配原版 Steam Build 24662480；版本不符会拒绝写入。\n\n'
                    '星星采用额外升级点，不改关卡星级。额外点数仅在连接后生效。\n'
                    '此 Steam PC 版没有启用钻石商店，已移除钻石入口。\n'
                    '英雄解锁按存档保存，连接修改器后生效，不改变通关记录。\n'
                    '英雄／成就操作请回到地图，关闭英雄和成就窗口。\n'
                    '修改星星、英雄、成就前自动备份；恢复前必须退出游戏。\n\n'
                    '快捷键（面板运行时全局生效）：\n'
                    'Ctrl+F1 加 1000 金币；Ctrl+F2 开关生命锁定；\n'
                    'Ctrl+F3 切换 1／2 倍速；Ctrl+F4 开关技能冷却；\n'
                    'Ctrl+F5 关闭全部临时效果。F8 切换游戏内状态条。\n\n'
                    '原有功能已获用户实测反馈；新增解锁功能待游戏内验收。\n'
                    '从旧版升级请先退出游戏和旧面板，再重新启动、连接。'))
        self.after(100,self.poll_hotkeys)

    def progression_slot(self):
        status=base.read_status()
        if not base.is_connected(status):raise ValueError('请先连接原版游戏。')
        if status.get('ce_version')!=VERSION:raise ValueError('请退出游戏和旧面板，使用新版重新连接。')
        slot=status.get('slot')
        if slot not in ('1','2','3') or status.get('in_level')!='0':raise ValueError('请先选择存档并返回地图。')
        if self.pending and self.pending[2] not in ('none','reset'):raise ValueError('上一条操作尚未确认，请稍后再试。')
        return slot

    def unlock_heroes(self):
        try:
            slot=self.progression_slot();base.backup()
            if self.progression_slot()!=slot:raise ValueError('存档已切换，请重新操作。')
            self.send('unlock_heroes',slot)
            self.note.set('英雄解锁已发送，等待游戏确认。')
        except (OSError,ValueError,RuntimeError) as e:messagebox.showerror('英雄解锁失败',str(e))

    def unlock_achievements(self):
        try:
            slot=self.progression_slot()
            answer=simpledialog.askstring('解锁全部成就 · 二次确认',
                '警告：游戏内成就和 Steam 成就都会全部解锁！\n'
                '恢复本地存档无法撤销 Steam 成就，Steam 记录可能永久改变。\n'
                f'操作对象：当前存档 {slot} 和当前登录的 Steam 账户。\n\n'
                '如确定继续，请完整输入下方文字；取消则不执行：\n'+CONFIRM_PHRASE,parent=self)
            if answer is None:return
            if answer!=CONFIRM_PHRASE:raise ValueError('确认文字不一致，没有执行任何解锁。')
            if self.progression_slot()!=slot:raise ValueError('确认期间存档已切换，请重新确认。')
            base.backup()
            if self.progression_slot()!=slot:raise ValueError('备份期间存档已切换，请重新确认。')
            self.send('unlock_achievements',slot+'|'+CONFIRM_PHRASE)
            self.note.set('成就解锁已发送，等待本地保存和 Steam 提交结果。')
        except (OSError,ValueError,RuntimeError) as e:messagebox.showerror('成就解锁失败',str(e))

    def launch(self):
        try:
            if self.backend and self.backend.poll() is None:raise RuntimeError('正在连接，请稍候。')
            if not base.game_running():raise RuntimeError('请先从 Steam 启动原版游戏；修改器不会替你启动游戏。')
            if self.connected():self.note.set('已连接，无需重复接入。');return
            engine=BUNDLE/'ce/cheatengine-x86_64.exe'
            script=BUNDLE/'ce/attach.CETRAINER'
            verify_components()
            folder=base.backup()
            self.reset(strict=True)
            base.CONTROL.mkdir(parents=True,exist_ok=True)
            for name in ('bridge_result.txt','status.txt','error.txt'):
                path=base.CONTROL/name
                if path.exists():path.unlink()
            info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
            self.backend=subprocess.Popen([str(engine),str(script),'NOAUTORUN'],cwd=engine.parent,
                startupinfo=info,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.backend_started=time.monotonic()
            self.note.set('正在通过 CE 连接原版游戏；备份：'+folder.name)
        except (OSError,ValueError,RuntimeError) as e:messagebox.showerror('连接失败',str(e))

    def refresh(self):
        super().refresh()
        if not self.connected():self.status_var.set('未连接 · 请先从 Steam 启动原版，再点击“连接原版游戏”')
        if not self.backend:return
        result=base.CONTROL/'bridge_result.txt'
        if result.exists():
            try:message=result.read_text(encoding='utf8')
            except (OSError,UnicodeError):return
            if message=='READY':self.note.set('CE 接入成功，临时接口已恢复。可以使用修改功能。')
            else:self.note.set(message)
            if self.backend.poll() is not None:self.backend=None
        elif self.backend.poll() is not None:
            self.note.set('CE 接入进程未返回成功结果；请检查版本或进程访问权限。')
            self.backend=None
        elif time.monotonic()-self.backend_started>25:
            self.note.set('接入未完成。请不要重复连接，等待恢复或退出游戏后重试。')

    def poll_hotkeys(self):
        down=set()
        get=ctypes.windll.user32.GetAsyncKeyState
        if get(0x11)&0x8000:
            for i in range(1,6):
                if get(0x6F+i)&0x8000:down.add(i)
        if self.connected():
            for i in down-self.hotkey_down:
                if i==1:self.add_gold()
                elif i==2:self.lock_lives.set(not self.lock_lives.get());self.apply()
                elif i==3:self.vars['speed'].set('2' if self.vars['speed'].get()=='1' else '1');self.apply()
                elif i==4:self.cooldown.set(not self.cooldown.get());self.apply()
                elif i==5:self.reset()
        self.hotkey_down=down
        self.after(100,self.poll_hotkeys)

    def close(self):
        if self.backend and self.backend.poll() is None:
            self.note.set('正在接入／恢复接口，请等待连接结束后关闭面板。')
            return
        super().close()

def main():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.restype=ctypes.c_void_p
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
    mutex=kernel.CreateMutexW(None,False,'Local\\KingdomRushCETrainerPanel')
    if ctypes.get_last_error()==183:messagebox.showinfo('修改器','CE 修改器已经打开。');return
    CEPanel().mainloop()

if __name__=='__main__':main()

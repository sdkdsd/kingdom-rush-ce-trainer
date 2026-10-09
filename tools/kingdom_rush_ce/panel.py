"""Standalone front end; CE performs the checked in-memory attachment."""
import ctypes
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import panel_base as base

BUNDLE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
COMPONENTS={'cheatengine-x86_64.exe','lua53-64.dll','defines.lua','main.lua','attach.CETRAINER'}
VERSION='2.2 RC2'
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
        self.connection_error=None
        self.connection_error_shown=False
        super().__init__()
        self.geometry('820x800')
        self.minsize(780,800)
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
                widget.grid_configure(row=4,pady=6)
                widget.configure(text=(
                    '使用：通过 Steam 启动原版 → 点击连接 → 选择存档 → 使用修改功能。\n'
                    '此 EXE 自带 CE 接入组件；不需要安装 CE，也不附带游戏。\n'
                    '适配原版 Steam Build 24662480；版本不符会拒绝写入。\n'
                    '星星采用额外升级点，不改关卡星级。额外点数仅在连接后生效。\n'
                    '此 Steam PC 版没有启用钻石商店，已移除钻石入口。\n'
                    '英雄解锁按存档保存，连接修改器后生效，不改变通关记录。\n'
                    '英雄／成就操作请回到地图，关闭英雄和成就窗口。\n'
                    '修改星星、英雄、成就前自动备份；恢复前必须退出游戏。\n'
                    '快捷键（面板运行时全局生效）：\n'
                    'Ctrl+F1 加 1000 金币；Ctrl+F2 开关生命锁定；\n'
                    'Ctrl+F3 切换 1／2 倍速；Ctrl+F4 开关技能冷却；\n'
                    'Ctrl+F5 关闭全部临时效果。F8 切换游戏内状态条。\n'
                    '原有功能和解锁已获用户实测反馈；新增战斗倍率待游戏内验收。\n'
                    '从旧版升级请先退出游戏和旧面板，再重新启动、连接。'))
        book=next(w for w in children(self) if isinstance(w,ttk.Notebook))
        battle=self.nametowidget(book.tabs()[0])
        book.tab(0,text='  我方buff  ')
        book.tab(1,text='  其他  ')
        # Pair each friendly damage control with its attack-speed control.
        # This keeps the existing window size and avoids a long scrolling page.
        for row,label,key in ((6,'英雄攻速','hero_rate'),(7,'士兵攻速','soldier_rate'),(8,'防御塔攻速','tower_rate')):
            ttk.Label(battle,text=label).grid(row=row,column=3,sticky='w',padx=(18,4))
            var=tk.StringVar(value='1');self.vars[key]=var
            ttk.Combobox(battle,textvariable=var,values=('1','2','3','5','10'),width=7).grid(row=row,column=4,padx=4)
            ttk.Label(battle,text='倍').grid(row=row,column=5,sticky='w')
        for widget in battle.winfo_children():
            info=widget.grid_info()
            if info and int(info['row']) in (5,9):widget.grid_configure(columnspan=6)
            if info and int(info['row'])==9:
                widget.configure(text='伤害只对敌人生效；防御塔攻速不影响士兵，士兵包含援军，英雄单独计算。\n'
                    '攻速调整攻击间隔、出手时间及攻击动画，不加快移动／复活；特殊技能受脚本限制。\n'
                    '游戏速度支持 10 倍并与攻速叠加；实际速度受电脑性能和模拟帧率限制。')
            if info and int(info['row'])==10:
                if int(info['column'])==0:widget.configure(text='应用全部设置')
                else:widget.grid_configure(column=3,columnspan=3)
        extra=ttk.Frame(book,padding=16);book.insert(1,extra,text='  敌方debuff  ')
        for row,(label,key,values) in enumerate([
            ('敌人击杀金币奖励','enemy_gold',('1','2','5','10','20','100')),
            ('敌人移动速度','enemy_speed',('1','0.75','0.5','0.25','0.1')),
            ('敌人攻击伤害','enemy_damage',('1','0.75','0.5','0.25','0.1','0'))]):
            self.make_factor(extra,row,label,key,values)
        ttk.Label(extra,text='全部默认 1 倍；敌人移动和伤害倍率越小越弱，伤害可设为 0。\n'
            '金币倍率仅作用于击杀奖励；提前出怪奖励、卖塔退款和漏怪返金保持原值。\n'
            '特殊即死效果不属于数值伤害；瞬移不属于普通移动。',
            foreground='#596579',wraplength=690).grid(row=3,column=0,columnspan=4,sticky='w',pady=16)
        ttk.Button(extra,text='应用全部设置',command=self.apply).grid(row=4,column=0,columnspan=2,sticky='w')
        ttk.Button(extra,text='恢复全部临时效果为默认',command=self.reset).grid(row=4,column=2,columnspan=2,sticky='e')
        extra.columnconfigure(0,weight=1)
        # Reserve the footer before the expanding notebook, so errors stay visible.
        footer=next(w for w in children(self) if isinstance(w,ttk.Label)
            and str(w.cget('textvariable'))==str(self.note))
        footer.pack_configure(side='bottom',before=book)
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
            self.connection_error=None;self.connection_error_shown=False
            engine=BUNDLE/'ce/cheatengine-x86_64.exe'
            script=BUNDLE/'ce/attach.CETRAINER'
            verify_components()
            folder=base.backup()
            self.reset(strict=True)
            base.CONTROL.mkdir(parents=True,exist_ok=True)
            for name in ('bridge_result.txt','connection_diagnostics.txt','status.txt','error.txt'):
                path=base.CONTROL/name
                if path.exists():path.unlink()
            info=subprocess.STARTUPINFO();info.dwFlags|=subprocess.STARTF_USESHOWWINDOW;info.wShowWindow=0
            self.backend=subprocess.Popen([str(engine),str(script),'NOAUTORUN'],cwd=engine.parent,
                startupinfo=info,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.backend_started=time.monotonic()
            self.note.set('正在通过 CE 连接原版游戏；备份：'+folder.name)
        except (OSError,ValueError,RuntimeError) as e:
            self.report_connection_error(str(e),popup=True)

    def report_connection_error(self,message,popup=False):
        self.connection_error=message
        summary=re.sub(r'^ERROR\s*','',message)
        summary=re.sub(r'^\[string[\s\S]*?\]:\d+:\s*','',summary)
        summary=' '.join(summary.split())
        self.note.set(summary if len(summary)<=72 else summary[:72]+'…（详情见日志）')
        self.status_var.set('连接失败 · 具体原因见下方提示')
        if popup and not self.connection_error_shown:
            self.connection_error_shown=True
            messagebox.showerror('连接失败',message+'\n\n诊断文件位于：\n'+str(base.CONTROL)+
                '\n请保留 bridge_result.txt 和 connection_diagnostics.txt（若已生成）。')

    def refresh(self):
        super().refresh()
        if not self.connected():self.status_var.set('未连接 · 请先从 Steam 启动原版，再点击“连接原版游戏”')
        if not self.backend:
            if self.connected():self.connection_error=None
            elif self.connection_error:self.report_connection_error(self.connection_error)
            return
        result=base.CONTROL/'bridge_result.txt'
        if result.exists():
            try:message=result.read_text(encoding='utf8')
            except (OSError,UnicodeError) as e:message='无法读取连接结果：'+str(e)
            stopped=self.backend.poll() is not None
            if stopped:self.backend=None
            if message=='READY':
                self.connection_error=None
                self.note.set('CE 接入成功，临时接口已恢复。可以使用修改功能。')
            else:self.report_connection_error(message,popup=stopped)
        elif self.backend.poll() is not None:
            self.backend=None
            self.report_connection_error('CE 接入进程未返回成功结果；请检查版本或进程访问权限。',popup=True)
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

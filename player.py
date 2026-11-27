"""Standalone offline Audition TBM player and MP3 exporter for Windows."""
from __future__ import annotations
import argparse
from collections import OrderedDict
import ctypes
from datetime import datetime, timedelta, timezone
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
import unicodedata

from audio_utils import ExportError, export_audio, find_tool
from tbm_decoder import decode_file


class WavePlayer:
    def __init__(self):
        self.dll = ctypes.WinDLL('winmm')
        self.dll.mciSendStringW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HWND]
        self.dll.mciSendStringW.restype = wintypes.DWORD
        self.dll.mciGetErrorStringW.argtypes = [wintypes.DWORD, wintypes.LPWSTR, wintypes.UINT]
        self.dll.mciGetErrorStringW.restype = wintypes.BOOL
        self.opened = False

    def command(self, text):
        result = ctypes.create_unicode_buffer(512)
        code = self.dll.mciSendStringW(text, result, len(result), None)
        if code:
            detail = ctypes.create_unicode_buffer(512)
            self.dll.mciGetErrorStringW(code, detail, len(detail))
            raise ExportError(f'Không phát được âm thanh ({code}): {detail.value}')
        return result.value

    def open(self, path):
        self.close()
        self.command(f'open "{path}" type waveaudio alias tbm_music')
        self.opened = True
        self.command('set tbm_music time format milliseconds')

    def play(self):
        self.command('play tbm_music from 0')

    def pause(self):
        self.command('pause tbm_music')

    def resume(self):
        self.command('resume tbm_music')

    def stop(self):
        if self.opened:
            self.command('stop tbm_music')
            self.command('seek tbm_music to start')

    def position(self):
        return int(self.command('status tbm_music position')) if self.opened else 0

    def mode(self):
        return self.command('status tbm_music mode') if self.opened else 'stopped'

    def close(self):
        if self.opened:
            try:
                self.command('close tbm_music')
            finally:
                self.opened = False


def clock(seconds):
    seconds = max(0, int(seconds))
    return f'{seconds // 60}:{seconds % 60:02d}'


class PlaybackSequence:
    """Consume a natural end once; a manual stop must never advance the list."""
    def __init__(self):
        self.armed = False

    def started(self):
        self.armed = True

    def stopped(self):
        self.armed = False

    def completed(self, mode, position, duration, paused=False, busy=False):
        if (not self.armed or paused or busy or mode != 'stopped'
                or duration <= 0 or position < duration - 0.2):
            return False
        self.armed = False
        return True


def next_song(playlist, current):
    try:
        index = playlist.index(current) + 1
    except ValueError:
        return None
    return playlist[index] if index < len(playlist) else None


def file_identity(path):
    path = Path(path)
    info = path.stat()
    return (str(path.resolve()), info.st_mtime_ns, info.st_ctime_ns,
            info.st_size, info.st_ino)


def folder_snapshot(folder):
    entries = []
    for path in Path(folder).iterdir():
        if path.suffix.lower() not in ('.tbm', '.abm'):
            continue
        try:
            if path.is_file():
                entries.append((path, file_identity(path)))
        except FileNotFoundError:
            continue  # A patcher may rename a file while the directory is scanned.
    return tuple(sorted(entries, key=lambda item: item[0].name.casefold()))


class FileChangedError(ExportError):
    pass


def source_revision(path):
    before = file_identity(path)
    with Path(path).open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    if file_identity(path) != before:
        raise FileChangedError('Tệp đang được cập nhật; chờ ghi xong rồi phát lại.')
    return before + (digest,)


class DecodedTrackCache:
    """Decode on access and reuse a result only for the same file revision."""
    def __init__(self, limit=3):
        self.limit = limit
        self.entries = OrderedDict()

    def get(self, path, loader):
        before = source_revision(path)
        if before in self.entries:
            self.entries.move_to_end(before)
            return self.entries[before]
        try:
            result = loader(path)
        except Exception as error:
            if source_revision(path) != before:
                raise FileChangedError('Tệp đang được cập nhật; chờ ghi xong rồi phát lại.') from error
            raise
        if source_revision(path) != before:
            raise FileChangedError('Tệp thay đổi trong lúc giải mã; chờ ghi xong rồi phát lại.')
        # Remove earlier versions of this file instead of keeping stale audio.
        for old in list(self.entries):
            if old[0] == before[0]:
                del self.entries[old]
        self.entries[before] = result
        while len(self.entries) > self.limit:
            self.entries.popitem(last=False)
        return result


class SongCatalog:
    def __init__(self, tracks=None):
        self.tracks = {}
        for name, item in (tracks or {}).items():
            if not isinstance(name, str) or not isinstance(item, dict):
                continue
            self.tracks[name.casefold()] = {
                key: item.get(key, '').strip() if isinstance(item.get(key), str) else ''
                for key in ('title', 'artist')
            }

    @classmethod
    def load(cls):
        # A sidecar can be updated without rebuilding the EXE. Bundle is fallback.
        bundled = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        external = Path(sys.executable).parent if getattr(sys, 'frozen', False) else bundled
        for path in dict.fromkeys((external / 'song_metadata.json', bundled / 'song_metadata.json')):
            try:
                data = json.loads(path.read_text(encoding='utf-8-sig'))
                if isinstance(data, dict) and isinstance(data.get('tracks'), dict):
                    return cls(data['tracks'])
            except (OSError, ValueError):
                continue
        return cls()

    def details(self, path):
        path = Path(path)
        item = self.tracks.get(path.name.casefold(), {})
        return item.get('title') or path.name, item.get('artist', '')

    def label(self, path):
        title, artist = self.details(path)
        return f'{title} — {artist}' if artist else title

    @staticmethod
    def search_text(text):
        text = unicodedata.normalize('NFD', text.casefold().replace('đ', 'd'))
        return ''.join(c for c in text if not unicodedata.combining(c))

    def matches(self, path, query):
        title, artist = self.details(path)
        return self.search_text(query.strip()) in self.search_text(f'{Path(path).name} {title} {artist}')


def gui(initial=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title('Audition Music — Offline Player')
    root.geometry('1280x800')
    root.minsize(1080, 680)
    bg, paper, navy = '#edf3fa', '#ffffff', '#172d48'
    ink, muted, blue, mint = '#20344d', '#61758d', '#2869c9', '#69d9c4'
    root.configure(bg=bg)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('.', font=('Segoe UI', 10), background=bg, foreground=ink)
    style.configure('TFrame', background=bg)
    style.configure('TLabel', background=bg, foreground=ink)
    style.configure('Muted.TLabel', foreground=muted)
    style.configure('Nav.TFrame', background=navy)
    style.configure('Nav.TLabel', background=navy, foreground='#c7d7e9')
    style.configure('TButton', background='#e0eaf6', foreground=ink, borderwidth=0,
                    padding=(14, 10), focusthickness=2, focuscolor=blue)
    style.map('TButton', background=[('active', '#d1e0f2'), ('disabled', '#e6ecf3')],
              foreground=[('disabled', '#8e9aaa')])
    style.configure('Primary.TButton', background=blue, foreground='white', font=('Segoe UI', 11, 'bold'))
    style.map('Primary.TButton', background=[('active', '#1c56ac'), ('disabled', '#b6c9e2')],
              foreground=[('disabled', '#edf3fa')])
    style.configure('Nav.TButton', background='#264260', foreground='#f2f7ff', anchor='w')
    style.map('Nav.TButton', background=[('active', '#365675'), ('disabled', '#213850')],
              foreground=[('disabled', '#879aaf')])
    style.configure('TEntry', fieldbackground=paper, foreground=ink, padding=10, bordercolor='#dbe5f1')
    style.map('TEntry', bordercolor=[('focus', blue)])
    style.configure('Treeview', background=paper, fieldbackground=paper, foreground=ink,
                    font=('Segoe UI', 10), rowheight=43, borderwidth=0, lightcolor=paper, darkcolor=paper)
    style.map('Treeview', background=[('selected', '#dbeaff')], foreground=[('selected', '#144e99')])
    style.configure('Treeview.Heading', background='#e5edf7', foreground=muted,
                    font=('Segoe UI', 9, 'bold'), padding=(10, 12), relief='flat', borderwidth=0)
    style.map('Treeview.Heading', background=[('active', '#d9e6f5')])
    style.configure('Vertical.TScrollbar', background='#cbd9e9', troughcolor=bg, borderwidth=0, arrowsize=13)
    style.configure('TCheckbutton', background=bg, foreground=muted, padding=4)
    style.map('TCheckbutton', background=[('active', bg)], foreground=[('active', ink)])
    style.configure('Music.Horizontal.TProgressbar', background=blue, troughcolor='#d9e4f1',
                    borderwidth=0, lightcolor=blue, darkcolor=blue, thickness=5)

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    shell = ttk.Frame(root)
    shell.grid(row=0, column=0, sticky='nsew')
    shell.columnconfigure(1, weight=1)
    shell.rowconfigure(0, weight=1)
    sidebar = ttk.Frame(shell, style='Nav.TFrame', padding=(20, 28), width=185)
    sidebar.grid(row=0, column=0, sticky='ns')
    sidebar.grid_propagate(False)
    sidebar.columnconfigure(0, weight=1)
    sidebar.rowconfigure(5, weight=1)
    ttk.Label(sidebar, text='Audition', style='Nav.TLabel', font=('Segoe UI', 22, 'bold'),
              foreground='white').grid(row=0, column=0, sticky='w')
    ttk.Label(sidebar, text='Music player', style='Nav.TLabel', font=('Segoe UI', 10)).grid(
              row=1, column=0, sticky='w', pady=(0, 32))
    ttk.Label(sidebar, text='♫  Thư viện nhạc', style='Nav.TLabel', foreground=mint,
              font=('Segoe UI', 11, 'bold')).grid(row=2, column=0, sticky='w', pady=(0, 18))
    main = ttk.Frame(shell, padding=(28, 24, 20, 14))
    main.grid(row=0, column=1, sticky='nsew')
    main.columnconfigure(0, weight=1)
    main.rowconfigure(3, weight=1)
    now_panel = ttk.Frame(shell, style='Nav.TFrame', padding=(22, 28), width=260)
    now_panel.grid(row=0, column=2, sticky='ns', padx=(0, 18), pady=(24, 14))
    now_panel.pack_propagate(False)
    dock = ttk.Frame(root, padding=(24, 14, 24, 12))
    dock.grid(row=1, column=0, sticky='ew')
    dock.columnconfigure(1, weight=1)

    files = []
    shown = []
    cache = DecodedTrackCache()
    songs = SongCatalog.load()
    watched_folder = None
    catalog_signature = None
    last_folder_scan = 0
    events = queue.Queue()
    search = tk.StringVar()
    folder_label = tk.StringVar(value='')
    status = tk.StringVar(value='Chọn tệp TBM rồi nhấn Nghe. Không cần mở game hoặc đăng nhập.')
    track_label = tk.StringVar(value='Chọn một bài hát')
    artist_label = tk.StringVar(value='Thư viện Audition')
    play_state = tk.StringVar(value='Sẵn sàng')
    detail_label = tk.StringVar(value='')
    time_label = tk.StringVar(value='0:00 / 0:00')
    auto_next = tk.BooleanVar(value=True)
    sequence = PlaybackSequence()
    busy = False
    paused = False
    total = 0
    current_path = None
    play_request = 0
    disc_playing = False
    ffmpeg = find_tool('ffmpeg')
    workspace = tempfile.TemporaryDirectory(prefix='TBMPlayer-')
    player = WavePlayer()

    def selected():
        ids = tree.selection()
        if not ids:
            raise ExportError('Hãy chọn một tệp nhạc trong danh sách.')
        return shown[int(ids[0])]

    def refresh(*unused):
        nonlocal shown
        chosen = None
        try:
            chosen = selected()
        except ExportError:
            pass
        term = search.get().strip().casefold()
        shown = [p for p in files if songs.matches(p, term)]
        tree.delete(*tree.get_children())
        selected_id = None
        for i, path in enumerate(shown):
            try:
                info = path.stat()
                size = f'{info.st_size / 1024**2:.2f} MiB'
                modified = datetime.fromtimestamp(info.st_mtime, timezone(timedelta(hours=7))).strftime('%d/%m/%Y %H:%M')
            except (OSError, ValueError, OverflowError):
                size = 'Không đọc được'
                modified = '—'
            title, artist = songs.details(path)
            tree.insert('', 'end', iid=str(i), values=(title, artist, path.name, modified, size),
                        tags=(('even' if i % 2 == 0 else 'odd'),) + (('playing',) if path == current_path else ()))
            if path == chosen or (chosen is None and path.stem == 'v3585'):
                selected_id = str(i)
        if shown:
            selected_id = selected_id or '0'
            tree.selection_set(selected_id)
            tree.see(selected_id)
        location = watched_folder or (files[0].parent if files else None)
        folder_label.set(f'{len(shown):,} / {len(files):,} bài hát' + ('  •  ' + str(location) if location else ''))

    def load_folder(path):
        nonlocal files, watched_folder, catalog_signature, last_folder_scan
        folder = Path(path).resolve()
        snapshot = folder_snapshot(folder)
        watched_folder = folder
        catalog_signature = snapshot
        last_folder_scan = time.monotonic()
        files = [item[0] for item in snapshot]
        search.set('')
        refresh()
        status.set(f'Đã nạp {len(files)} tệp. Chọn bài và nhấn Nghe.')

    def sync_folder(force=False):
        nonlocal files, catalog_signature, last_folder_scan
        if watched_folder is None:
            return
        now = time.monotonic()
        if not force and now - last_folder_scan < 3:
            return
        last_folder_scan = now
        try:
            snapshot = folder_snapshot(watched_folder)
        except OSError:
            folder_label.set('Tạm thời không đọc được thư mục: ' + str(watched_folder))
            return
        if snapshot != catalog_signature:
            catalog_signature = snapshot
            files = [item[0] for item in snapshot]
            refresh()

    def choose_folder():
        path = filedialog.askdirectory(initialdir=r'D:\Audition\abm', title='Chọn thư mục chứa TBM/ABM')
        if path:
            try:
                load_folder(path)
            except OSError as e:
                messagebox.showerror('Không mở được thư mục', str(e))

    def choose_file():
        nonlocal files, watched_folder, catalog_signature
        path = filedialog.askopenfilename(initialdir=r'D:\Audition\abm',
                                          filetypes=[('Nhạc Audition', '*.tbm *.abm'), ('Tất cả tệp', '*.*')])
        if path:
            watched_folder = None
            catalog_signature = None
            files = [Path(path)]
            search.set('')
            refresh()

    open_button = ttk.Button(sidebar, text='Mở tệp…', style='Nav.TButton', command=choose_file)
    open_button.grid(row=3, column=0, sticky='ew', pady=(0, 8))
    folder_button = ttk.Button(sidebar, text='Mở thư mục…', style='Nav.TButton', command=choose_folder)
    folder_button.grid(row=4, column=0, sticky='ew')
    ttk.Label(sidebar, text='Nhạc trong máy.\nNghe theo cách của bạn.', style='Nav.TLabel',
              wraplength=145, justify='left').grid(row=6, column=0, sticky='sw', pady=(16, 18))
    ttk.Label(main, text='Thư viện của bạn', font=('Segoe UI', 24, 'bold')).grid(
              row=0, column=0, sticky='w', pady=(0, 6))
    ttk.Label(main, textvariable=folder_label, style='Muted.TLabel', wraplength=480).grid(
              row=1, column=0, sticky='w', pady=(0, 18))
    search_row = ttk.Frame(main)
    search_row.grid(row=2, column=0, sticky='ew', pady=(0, 16))
    ttk.Label(search_row, text='Tìm nhạc', style='Muted.TLabel').pack(side='left', padx=(0, 12))
    search_entry = ttk.Entry(search_row, textvariable=search)
    search_entry.pack(side='left', fill='x', expand=True)
    list_frame = ttk.Frame(main)
    list_frame.grid(row=3, column=0, sticky='nsew')
    tree = ttk.Treeview(list_frame, columns=('name', 'artist', 'file', 'modified', 'size'), show='headings', selectmode='browse', height=7)
    for key, label in [('name', 'Tên bài hát'), ('artist', 'Ca sĩ'), ('file', 'Tệp'), ('modified', 'Ngày sửa đổi'), ('size', 'Dung lượng')]:
        tree.heading(key, text=label, anchor='w')
    tree.column('name', width=220, minwidth=150)
    tree.column('artist', width=120, minwidth=90)
    tree.column('file', width=105, minwidth=95, stretch=False)
    tree.column('modified', width=148, minwidth=145, anchor='center', stretch=False)
    tree.column('size', width=80, minwidth=80, anchor='center', stretch=False)
    tree.tag_configure('even', background=paper)
    tree.tag_configure('odd', background='#f7faff')
    tree.tag_configure('playing', background='#e2f3ee', foreground='#126655')
    scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
    horizontal = ttk.Scrollbar(list_frame, orient='horizontal', command=tree.xview)
    tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
    list_frame.rowconfigure(0, weight=1)
    list_frame.columnconfigure(0, weight=1)
    tree.grid(row=0, column=0, sticky='nsew')
    scrollbar.grid(row=0, column=1, sticky='ns')
    horizontal.grid(row=1, column=0, sticky='ew')
    search.trace_add('write', refresh)

    def stop():
        nonlocal paused, play_request, disc_playing
        disc_playing = False
        play_request += 1
        sequence.stopped()
        try:
            player.stop()
            paused = False
            pause_button.configure(text='Tạm dừng')
            progress['value'] = 0
            time_label.set(f'0:00 / {clock(total)}')
            play_state.set('Đã dừng')
            status.set('Đã dừng phát.')
        except ExportError as e:
            status.set(str(e))

    def pause():
        nonlocal paused, disc_playing
        if not player.opened:
            return
        try:
            if paused:
                player.resume()
            elif player.mode() == 'playing':
                player.pause()
            else:
                return
            paused = not paused
            disc_playing = not paused
            play_state.set('Tạm dừng' if paused else 'Đang phát')
            pause_button.configure(text='Tiếp tục' if paused else 'Tạm dừng')
        except ExportError as e:
            messagebox.showerror('Phát nhạc', str(e))

    def decoded(path):
        def load(source):
            events.put(('status', 'Đang giải mã và kiểm tra OGG: ' + source.name))
            return decode_file(source)
        for attempt in range(3):
            try:
                return cache.get(path, load)
            except FileChangedError:
                if attempt == 2:
                    raise
                events.put(('status', 'Tệp đang cập nhật, đang chờ đọc lại: ' + path.name))
                time.sleep(0.4)

    def start_job(function, source=None):
        nonlocal busy
        if busy:
            return
        busy = True
        for button in job_buttons:
            button.configure(state='disabled')
        status.set('Đang xử lý…')
        play_state.set('Đang xử lý')
        def worker():
            try:
                function()
            except Exception as e:
                events.put(('error', f'{source.name}\n{e}' if source else str(e)))
            finally:
                events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def listen(path=None):
        if busy:
            return
        if path is None:
            try:
                path = selected()
            except ExportError as e:
                messagebox.showinfo('Chọn bài', str(e))
                return
        stop()
        request = play_request
        def worker():
            track, receipt = decoded(path)
            if not ffmpeg:
                raise ExportError('Chưa tìm thấy FFmpeg. Nhấn Chọn FFmpeg để chọn ffmpeg.exe trong máy.')
            wav = Path(workspace.name) / (track.digest + '.wav')
            if not wav.exists():
                export_audio(track, wav, ffmpeg)
            events.put(('play', (request, path, track, receipt, str(wav))))
        start_job(worker, path)

    def save(ext):
        try:
            path = selected()
        except ExportError as e:
            messagebox.showinfo('Chọn bài', str(e))
            return
        destination = filedialog.asksaveasfilename(initialfile=path.stem + ext, defaultextension=ext,
            filetypes=[('MP3', '*.mp3')] if ext == '.mp3' else [('OGG gốc', '*.ogg'), ('WAV', '*.wav')])
        if not destination:
            return
        if Path(destination).exists():
            messagebox.showinfo('Chọn tên khác', 'Công cụ không ghi đè tệp có sẵn. Hãy chọn một tên mới.')
            return
        def worker():
            track, receipt = decoded(path)
            export_audio(track, destination, ffmpeg)
            events.put(('saved', (path, track, receipt, destination)))
        start_job(worker, path)

    def adjacent(direction):
        if busy:
            return
        sync_folder(force=True)
        if not shown:
            return
        path = current_path
        if path not in shown:
            try:
                path = selected()
            except ExportError:
                path = shown[0]
        index = shown.index(path) + direction
        if 0 <= index < len(shown):
            row = str(index)
            tree.selection_set(row)
            tree.see(row)
            listen(shown[index])
        else:
            status.set('Đã đến đầu danh sách.' if direction < 0 else 'Đã đến cuối danh sách.')

    ttk.Label(now_panel, textvariable=play_state, style='Nav.TLabel', foreground=mint,
              font=('Segoe UI', 10, 'bold')).pack(anchor='w', pady=(0, 20))
    record = tk.Canvas(now_panel, width=216, height=228, bg=navy, highlightthickness=0)
    record.pack(fill='x', pady=(0, 22))
    record_angle = 0.0
    record_tick = time.monotonic()
    def draw_record(event=None):
        record.delete('all')
        width, height = record.winfo_width(), record.winfo_height()
        x, y = width / 2, height / 2
        radius = max(12, min(width, height) / 2 - 8)
        record.create_oval(x-radius, y-radius, x+radius, y+radius,
                           fill='#101e32', outline='#34506e', width=2)
        for ratio in (.86, .75, .64, .53, .42):
            r = radius * ratio
            record.create_oval(x-r, y-r, x+r, y+r, outline='#233c56')
        for tag, offset, extent in [('record_shine_a', 30, 44), ('record_shine_b', 210, 24)]:
            r = radius * .91
            record.create_arc(x-r, y-r, x+r, y+r, start=offset-record_angle, extent=extent,
                              style='arc', outline='#53718e', width=2, tags=tag)
        r = radius * .3
        record.create_oval(x-r, y-r, x+r, y+r, fill=mint, outline='')
        record.create_text(x, y, text='♫', fill=navy, font=('Segoe UI', max(12, int(radius / 4))),
                           angle=-record_angle, tags='record_note')
        record.create_oval(x-3, y-3, x+3, y+3, fill=navy, outline='')

    def animate_record():
        nonlocal record_angle, record_tick
        now = time.monotonic()
        elapsed = now - record_tick
        record_tick = now
        if disc_playing:
            record_angle = (record_angle + 60 * min(elapsed, .1)) % 360
            # Rotate just the visible markings; keep the grooves and disc intact.
            record.itemconfigure('record_shine_a', start=30-record_angle)
            record.itemconfigure('record_shine_b', start=210-record_angle)
            record.itemconfigure('record_note', angle=-record_angle)
        root.after(33 if disc_playing else 150, animate_record)

    record.bind('<Configure>', draw_record)
    now_panel.bind('<Configure>', lambda event: record.configure(height=max(95, min(228, event.height - 340))))
    ttk.Label(now_panel, textvariable=track_label, style='Nav.TLabel', foreground='white',
              font=('Segoe UI', 16, 'bold'), wraplength=212, justify='left').pack(anchor='w')
    ttk.Label(now_panel, textvariable=artist_label, style='Nav.TLabel', wraplength=212,
              justify='left').pack(anchor='w', pady=(8, 22))
    ttk.Label(now_panel, textvariable=detail_label, style='Nav.TLabel', foreground='#8fa8c3',
              font=('Segoe UI', 9), wraplength=212, justify='left').pack(anchor='w')

    export_row = ttk.Frame(main)
    export_row.grid(row=4, column=0, sticky='ew', pady=(14, 0))
    ttk.Checkbutton(export_row, text='Tự chuyển bài khi hết', variable=auto_next).pack(side='left')
    mp3_button = ttk.Button(export_row, text='Xuất MP3…', command=lambda: save('.mp3'))
    mp3_button.pack(side='right')
    ogg_button = ttk.Button(export_row, text='Lưu OGG / WAV…', command=lambda: save('.ogg'))
    ogg_button.pack(side='right', padx=(8, 8))
    job_buttons = [mp3_button, ogg_button, open_button, folder_button]

    dock_track = ttk.Frame(dock, width=235)
    dock_track.grid(row=0, column=0, rowspan=2, sticky='nw', padx=(0, 24))
    ttk.Label(dock_track, textvariable=track_label, font=('Segoe UI', 11, 'bold'),
              wraplength=210, justify='left').pack(anchor='w')
    ttk.Label(dock_track, textvariable=artist_label, style='Muted.TLabel',
              wraplength=210).pack(anchor='w', pady=(3, 0))
    actions = ttk.Frame(dock)
    actions.grid(row=0, column=1, sticky='ew')
    controls = ttk.Frame(actions)
    controls.pack(anchor='center')
    previous_button = ttk.Button(controls, text='Bài trước', command=lambda: adjacent(-1))
    previous_button.pack(side='left', padx=(0, 8))
    play_button = ttk.Button(controls, text='▶  Nghe', style='Primary.TButton', command=listen)
    play_button.pack(side='left')
    pause_button = ttk.Button(controls, text='Tạm dừng', command=pause)
    pause_button.pack(side='left', padx=8)
    ttk.Button(controls, text='Dừng', command=stop).pack(side='left')
    next_button = ttk.Button(controls, text='Bài sau', command=lambda: adjacent(1))
    next_button.pack(side='left', padx=(8, 0))
    job_buttons.extend((play_button, previous_button, next_button))
    playback = ttk.Frame(dock)
    playback.grid(row=1, column=1, sticky='ew', pady=(12, 2))
    progress = ttk.Progressbar(playback, style='Music.Horizontal.TProgressbar', mode='determinate', maximum=1)
    progress.pack(side='left', fill='x', expand=True, padx=(0, 14))
    ttk.Label(playback, textvariable=time_label, style='Muted.TLabel', font=('Segoe UI', 9),
              width=15, anchor='e').pack(side='right')
    ttk.Label(dock, textvariable=status, foreground=muted, font=('Segoe UI', 9),
              wraplength=1080).grid(row=2, column=0, columnspan=2, sticky='w', pady=(12, 0))

    def choose_ffmpeg():
        nonlocal ffmpeg
        path = filedialog.askopenfilename(title='Chọn FFmpeg', filetypes=[('FFmpeg', 'ffmpeg*.exe')])
        if path:
            ffmpeg = path
            status.set('Đã chọn FFmpeg: ' + path)

    ttk.Button(sidebar, text='Chọn FFmpeg…', style='Nav.TButton', command=choose_ffmpeg).grid(
               row=7, column=0, sticky='ew')

    def describe(path, track, receipt):
        title, artist = songs.details(path)
        track_label.set(title)
        artist_label.set(artist or 'Chưa có thông tin ca sĩ')
        detail_label.set(f'{path.name}\n{clock(track.seconds)}   /   {track.rate:,} Hz\n{track.channels} kênh   /   {len(track.data) / 1024**2:.2f} MiB')

    def pump():
        nonlocal busy, total, paused, current_path, disc_playing
        sync_folder()
        while True:
            try:
                kind, value = events.get_nowait()
            except queue.Empty:
                break
            if kind == 'status':
                status.set(value)
            elif kind == 'error':
                play_state.set('Chưa phát được')
                status.set('Chưa hoàn tất: ' + value)
                messagebox.showerror('Chưa hoàn tất', value)
            elif kind == 'done':
                busy = False
                if play_state.get() == 'Đang xử lý':
                    play_state.set(('Tạm dừng' if paused else 'Đang phát') if player.opened else 'Sẵn sàng')
                for button in job_buttons:
                    button.configure(state='normal')
            elif kind == 'play':
                request, path, track, receipt, wav = value
                if request != play_request:
                    continue
                describe(path, track, receipt)
                try:
                    player.open(wav)
                    total = track.seconds
                    for candidate in (current_path, path):
                        if candidate in shown:
                            index = shown.index(candidate)
                            tags = ('even' if index % 2 == 0 else 'odd',) + (('playing',) if candidate == path else ())
                            tree.item(str(index), tags=tags)
                    current_path = path
                    play_state.set('Đang phát')
                    progress['maximum'] = total
                    player.play()
                    disc_playing = True
                    sequence.started()
                    paused = False
                    pause_button.configure(text='Tạm dừng')
                    status.set('Đang phát ' + songs.label(path))
                except ExportError as e:
                    sequence.stopped()
                    status.set(str(e))
                    messagebox.showerror('Phát nhạc', str(e))
            elif kind == 'saved':
                path, track, receipt, destination = value
                if not player.opened:
                    describe(path, track, receipt)
                status.set('Đã xuất: ' + destination)
                messagebox.showinfo('Đã xuất nhạc', destination)
        if player.opened:
            try:
                pos = player.position() / 1000
                progress['value'] = pos
                time_label.set(f'{clock(pos)} / {clock(total)}')
                mode = player.mode()
                disc_playing = mode == 'playing' and not paused
                if current_path and sequence.completed(mode, pos, total, paused, busy):
                    play_state.set('Đã phát xong')
                    status.set('Đã phát xong ' + songs.label(current_path))
                    sync_folder(force=True)
                    following = next_song(shown, current_path) if auto_next.get() else None
                    if following is not None:
                        row = str(shown.index(following))
                        tree.selection_set(row)
                        tree.see(row)
                        listen(following)
            except ExportError:
                disc_playing = False
        else:
            disc_playing = False
        root.after(200, pump)

    def close():
        if busy:
            messagebox.showinfo('Đang xử lý', 'Chờ tác vụ giải mã/xuất tệp hoàn tất rồi đóng cửa sổ.')
            return
        player.close()
        try:
            workspace.cleanup()
        except OSError:
            pass
        root.destroy()

    def preview_selection(event=None):
        if player.opened:
            return
        try:
            path = selected()
        except ExportError:
            return
        title, artist = songs.details(path)
        track_label.set(title)
        artist_label.set(artist or 'Chưa có thông tin ca sĩ')
        detail_label.set(path.name)

    tree.bind('<<TreeviewSelect>>', preview_selection)
    root.bind('<Control-f>', lambda event: search_entry.focus_set())
    tree.bind('<Double-1>', lambda event: listen() if not busy else None)
    root.protocol('WM_DELETE_WINDOW', close)
    if initial:
        files = [Path(initial)]
        refresh()
    elif Path(r'D:\Audition\abm').is_dir():
        load_folder(r'D:\Audition\abm')
    root.after(200, pump)
    root.after(33, animate_record)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description='Nghe và xuất nhạc TBM Audition offline.')
    parser.add_argument('file', nargs='?')
    parser.add_argument('--export', dest='destination', help='Xuất .mp3, .ogg hoặc .wav mà không mở giao diện')
    parser.add_argument('--report', help='Ghi biên bản kiểm tra JSON vào tệp mới')
    args = parser.parse_args()
    if args.destination:
        try:
            if not args.file:
                raise ExportError('Cần chỉ định tệp TBM đầu vào.')
            track, receipt = decode_file(args.file)
            export_audio(track, args.destination)
            if args.report:
                with Path(args.report).open('x', encoding='utf-8') as out:
                    json.dump(receipt, out, ensure_ascii=False, indent=2)
            if sys.stdout:
                print(json.dumps(receipt, ensure_ascii=True))
            return 0
        except Exception as e:
            if sys.stderr:
                print(str(e), file=sys.stderr)
            return 1
    gui(args.file)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

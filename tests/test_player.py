from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
import os
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import player as app
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class SequenceTests(unittest.TestCase):
    def test_completion_is_once_and_waits_for_idle(self):
        seq = app.PlaybackSequence()
        seq.started()
        self.assertFalse(seq.completed('playing', 10, 10))
        self.assertFalse(seq.completed('paused', 10, 10, paused=True))
        self.assertFalse(seq.completed('stopped', 10, 10, busy=True))
        self.assertTrue(seq.completed('stopped', 10, 10))
        self.assertFalse(seq.completed('stopped', 10, 10))

    def test_manual_stop_cancels_completion(self):
        seq = app.PlaybackSequence()
        seq.started()
        seq.stopped()
        self.assertFalse(seq.completed('stopped', 10, 10))

    def test_list_end_and_filtered_out_track(self):
        self.assertEqual(app.next_song(['a', 'b'], 'a'), 'b')
        self.assertIsNone(app.next_song(['a', 'b'], 'b'))
        self.assertIsNone(app.next_song(['b'], 'a'))


class GuiTests(unittest.TestCase):
    def run_scenario(self, scenario):
        played = []
        failures = []
        roots = []
        finished = False
        decoded_paths = []
        with tempfile.TemporaryDirectory(prefix='tbm-autonext-test-') as temp:
            folder = Path(temp)
            (folder / 'a.tbm').write_bytes(b'fixture-a')
            (folder / 'b.tbm').write_bytes(b'fixture-b')
            if scenario in ('added_at_end', 'folder_poll'):
                (folder / 'b.tbm').unlink()

            class FakePlayer:
                opened = False
                state = 'stopped'
                started_at = 0
                pos = 0
                path = ''

                def open(self, path):
                    self.opened = True
                    self.path = path
                    self.state = 'stopped'
                    self.pos = 0

                def play(self):
                    self.state = 'playing'
                    self.started_at = time.monotonic()
                    played.append(Path(self.path).stem)

                def position(self):
                    if self.state == 'playing':
                        self.pos = min(50, int((time.monotonic() - self.started_at) * 1000))
                        if self.pos == 50:
                            self.state = 'stopped'
                    return self.pos

                def mode(self):
                    self.position()
                    return self.state

                def stop(self):
                    self.state = 'stopped'
                    self.pos = 0

                def pause(self):
                    self.state = 'paused'

                def resume(self):
                    self.state = 'playing'

                def close(self):
                    self.opened = False

            def decode(path):
                decoded_paths.append(path.name)
                if scenario == 'stop_during_load':
                    time.sleep(.2)
                return types.SimpleNamespace(digest=path.stem, data=b'ogg', seconds=.05,
                                             rate=44100, channels=2), {}

            def widgets(root):
                out = [root]
                for child in root.winfo_children():
                    out.extend(widgets(child))
                return out

            original_loop = tk.Tk.mainloop

            def test_loop(root, *args, **kwargs):
                nonlocal finished
                roots.append(root)
                root.withdraw()
                controls = {str(w.cget('text')): w for w in widgets(root) if isinstance(w, ttk.Button)}
                checkbox = next(w for w in widgets(root) if isinstance(w, ttk.Checkbutton))
                self.assertEqual(root.getvar(str(checkbox.cget('variable'))), 1)
                controls['Mở thư mục…'].invoke()
                if scenario == 'disabled':
                    checkbox.invoke()
                start = time.monotonic()
                stopped = False
                added = False

                def drive():
                    nonlocal finished, stopped, added
                    try:
                        elapsed = time.monotonic() - start
                        if scenario == 'added_at_end' and played and not added:
                            (folder / 'b.tbm').write_bytes(b'new-patch')
                            added = True
                        if scenario == 'folder_poll' and elapsed > .1 and not added:
                            (folder / 'b.tbm').write_bytes(b'new-patch')
                            added = True
                        if scenario == 'manual_stop' and played and not stopped:
                            controls['Dừng'].invoke()
                            stopped = True
                        if elapsed > (3.5 if scenario == 'folder_poll' else 1.25):
                            expected = ['a', 'b'] if scenario in ('automatic', 'added_at_end') else ([] if scenario in ('stop_during_load', 'folder_poll') else ['a'])
                            self.assertEqual(played, expected)
                            if scenario == 'folder_poll':
                                self.assertEqual(decoded_paths, [])
                                view = next(w for w in widgets(root) if isinstance(w, ttk.Treeview))
                                self.assertEqual([view.item(i)['values'][0] for i in view.get_children()], ['a.tbm', 'b.tbm'])
                            self.assertFalse(failures)
                            finished = True
                            for timer in root.tk.call('after', 'info'):
                                root.after_cancel(timer)
                            root.destroy()
                            return
                        root.after(10, drive)
                    except BaseException as e:
                        failures.append(e)
                        for timer in root.tk.call('after', 'info'):
                            root.after_cancel(timer)
                        root.destroy()

                if scenario != 'folder_poll':
                    controls['▶  Nghe'].invoke()
                if scenario == 'stop_during_load':
                    controls['Dừng'].invoke()
                root.after(10, drive)
                original_loop(root, *args, **kwargs)

            with patch.object(app, 'WavePlayer', FakePlayer), patch.object(app, 'decode_file', decode), \
                 patch.object(app, 'find_tool', return_value='fake-ffmpeg'), \
                 patch.object(app, 'export_audio', side_effect=lambda track, path, ffmpeg: Path(path).write_bytes(b'wav')), \
                 patch.object(filedialog, 'askdirectory', return_value=str(folder)), \
                 patch.object(messagebox, 'showerror', side_effect=lambda *args: failures.append(args)), \
                 patch.object(tk.Tk, 'mainloop', test_loop):
                app.gui()
        self.assertTrue(finished, repr(failures))
        self.assertFalse(failures)

    def test_automatic_next_and_stop_at_end(self):
        self.run_scenario('automatic')

    def test_manual_stop_does_not_advance(self):
        self.run_scenario('manual_stop')

    def test_checkbox_disables_auto_next(self):
        self.run_scenario('disabled')

    def test_stop_during_loading_does_not_start_later(self):
        self.run_scenario('stop_during_load')

    def test_new_file_is_available_at_auto_advance_without_waiting_for_poll(self):
        self.run_scenario('added_at_end')

    def test_directory_refresh_does_not_decode_files(self):
        self.run_scenario('folder_poll')


class CacheTests(unittest.TestCase):
    def test_replacement_with_preserved_size_and_timestamp_is_not_stale(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'song.tbm'
            path.write_bytes(b'old')
            info = path.stat()
            cache = app.DecodedTrackCache()
            self.assertEqual(cache.get(path, lambda p: p.read_bytes()), b'old')
            path.write_bytes(b'new')
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
            self.assertEqual(cache.get(path, lambda p: p.read_bytes()), b'new')

    def test_updated_file_is_decoded_again(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'song.tbm'
            path.write_bytes(b'old')
            cache = app.DecodedTrackCache()
            calls = []
            def loader(p):
                calls.append(p)
                return p.read_bytes()
            self.assertEqual(cache.get(path, loader), b'old')
            self.assertEqual(cache.get(path, loader), b'old')
            self.assertEqual(len(calls), 1)
            path.write_bytes(b'new revision')
            self.assertEqual(cache.get(path, loader), b'new revision')
            self.assertEqual(len(calls), 2)
            self.assertEqual(len(cache.entries), 1)

    def test_file_changed_mid_decode_is_not_cached(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'song.tbm'
            path.write_bytes(b'old')
            cache = app.DecodedTrackCache()
            def loader(p):
                p.write_bytes(b'new revision')
                return b'stale audio'
            with self.assertRaises(app.FileChangedError):
                cache.get(path, loader)
            self.assertFalse(cache.entries)

    def test_decode_failure_during_update_is_reported_as_file_change(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'song.tbm'
            path.write_bytes(b'partial')
            cache = app.DecodedTrackCache()
            def loader(p):
                p.write_bytes(b'complete new revision')
                raise app.ExportError('partial stream')
            with self.assertRaises(app.FileChangedError):
                cache.get(path, loader)
            self.assertFalse(cache.entries)


if __name__ == '__main__':
    unittest.main(verbosity=2)

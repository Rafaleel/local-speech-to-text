import socket
import threading
import time
from typing import Callable, Optional
from PySide6.QtCore import QObject, Signal

try:
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except Exception as e:
    PYNPUT_AVAILABLE = False
    keyboard = None
    print(f"[HotkeyListener] Warning importing pynput: {e}", flush=True)


class GlobalHotkeyListener(QObject):
    start_recording_signal = Signal()
    stop_recording_signal = Signal()
    cancel_recording_signal = Signal()

    def __init__(
        self,
        on_start_recording: Optional[Callable[[], None]] = None,
        on_stop_recording: Optional[Callable[[], None]] = None,
        on_cancel_recording: Optional[Callable[[], None]] = None,
        mode: str = "toggle",
        combination_str: str = "<ctrl>+<space>"
    ):
        """
        :param mode: 'toggle' or 'hold' (hold key while talking)
        :param combination_str: Key combination in pynput format
        """
        super().__init__()
        if on_start_recording:
            self.start_recording_signal.connect(on_start_recording)
        if on_stop_recording:
            self.stop_recording_signal.connect(on_stop_recording)
        if on_cancel_recording:
            self.cancel_recording_signal.connect(on_cancel_recording)

        self.mode = mode

        self.combination_str = combination_str

        self.is_recording = False
        self._listener: Optional[keyboard.Listener] = None
        self.current_keys = set()
        self._toggle_key_latched = False
        self._hold_stop_timer: Optional[threading.Timer] = None

        # UDP socket server for Wayland compatibility
        self._udp_thread = None
        self._udp_socket = None
        self._udp_running = False
        self._last_udp_toggle_time = 0.0

        # Parse combination into target key objects
        self.target_key_groups = self._parse_combination(combination_str)
        self.target_keys_flat = set().union(
            *self.target_key_groups) if self.target_key_groups else set()

    def _parse_combination(self, combo: str) -> list:
        groups = []
        if not PYNPUT_AVAILABLE or keyboard is None:
            return groups
        parts = combo.lower().split('+')
        for p in parts:
            p = p.strip()
            group = set()
            if p in ('<ctrl>', 'ctrl'):
                group.add(keyboard.Key.ctrl)
                group.add(keyboard.Key.ctrl_l)
                group.add(keyboard.Key.ctrl_r)
            elif p in ('<alt>', 'alt'):
                group.add(keyboard.Key.alt)
                group.add(keyboard.Key.alt_l)
                group.add(keyboard.Key.alt_r)
            elif p in ('<shift>', 'shift'):
                group.add(keyboard.Key.shift)
                group.add(keyboard.Key.shift_l)
                group.add(keyboard.Key.shift_r)
            elif p in ('<space>', 'space'):
                group.add(keyboard.Key.space)
            else:
                try:
                    group.add(keyboard.KeyCode.from_char(p))
                except Exception:
                    pass
            if group:
                groups.append(group)
        return groups

    def _is_combination_pressed(self) -> bool:
        if not self.target_key_groups:
            return False

        for group in self.target_key_groups:
            if not group.intersection(self.current_keys):
                return False

        return True

    def _cancel_hold_stop_timer(self):
        if self._hold_stop_timer is not None:
            try:
                self._hold_stop_timer.cancel()
            except Exception:
                pass
            self._hold_stop_timer = None

    def _trigger_start(self):
        if not self.is_recording:
            self.is_recording = True
            print("[HotkeyListener] Emitting START signal", flush=True)
            self.start_recording_signal.emit()

    def _trigger_stop(self):
        if self.is_recording:
            self.is_recording = False
            print("[HotkeyListener] Emitting STOP signal", flush=True)
            self.stop_recording_signal.emit()

    def _trigger_cancel(self):
        if self.is_recording:
            self._cancel_hold_stop_timer()
            self.is_recording = False
            self._toggle_key_latched = False
            print("[HotkeyListener] Emitting CANCEL signal", flush=True)
            self.cancel_recording_signal.emit()

    def _on_press(self, key):
        if key == keyboard.Key.esc and self.is_recording:
            self._trigger_cancel()
            return

        self.current_keys.add(key)

        if self._is_combination_pressed():

            if self.mode == "toggle":
                if not self._toggle_key_latched:
                    self._toggle_key_latched = True
                    if not self.is_recording:
                        self._trigger_start()
                    else:
                        self._trigger_stop()
            elif self.mode == "hold":
                self._cancel_hold_stop_timer()
                if not self.is_recording:
                    self._trigger_start()

    def _confirm_stop_hold(self):
        if self.mode == "hold" and self.is_recording:
            if not self._is_combination_pressed():
                self._trigger_stop()

    def _on_release(self, key):
        if key in self.current_keys:
            self.current_keys.remove(key)

        if not self._is_combination_pressed():
            self._toggle_key_latched = False

        if self.mode == "hold" and self.is_recording:
            if (
                key in self.target_keys_flat or
                not self._is_combination_pressed()
            ):
                self._cancel_hold_stop_timer()

                self._hold_stop_timer = threading.Timer(
                    0.20, self._confirm_stop_hold
                )
                self._hold_stop_timer.start()

    def start(self):
        self._start_udp_listener()

        if not PYNPUT_AVAILABLE or keyboard is None:
            print(
                "[HotkeyListener] pynput shortcuts disabled (Wayland). "
                "UDP listener active.",
                flush=True
            )
            return

        if self._listener is None:

            try:
                self._listener = keyboard.Listener(
                    on_press=self._on_press,
                    on_release=self._on_release
                )
                self._listener.start()
                print(
                    f"[HotkeyListener] Listener active in '{self.mode}' mode "
                    f"({self.combination_str})",
                    flush=True
                )
            except Exception as e:
                print(
                    f"[HotkeyListener] Warning: Unable to activate X11 "
                    f"global shortcuts: {e}",
                    flush=True
                )

    def _start_udp_listener(self):
        if self._udp_running:
            return
        self._udp_running = True
        self._udp_thread = threading.Thread(
            target=self._udp_listen_loop, daemon=True
        )
        self._udp_thread.start()

    def _udp_listen_loop(self):
        self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self._udp_socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            self._udp_socket.bind(("127.0.0.1", 15324))
            print(
                "[HotkeyListener] Listening for UDP commands on port 15324 "
                "(Wayland support)",
                flush=True
            )

        except Exception as e:
            print(
                f"[HotkeyListener] Failed to start UDP listener: {e}",
                flush=True
            )
            return

        self._udp_socket.settimeout(1.0)

        while self._udp_running:
            try:
                data, _ = self._udp_socket.recvfrom(1024)
                command = data.decode('utf-8').strip()
                if command == "TOGGLE":
                    if self.mode == "toggle":
                        now = time.time()
                        if now - self._last_udp_toggle_time < 0.4:
                            continue
                        self._last_udp_toggle_time = now
                        if not self.is_recording:
                            self._trigger_start()
                        else:
                            self._trigger_stop()
                    elif self.mode == "hold":
                        self._cancel_hold_stop_timer()
                        if not self.is_recording:
                            self._trigger_start()
                        self._hold_stop_timer = threading.Timer(
                            0.35, self._trigger_stop
                        )
                        self._hold_stop_timer.start()
                elif command == "START":
                    self._cancel_hold_stop_timer()
                    if not self.is_recording:
                        self._trigger_start()
                    if self.mode == "hold":
                        self._hold_stop_timer = threading.Timer(
                            0.35, self._trigger_stop
                        )
                        self._hold_stop_timer.start()
                elif command == "STOP":
                    self._cancel_hold_stop_timer()
                    if self.is_recording:
                        self._trigger_stop()
                elif command == "CANCEL":
                    self._trigger_cancel()

            except socket.timeout:
                continue
            except Exception:
                break

        if self._udp_socket:
            self._udp_socket.close()

    def stop(self):
        self._udp_running = False
        if self._udp_thread:
            self._udp_thread.join(timeout=2.0)

        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
            print("[HotkeyListener] pynput listener stopped.", flush=True)

    def set_mode(self, mode: str):
        self.mode = mode
        print(f"[HotkeyListener] Mode changed to '{self.mode}'", flush=True)

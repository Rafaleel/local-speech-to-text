import GLib from 'gi://GLib';
import Shell from 'gi://Shell';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const PILL_ROLE = 'voice-to-text-pill';
// Keep the blur inside the rounded edge of the client window.
const HORIZONTAL_INSET = 8;
const VERTICAL_INSET = 4;
const MAP_DELAY_MS = 400;

export default class VoiceToTextBackdrop extends Extension {
    enable() {
        this._windows = new Map();
        this._mapId = global.window_manager.connect('map', (_manager, actor) => {
            this._addBackdrop(actor);
        });
        this._overviewShowingId = Main.overview.connect('showing', () => {
            for (const entry of this._windows.values())
                entry.backdrop.hide();
        });
        this._overviewHiddenId = Main.overview.connect('hidden', () => {
            for (const entry of this._windows.values()) {
                if (!entry.timer)
                    entry.backdrop.show();
            }
        });
        for (const actor of global.get_window_actors())
            this._addBackdrop(actor);
    }

    disable() {
        global.window_manager.disconnect(this._mapId);
        Main.overview.disconnect(this._overviewShowingId);
        Main.overview.disconnect(this._overviewHiddenId);
        for (const [actor, entry] of this._windows) {
            actor.disconnect(entry.destroyId);
            this._disconnectWindow(entry);
            entry.backdrop.destroy();
        }
        this._windows.clear();
    }

    _addBackdrop(actor) {
        const existing = this._windows.get(actor);
        if (existing) {
            this._showAfterMap(existing);
            return;
        }

        const window = actor.meta_window;
        if (window?.get_role() !== PILL_ROLE)
            return;

        const surface = actor.get_first_child();
        if (!surface)
            return;

        const backdrop = new St.Widget({
            name: PILL_ROLE + '-backdrop',
            reactive: false,
            visible: false,
            x: HORIZONTAL_INSET,
            y: VERTICAL_INSET,
        });
        const updateSize = () => {
            const {width, height} = window.get_buffer_rect();
            backdrop.set_size(
                Math.max(1, width - 2 * HORIZONTAL_INSET),
                Math.max(1, height - 2 * VERTICAL_INSET)
            );
        };
        updateSize();
        backdrop.add_effect(new Shell.BlurEffect({
            mode: Shell.BlurMode.BACKGROUND,
            radius: 20,
            brightness: 1,
        }));
        actor.insert_child_below(backdrop, surface);

        const entry = {backdrop, window, timer: 0};
        entry.resizeId = window.connect('size-changed', updateSize);
        entry.destroyId = actor.connect('destroy', () => {
            this._disconnectWindow(entry);
            this._windows.delete(actor);
        });
        this._windows.set(actor, entry);
        this._showAfterMap(entry);
    }

    _showAfterMap(entry) {
        entry.backdrop.hide();
        if (entry.timer)
            GLib.source_remove(entry.timer);
        // The compositor can briefly give the opening window a zero-scale transform.
        entry.timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, MAP_DELAY_MS, () => {
            entry.timer = 0;
            if (!Main.overview.visible)
                entry.backdrop.show();
            return GLib.SOURCE_REMOVE;
        });
    }

    _disconnectWindow(entry) {
        if (entry.timer)
            GLib.source_remove(entry.timer);
        entry.window.disconnect(entry.resizeId);
    }
}

"""
BasaltDemo – a maximal‑feature showcase for rumps.

• nested menus, sub‑menus, and live‑updated menu titles
• keyboard shortcut (d) for Dashboard when the menu is open
• timers that update the menubar title and inject menu items
• notifications toggle
• dynamic theme picker
"""

import datetime, sys, os
import random
import itertools

import rumps
from AppKit import NSApplication, NSImage, NSApplicationActivationPolicyAccessory  # type: ignore[import]

# Hide Dock icon and App‑Switcher entry when running unbundled
NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)

def resource_path(filename: str) -> str:
    """
    Return an absolute path to an asset that works both in development
    and when bundled inside a .app (py2app / PyInstaller).
    """
    if getattr(sys, "frozen", False):  # Running from bundled executable
        base = os.path.dirname(sys.executable)
    else:  # Running from source
        base = os.path.dirname(__file__)
    return os.path.join(base, "assets", filename)

class BasaltDemoApp(rumps.App):
    def __init__(self):
        super().__init__("🪨BasaltDemo", icon=None)
        # Replace the default Python rocket icon in title‑bar windows
        try:
            app_icon_path = resource_path("icon_idle.png")  # use any 128×128+ PNG/ICNS you ship
            nsimg = NSImage.alloc().initWithContentsOfFile_(app_icon_path)
            if nsimg:
                NSApplication.sharedApplication().setApplicationIconImage_(nsimg)
        except Exception as e:
            print("Could not set app icon:", e)

        # ── Build root‑level menu items first ──────────────────────────────────
        dashboard_item = rumps.MenuItem("Dashboard", callback=self.show_dashboard, key='d')
        settings_menu  = rumps.MenuItem("Settings")
        advanced_menu  = rumps.MenuItem("Advanced")
        quote_item     = rumps.MenuItem("Random Quote", callback=self.show_quote)
        timer_item     = rumps.MenuItem("Toggle Timer", callback=self.toggle_timer)
        quit_item      = rumps.MenuItem("Quit", callback=rumps.quit_application)

        self.menu = [
            dashboard_item,
            settings_menu,
            advanced_menu,
            None,
            quote_item,
            timer_item,
            None,
            quit_item,
        ]

        enable_notif = rumps.MenuItem("Enable Notifications", callback=self.toggle_notifications, key="n")
        theme_menu   = rumps.MenuItem("Theme")

        settings_menu.submenu = [
            enable_notif,
            theme_menu,
        ]
        enable_notif.state = 1

        theme_menu.submenu = [
            rumps.MenuItem("Light", callback=lambda _: self.set_theme("light")),
            rumps.MenuItem("Dark", callback=lambda _: self.set_theme("dark")),
        ]

        debug_item  = rumps.MenuItem("Debug Mode", callback=self.toggle_debug, key='d')
        change_icon = rumps.MenuItem("Change Icon", callback=self.cycle_icon, key='i')
        links_menu  = rumps.MenuItem("Links")

        advanced_menu.submenu = [
            debug_item,
            change_icon,
            links_menu,
        ]
        debug_item.state = 0

        links_menu.submenu = [
            rumps.MenuItem("Open Basalt Site", callback=lambda _: self.open_url("https://example.com")),
            rumps.MenuItem("GitHub Repo", callback=lambda _: self.open_url("https://github.com/yourname/basalt")),
        ]

        # ── Background timer that fires every 5 s ───────────────────────────────
        self.timer = rumps.Timer(self._tick, 5)
        self.timer.start()

        # Store mutable state
        self.notifications_enabled = True
        self.counter = 0
        self.debug = False

        # Set up icon cycle
        try:
            self._icons = itertools.cycle([None, resource_path("icon_idle.png"), resource_path("icon_alert.png")])
        except Exception:
            self._icons = itertools.cycle([None])

    # ─────────────────────── Callbacks ─────────────────────────────────────────

    def show_dashboard(self, _=None):
        """Popup window summarising current state."""
        # Bring app to foreground so the window isn’t hidden behind others
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        now = datetime.datetime.now().strftime("%Y‑%m‑%d %H:%M:%S")
        text = f"Counter: {self.counter}\nCurrent time: {now}"
        window = rumps.Window(
            message=text,
            title="Basalt Dashboard",
            default_text="Write a note here...",
            ok="Save Note",
            cancel="Dismiss",
            dimensions=(320, 120),
        )
        response = window.run()
        if response.clicked:
            rumps.alert(f"Note saved:\n{response.text}")
    def toggle_debug(self, sender):
        sender.state = int(not sender.state)
        self.debug = bool(sender.state)
        rumps.notification("Debug", f"Debug mode {'ON' if self.debug else 'OFF'}", "", sound=True)

    def cycle_icon(self, _):
        try:
            self.icon = next(self._icons)
        except Exception:
            self.icon = None

    def open_url(self, url: str):
        self.open(url)

    def show_quote(self, _):
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        quote = random.choice(
            [
                "Stay hungry.",
                "Rock solid.",
                "Stone by stone.",
                "Keep building.",
                "Geology rocks!",
            ]
        )
        rumps.alert(title="Random Quote", message=quote)

    def toggle_notifications(self, sender):
        # MenuItem.state is 0 or 1
        sender.state = int(not sender.state)
        self.notifications_enabled = bool(sender.state)

    def toggle_timer(self, sender):
        sender.state = int(not sender.state)
        if sender.state:
            self.timer.start()
        else:
            self.timer.stop()

    def set_theme(self, theme):
        # Placeholder – swap icons or colours here
        rumps.notification("Theme changed", "", theme.capitalize())

    # ─────────────────────── Timer handler ────────────────────────────────────

    def _tick(self, _):
        self.counter += 1

        # Update menubar title live
        prefix = "[DBG] " if self.debug else ""
        self.title = f"{prefix}🪨{self.counter}"

        # Every 10 ticks, insert a new menu item just after "Random Quote"
        if self.counter % 10 == 0:
            item_title = f"Snapshot {self.counter}"
            # insert after the item whose title is "Random Quote"
            self.menu.insert_after(
                "Random Quote", rumps.MenuItem(item_title)
            )

            if self.notifications_enabled:
                rumps.notification("Snapshot Added", "", item_title)


if __name__ == "__main__":
    BasaltDemoApp().run()

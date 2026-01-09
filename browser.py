import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, Gio, Gdk, Soup
from gi.repository import Pango
from gi.repository import GLib
import json
import os

class ASGBrowser(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_default_size(1100, 650)
        self.set_title("ASG Browser")

        # Setup WebsiteDataManager (untuk localStorage, IndexedDB, cache, dll)
        self.data_manager = self.get_data_manager()

        # >>> AKTIFKAN PENYIMPANAN COOKIE PERMANEN <<<
        self.setup_persistent_cookies()

        # Daftar bookmark (disimpan di memori)
        self.bookmarks = []

        # Homepage default
        self.homepage_html = self.get_default_homepage()

        # ================= HEADER BAR =================
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        self.set_titlebar(header)

        self.stack_switcher = Gtk.StackSwitcher()
        self.stack_switcher.set_hexpand(True)
        header.set_custom_title(self.stack_switcher)

        self.btn_new_tab = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        self.btn_new_tab.set_relief(Gtk.ReliefStyle.NONE)
        self.btn_new_tab.set_tooltip_text("Tab baru")
        self.btn_new_tab.connect("clicked", self.new_tab)
        header.pack_end(self.btn_new_tab)

        # ================= MAIN LAYOUT =================
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        # ================= TOOLBAR =================
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)
        vbox.pack_start(toolbar, False, False, 0)

        self.btn_back = Gtk.Button.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON)
        self.btn_back.set_tooltip_text("Kembali")
        self.btn_back.connect("clicked", self.go_back)
        toolbar.pack_start(self.btn_back, False, False, 0)

        self.btn_forward = Gtk.Button.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON)
        self.btn_forward.set_tooltip_text("Maju")
        self.btn_forward.connect("clicked", self.go_forward)
        toolbar.pack_start(self.btn_forward, False, False, 0)

        self.btn_reload = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        self.btn_reload.set_tooltip_text("Reload")
        self.btn_reload.connect("clicked", self.reload_page)
        toolbar.pack_start(self.btn_reload, False, False, 0)

        self.btn_home = Gtk.Button.new_from_icon_name("go-home-symbolic", Gtk.IconSize.BUTTON)
        self.btn_home.set_tooltip_text("Home")
        self.btn_home.connect("clicked", self.go_home)
        toolbar.pack_start(self.btn_home, False, False, 0)

        self.url_entry = Gtk.Entry()
        self.url_entry.set_placeholder_text("Masukkan URL lalu tekan Enter")
        self.url_entry.connect("activate", self.load_url)
        toolbar.pack_start(self.url_entry, True, True, 0)

        # Tombol menu (⋮)
        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.BUTTON))
        menu_btn.set_relief(Gtk.ReliefStyle.NONE)
        menu_btn.set_tooltip_text("Menu")
        menu = Gio.Menu()
        menu.append("Add To Bookmark", "app.add_bookmark")
        menu.append("Bookmark List", "app.bookmark_list")
        menu.append("Pengaturan", "app.settings")
        menu.append("Tentang", "app.about")
        menu_btn.set_menu_model(menu)
        toolbar.pack_start(menu_btn, False, False, 0)

        # Action group
        actions = Gio.SimpleActionGroup()
        add_bookmark_action = Gio.SimpleAction.new("add_bookmark", None)
        add_bookmark_action.connect("activate", self.on_add_bookmark)
        actions.add_action(add_bookmark_action)

        bookmark_list_action = Gio.SimpleAction.new("bookmark_list", None)
        bookmark_list_action.connect("activate", self.on_bookmark_list)
        actions.add_action(bookmark_list_action)

        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self.on_settings)
        actions.add_action(settings_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about)
        actions.add_action(about_action)

        self.insert_action_group("app", actions)

        # ================= PROGRESS BAR =================
        self.progress = Gtk.ProgressBar()
        self.progress.set_visible(False)
        vbox.pack_start(self.progress, False, False, 0)

        # ================= STACK =================
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack_switcher.set_stack(self.stack)
        vbox.pack_start(self.stack, True, True, 0)

        # Tab pertama
        self.new_tab()

        self.connect("destroy", Gtk.main_quit)
        self.show_all()

    def get_data_manager(self):
        base_dir = os.path.join(GLib.get_user_data_dir(), "asg-browser")
        os.makedirs(base_dir, exist_ok=True)
        return WebKit2.WebsiteDataManager(
            base_data_directory=base_dir,
            base_cache_directory=os.path.join(base_dir, "cache")
        )

    def setup_persistent_cookies(self):
        """Aktifkan penyimpanan cookie permanen agar login tetap bertahan"""
        cookie_manager = self.data_manager.get_cookie_manager()

        # Pilih salah satu format penyimpanan:
        # 1. TEXT (mudah dibaca, cocok untuk debug)
        # 2. SQLITE (lebih efisien untuk jumlah cookie banyak)

        cookie_file = os.path.join(
            self.data_manager.get_base_data_directory(),
            "cookies.txt"   # atau "cookies.sqlite" jika pakai SQLITE
        )

        cookie_manager.set_persistent_storage(
            cookie_file,
            WebKit2.CookiePersistentStorage.TEXT   # ganti ke .SQLITE jika ingin
        )

        # Izinkan semua cookie (termasuk third-party jika situs butuh)
        # Alternatif: Soup.CookieJarAcceptPolicy.NO_THIRD_PARTY untuk lebih aman
        cookie_manager.set_accept_policy(Soup.CookieJarAcceptPolicy.ALWAYS)

        print(f"Cookie disimpan permanen di: {cookie_file}")

    def get_default_homepage(self):
        return """
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {
                    font-family: sans-serif;
                    text-align: center;
                    margin: 0;
                    padding: 0;
                    height: 100vh;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    background: #f9f9f9;
                    color: #333;
                }
                h1 { font-size: 3em; margin-bottom: 0.2em; }
                p { font-size: 1.3em; color: #666; }
            </style>
        </head>
        <body>
            <h1>Selamat Datang di ASG Browser</h1>
            <p>Tab baru siap digunakan. Ketik alamat di address bar untuk memulai browsing.</p>
        </body>
        </html>
        """

    # ================= TAB MANAGEMENT =================
    def new_tab(self, *_):
        webview = self.create_webview()

        tab_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tab_box.set_margin_start(4)
        tab_box.set_margin_end(4)

        label = Gtk.Label(label="New Tab")
        label.set_ellipsize(Pango.EllipsizeMode.END)
        tab_box.pack_start(label, True, True, 0)

        close_btn = Gtk.Button()
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.add(Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.SMALL_TOOLBAR))
        close_btn.set_tooltip_text("Tutup tab")
        close_btn.connect("clicked", self.close_tab, webview)
        tab_box.pack_start(close_btn, False, False, 0)

        tab_box.show_all()

        self.stack.add_titled(webview, str(id(webview)), "New Tab")
        self.stack.child_set_property(webview, "title", "New Tab")
        self.stack.child_set_property(webview, "tab", tab_box)

        webview.connect("notify::title", self.on_title_changed, label)
        self.stack.set_visible_child(webview)
        self.load_start_page(webview)

    def close_tab(self, button, webview):
        self.stack.remove(webview)
        if self.stack.get_visible_child() is None:
            self.new_tab()

    def get_current_webview(self):
        return self.stack.get_visible_child()

    def on_title_changed(self, webview, param, label_widget):
        title = webview.get_title() or "New Tab"
        label_widget.set_text(title)
        self.stack.child_set_property(webview, "title", title)

    # ================= WEBVIEW =================
    def create_webview(self):
        context = WebKit2.WebContext.new_with_website_data_manager(self.data_manager)
        webview = WebKit2.WebView.new_with_context(context)

        webview.connect("load-changed", self.on_load_changed)
        webview.connect("notify::estimated-load-progress", self.on_progress_changed)
        webview.connect("context-menu", self.on_context_menu)
        webview.show()
        return webview

    def on_context_menu(self, webview, context_menu, event, hit_test_result):
        if hit_test_result.context_is_link():
            link_uri = hit_test_result.get_link_uri()
            action_name = f"open-link-new-tab-{id(webview)}"
            action = Gio.SimpleAction.new(action_name, None)
            action.connect("activate", lambda a, p, url=link_uri: self.open_link_in_new_tab(url))
            new_tab_item = WebKit2.ContextMenuItem.new_from_gaction(
                action, "Buka Link di Tab Baru", None
            )
            separator = WebKit2.ContextMenuItem.new_separator()
            context_menu.prepend(separator)
            context_menu.prepend(new_tab_item)
        return False

    def open_link_in_new_tab(self, url):
        if not url:
            return
        self.new_tab()
        current_webview = self.get_current_webview()
        if current_webview:
            current_webview.load_uri(url)

    # ================= NAVIGATION =================
    def load_start_page(self, webview):
        webview.load_html(self.homepage_html, "file:///")

    def load_url(self, entry):
        url = entry.get_text().strip()
        if not url:
            return
        if not url.startswith(("http://", "https://", "file://")):
            if " " in url:
                url = "https://www.google.com/search?q=" + url.replace(" ", "+")
            else:
                url = "https://" + url
        webview = self.get_current_webview()
        if webview:
            webview.load_uri(url)

    def go_back(self, *_):
        w = self.get_current_webview()
        if w and w.can_go_back():
            w.go_back()

    def go_forward(self, *_):
        w = self.get_current_webview()
        if w and w.can_go_forward():
            w.go_forward()

    def reload_page(self, *_):
        w = self.get_current_webview()
        if w:
            w.reload()

    def go_home(self, *_):
        w = self.get_current_webview()
        if w:
            self.load_start_page(w)

    # ================= EVENTS =================
    def on_load_changed(self, webview, event):
        if event == WebKit2.LoadEvent.STARTED:
            self.progress.set_visible(True)
        elif event == WebKit2.LoadEvent.FINISHED:
            self.progress.set_visible(False)
            if webview == self.get_current_webview():
                uri = webview.get_uri() or ""
                if uri.startswith("file://"):
                    self.url_entry.set_text("")
                else:
                    self.url_entry.set_text(uri)

    def on_progress_changed(self, webview, pspec):
        self.progress.set_fraction(webview.get_estimated_load_progress())

    # ================= MENU ACTIONS =================
    def on_add_bookmark(self, action, param):
        webview = self.get_current_webview()
        if webview:
            title = webview.get_title() or "Tanpa Judul"
            uri = webview.get_uri() or ""
            if uri.startswith("file://"):
                uri = ""
            if uri and not any(b['url'] == uri for b in self.bookmarks):
                self.bookmarks.append({"title": title, "url": uri})
                self.show_info_dialog("Bookmark ditambahkan!", f"{title}\n{uri}")
            elif uri:
                self.show_info_dialog("Informasi", "Halaman ini sudah ada di bookmark.")

    def on_bookmark_list(self, action, param):
        dialog = Gtk.Dialog(title="Daftar Bookmark", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dialog.set_default_size(600, 400)

        scrolled = Gtk.ScrolledWindow()
        dialog.get_content_area().add(scrolled)
        listbox = Gtk.ListBox()
        scrolled.add(listbox)

        if not self.bookmarks:
            label = Gtk.Label(label="Belum ada bookmark.")
            label.set_padding(20, 20)
            listbox.add(label)
        else:
            for bm in self.bookmarks:
                row = self._create_bookmark_row(bm, listbox)
                listbox.add(row)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _create_bookmark_row(self, bm, listbox):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_margin_start(10)
        row.set_margin_end(10)
        row.set_margin_top(5)
        row.set_margin_bottom(5)

        label = Gtk.Label(label=f"<b>{bm['title']}</b>\n<small>{bm['url']}</small>")
        label.set_use_markup(True)
        label.set_halign(Gtk.Align.START)
        row.pack_start(label, True, True, 0)

        btn_open = Gtk.Button.new_with_label("Buka")
        btn_open.connect("clicked", lambda w, url=bm['url']: self.open_bookmark(url))
        row.pack_end(btn_open, False, False, 0)

        btn_del = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON)
        btn_del.connect("clicked", lambda w, item=bm: self.delete_bookmark(item, listbox))
        row.pack_end(btn_del, False, False, 0)

        return row

    def open_bookmark(self, url):
        self.new_tab()
        current = self.get_current_webview()
        if current:
            current.load_uri(url)

    def delete_bookmark(self, bookmark_item, listbox):
        self.bookmarks.remove(bookmark_item)
        for child in listbox.get_children():
            listbox.remove(child)
        for bm in self.bookmarks:
            row = self._create_bookmark_row(bm, listbox)
            listbox.add(row)
        listbox.show_all()

    def on_settings(self, action, param):
        dialog = Gtk.Dialog(title="Pengaturan", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OK, Gtk.ResponseType.OK)
        dialog.set_default_size(400, 200)

        grid = Gtk.Grid()
        grid.set_margin_start(20)
        grid.set_margin_end(20)
        grid.set_margin_top(20)
        grid.set_margin_bottom(20)
        grid.set_row_spacing(10)
        grid.set_column_spacing(10)
        dialog.get_content_area().add(grid)

        label = Gtk.Label(label="Homepage kustom (kosongkan untuk default):")
        label.set_halign(Gtk.Align.START)
        grid.attach(label, 0, 0, 2, 1)

        entry = Gtk.Entry()
        grid.attach(entry, 0, 1, 2, 1)

        dialog.show_all()
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            custom_html = entry.get_text().strip()
            self.homepage_html = custom_html if custom_html else self.get_default_homepage()
            self.show_info_dialog("Pengaturan disimpan", "Homepage telah diperbarui.")
        dialog.destroy()

    def on_about(self, action, param):
        about_dialog = Gtk.AboutDialog()
        about_dialog.set_transient_for(self)
        about_dialog.set_modal(True)
        about_dialog.set_program_name("ASG Browser")
        about_dialog.set_version("1.0")
        about_dialog.set_copyright("© 2026 ASG Browser")
        about_dialog.set_comments("Browser ringan dan sederhana berbasis WebKitGTK.\nDibuat dengan Python dan PyGObject.")
        about_dialog.set_website("https://github.com/alisitaDEV/asg-browser-py")
        about_dialog.set_authors(["M Ali Muhsinin"])
        about_dialog.set_logo_icon_name("web-browser-symbolic")
        about_dialog.run()
        about_dialog.destroy()

    def show_info_dialog(self, title, message):
        dlg = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dlg.format_secondary_text(message)
        dlg.run()
        dlg.destroy()


if __name__ == "__main__":
    ASGBrowser()
    Gtk.main()

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2, Gio, Gdk, Soup, GLib, Pango
import os
import json  

class ASGBrowser(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_default_size(1100, 650)
        self.set_title("ASG Browser Pro")

        # 1. Setup Data Manager & Persistent Storage
        base_dir = os.path.join(GLib.get_user_data_dir(), "asg-browser")
        os.makedirs(base_dir, exist_ok=True)
        self.data_manager = WebKit2.WebsiteDataManager(
            base_data_directory=base_dir,
            base_cache_directory=os.path.join(base_dir, "cache"),
            local_storage_directory=os.path.join(base_dir, "localstorage"),
            indexeddb_directory=os.path.join(base_dir, "indexeddb")
        )
        
        # Lokasi file bookmark
        self.bookmarks_file = os.path.join(base_dir, "bookmarks.json")
        
        self.setup_persistent_cookies()
        self.load_bookmarks() # Memuat bookmark dari file saat startup
        self.homepage_html = self.get_default_homepage()

        # 2. Header Bar Setup
        header = Gtk.HeaderBar()
        header.set_show_close_button(True)
        self.set_titlebar(header)

        self.stack_switcher = Gtk.StackSwitcher()
        header.set_custom_title(self.stack_switcher)

        self.btn_new_tab = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.BUTTON)
        self.btn_new_tab.connect("clicked", self.new_tab)
        header.pack_end(self.btn_new_tab)

        # 3. Main Layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)

        # Toolbar
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(6)
        toolbar.set_margin_bottom(6)
        vbox.pack_start(toolbar, False, False, 0)

        # Nav Buttons
        for icon, cmd in [("go-previous-symbolic", self.go_back), 
                          ("go-next-symbolic", self.go_forward),
                          ("view-refresh-symbolic", self.reload_page),
                          ("go-home-symbolic", self.go_home)]:
            btn = Gtk.Button.new_from_icon_name(icon, Gtk.IconSize.BUTTON)
            btn.connect("clicked", cmd)
            toolbar.pack_start(btn, False, False, 0)

        self.url_entry = Gtk.Entry()
        self.url_entry.connect("activate", self.load_url)
        toolbar.pack_start(self.url_entry, True, True, 0)

        # --- MENU TITIK TIGA ---
        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.BUTTON))
        menu_btn.set_relief(Gtk.ReliefStyle.NONE)
        
        menu = Gio.Menu()
        menu.append("Tambah Bookmark", "app.add_bookmark")
        menu.append("Daftar Bookmark", "app.bookmark_list")
        menu.append("Pengaturan", "app.settings")
        menu.append("Tentang", "app.about")
        menu_btn.set_menu_model(menu)
        toolbar.pack_start(menu_btn, False, False, 0)

        self.setup_actions()

        # Progress Bar & Stack
        self.progress = Gtk.ProgressBar()
        self.progress.set_visible(False)
        vbox.pack_start(self.progress, False, False, 0)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack_switcher.set_stack(self.stack)
        vbox.pack_start(self.stack, True, True, 0)

        self.new_tab()
        self.connect("destroy", Gtk.main_quit)
        self.show_all()

    # --- PENGEMBANGAN SISTEM BOOKMARK ---
    def load_bookmarks(self):
        """Memuat daftar bookmark dari file JSON."""
        if os.path.exists(self.bookmarks_file):
            try:
                with open(self.bookmarks_file, 'r') as f:
                    self.bookmarks = json.load(f)
            except Exception:
                self.bookmarks = []
        else:
            self.bookmarks = []

    def save_bookmarks(self):
        """Menyimpan daftar bookmark ke file JSON."""
        try:
            with open(self.bookmarks_file, 'w') as f:
                json.dump(self.bookmarks, f, indent=4)
        except Exception as e:
            print(f"Gagal menyimpan bookmark: {e}")

    def on_add_bookmark(self, action, param):
        webview = self.get_current_webview()
        uri = webview.get_uri()
        if uri and not uri.startswith("file://"):
            # Cek apakah sudah ada untuk menghindari duplikat
            if not any(bm['url'] == uri for bm in self.bookmarks):
                self.bookmarks.append({"title": webview.get_title(), "url": uri})
                self.save_bookmarks() # Simpan ke disk
                self.show_info_dialog("Sukses", "Bookmark disimpan permanen")
            else:
                self.show_info_dialog("Info", "Halaman ini sudah ada di bookmark")

    def on_bookmark_list(self, action, param):
        # Membuat jendela pop-up baru
        dialog = Gtk.Dialog(title="Daftar Bookmark", transient_for=self, flags=0)
        dialog.add_buttons(Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE)
        dialog.set_default_size(500, 450) # Ukuran default diperbesar sedikit

        # Container ScrolledWindow
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        # --- PERBAIKAN UTAMA DI SINI ---
        scrolled.set_vexpand(True)  # Memaksa scrollbar mengambil ruang vertikal yang tersisa
        scrolled.set_hexpand(True)  # Memaksa scrollbar mengambil ruang horizontal yang tersisa
        scrolled.set_propagate_natural_height(True) # Memastikan konten tidak terpotong
        # -------------------------------

        # Masukkan scrolled ke area konten dialog dengan opsi 'expand' True
        content_area = dialog.get_content_area()
        content_area.pack_start(scrolled, True, True, 0)

        # ListBox untuk menampung baris bookmark
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.add(listbox)

        if not self.bookmarks:
            label = Gtk.Label(label="Belum ada bookmark.")
            label.set_margin_top(20)
            listbox.add(label)
        else:
            for bm in self.bookmarks:
                row = Gtk.ListBoxRow()
                hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                hbox.set_border_width(10)
                row.add(hbox)

                # Label Judul & URL
                vbox_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                
                # Tambahkan judul dengan pembatasan karakter agar tidak merusak layout
                clean_title = (bm['title'][:50] + '..') if len(bm['title']) > 50 else bm['title']
                title_lbl = Gtk.Label(label=f"<b>{clean_title}</b>")
                title_lbl.set_use_markup(True)
                title_lbl.set_xalign(0)
                
                url_lbl = Gtk.Label(label=f"<span color='gray' size='small'>{bm['url']}</span>")
                url_lbl.set_use_markup(True)
                url_lbl.set_xalign(0)
                url_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                url_lbl.set_max_width_chars(40) # Mencegah URL memanjangkan jendela secara berlebih
                
                vbox_text.pack_start(title_lbl, False, False, 0)
                vbox_text.pack_start(url_lbl, False, False, 0)
                hbox.pack_start(vbox_text, True, True, 0)

                # Tombol Aksi (Buka & Hapus)
                btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                
                btn_open = Gtk.Button.new_from_icon_name("document-open-symbolic", Gtk.IconSize.BUTTON)
                btn_open.connect("clicked", lambda w, url=bm['url']: self._open_bookmark(url, dialog))
                
                btn_del = Gtk.Button.new_from_icon_name("edit-delete-symbolic", Gtk.IconSize.BUTTON)
                btn_del.connect("clicked", lambda w, b=bm: self._delete_bookmark(b, dialog))
                
                btn_box.pack_start(btn_open, False, False, 0)
                btn_box.pack_start(btn_del, False, False, 0)
                hbox.pack_end(btn_box, False, False, 0)

                listbox.add(row)

        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def _delete_bookmark(self, bookmark, dialog):
        if bookmark in self.bookmarks:
            self.bookmarks.remove(bookmark)
            self.save_bookmarks()
            dialog.destroy()
            self.on_bookmark_list(None, None) # Refresh list

    # --- Sisa Script Asli (Tidak Berubah) ---
    def setup_persistent_cookies(self):
        cookie_manager = self.data_manager.get_cookie_manager()
        cookie_file = os.path.join(self.data_manager.get_base_data_directory(), "cookies.sqlite")
        cookie_manager.set_persistent_storage(cookie_file, WebKit2.CookiePersistentStorage.SQLITE)
        cookie_manager.set_accept_policy(Soup.CookieJarAcceptPolicy.ALWAYS)

    def create_webview(self):
        context = WebKit2.WebContext.new_with_website_data_manager(self.data_manager)
        context.set_cache_model(WebKit2.CacheModel.WEB_BROWSER)
        context.set_process_model(WebKit2.ProcessModel.MULTIPLE_SECONDARY_PROCESSES)
        settings = WebKit2.Settings()
        settings.set_enable_webgl(True)
        settings.set_enable_accelerated_2d_canvas(True)
        settings.set_enable_smooth_scrolling(True)
        settings.set_javascript_can_open_windows_automatically(True)
        settings.set_user_agent("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        webview = WebKit2.WebView.new_with_context(context)
        webview.set_settings(settings)
        webview.connect("load-changed", self.on_load_changed)
        webview.connect("notify::estimated-load-progress", self.on_progress_changed)
        webview.show()
        return webview

    def setup_actions(self):
        actions = Gio.SimpleActionGroup()
        menu_items = [("add_bookmark", self.on_add_bookmark), ("bookmark_list", self.on_bookmark_list),
                      ("settings", self.on_settings), ("about", self.on_about)]
        for name, callback in menu_items:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            actions.add_action(action)
        self.insert_action_group("app", actions)

    def new_tab(self, *_):
        webview = self.create_webview()
        self.stack.add_titled(webview, str(id(webview)), "Tab Baru")
        webview.connect("notify::title", lambda w, p: self.update_tab_title(w))
        self.stack.set_visible_child(webview)
        self.load_start_page(webview)

    def update_tab_title(self, webview):
        title = webview.get_title() or "Tab Baru"
        self.stack.child_set_property(webview, "title", title[:15] + "..." if len(title) > 15 else title)

    def load_url(self, entry):
        url = entry.get_text().strip()
        if not url.startswith(("http", "file")):
            url = f"https://www.google.com/search?q={url}" if " " in url else f"https://{url}"
        self.get_current_webview().load_uri(url)

    def get_current_webview(self):
        return self.stack.get_visible_child()

    def go_back(self, *_): self.get_current_webview().go_back()
    def go_forward(self, *_): self.get_current_webview().go_forward()
    def reload_page(self, *_): self.get_current_webview().reload()
    def go_home(self, *_): self.load_start_page(self.get_current_webview())
    def load_start_page(self, webview): webview.load_html(self.homepage_html, "file:///")

    def on_load_changed(self, webview, event):
        if event == WebKit2.LoadEvent.FINISHED:
            self.progress.set_visible(False)
            if webview == self.get_current_webview():
                uri = webview.get_uri() or ""
                self.url_entry.set_text("" if uri.startswith("file://") else uri)
        elif event == WebKit2.LoadEvent.STARTED:
            self.progress.set_visible(True)

    def on_progress_changed(self, webview, pspec):
        self.progress.set_fraction(webview.get_estimated_load_progress())

    def _open_bookmark(self, url, dialog):
        webview = self.get_current_webview()
        if webview: webview.load_uri(url)
        dialog.destroy()

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
      about_dialog.set_version("1.1")
      about_dialog.set_copyright("© 2026 ASG Browser")
      about_dialog.set_comments("Browser ringan dan sederhana berbasis WebKitGTK.\nDibuat dengan Python dan PyGObject.")
      about_dialog.set_website("https://github.com/alisitaDEV/asg-browser-py")
      about_dialog.set_authors(["M Ali Muhsinin"])
      about_dialog.set_logo_icon_name("web-browser-symbolic")
      about_dialog.run()
      about_dialog.destroy()

    def show_info_dialog(self, title, message):
        dlg = Gtk.MessageDialog(transient_for=self, message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.OK, text=title)
        dlg.format_secondary_text(message)
        dlg.run()
        dlg.destroy()

    def get_default_homepage(self):
        return "<html><body style='background:#f9f9f9;text-align:center;padding-top:100px;font-family:sans-serif;'><h1>ASG Browser</h1><p>Browser sederhana, ringan dan cepat.</p></body></html>"

if __name__ == "__main__":
    app = ASGBrowser()
    Gtk.main()

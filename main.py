import requests
import time
import pandas as pd
import tkinter as tk
from tkinter import ttk, messagebox
import threading

PLAYER_ID_FILE = "player_ids.txt"
PLAYER_CSV_FILE = "players_data.csv"

# UI Color Theme
BG_DARK       = "#0d1117"
BG_CARD       = "#161b22"
BG_INPUT      = "#21262d"
ACCENT        = "#238636"
ACCENT_HOVER  = "#2ea043"
ACCENT2       = "#1f6feb"
ACCENT2_HOVER = "#388bfd"
TEXT_PRIMARY  = "#e6edf3"
TEXT_MUTED    = "#8b949e"
BORDER        = "#30363d"
ROW_ODD       = "#161b22"
ROW_EVEN      = "#1c2128"
ROW_SELECT    = "#1f4068"
HEADER_BG     = "#0d1117"

POSITION_ORDER = ["All", "Goalkeeper", "Defender", "Midfielder", "Forward"]
FILTER_W = 20

# Custom button implemented using Canvas to allow rounded corners and hover effects
class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, bg, hover_bg,
                 fg=TEXT_PRIMARY, radius=10, padx=14, pady=7,
                 font=("Segoe UI", 10, "bold"), **kwargs):
        super().__init__(parent, bg=parent["bg"], highlightthickness=0,
                         cursor="hand2", **kwargs)

        self._bg = bg
        self._hover_bg = hover_bg
        self._fg = fg
        self._radius = radius
        self._text = text
        self._command = command
        self._font = font
        self._padx = padx
        self._pady = pady
        self._enabled = True

        self._draw(bg)

        self.bind("<Enter>", lambda e: self._on_enter())
        self.bind("<Leave>", lambda e: self._on_leave())
        self.bind("<ButtonRelease-1>", lambda e: self._on_click())

    def _on_enter(self):
        if self._enabled:
            self._draw(self._hover_bg)

    def _on_leave(self):
        if self._enabled:
            self._draw(self._bg)

    def _on_click(self):
        if self._enabled:
            self._command()

    def _draw(self, color):
        self.delete("all")

        temp = self.create_text(0, 0, text=self._text, font=self._font, anchor="nw")
        bbox = self.bbox(temp)
        self.delete(temp)

        text_width = (bbox[2] - bbox[0]) if bbox else 80
        text_height = (bbox[3] - bbox[1]) if bbox else 14

        width = text_width + self._padx * 2
        height = text_height + self._pady * 2
        self.config(width=width, height=height)

        r = self._radius

        self.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=color, outline=color)
        self.create_arc(width-r*2, 0, width, r*2, start=0, extent=90, fill=color, outline=color)
        self.create_arc(0, height-r*2, r*2, height, start=180, extent=90, fill=color, outline=color)
        self.create_arc(width-r*2, height-r*2, width, height, start=270, extent=90, fill=color, outline=color)

        self.create_rectangle(r, 0, width-r, height, fill=color, outline=color)
        self.create_rectangle(0, r, width, height-r, fill=color, outline=color)

        self.create_text(width//2, height//2, text=self._text, fill=self._fg,
                         font=self._font, anchor="center")

    def config_state(self, state):
        self._enabled = (state == "normal")
        self._draw(self._bg if self._enabled else BORDER)

# Fetch all player IDs from the API and store them locally
def update_player_ids():
    def run():
        set_buttons_state("disabled")

        player_ids = set()
        page_num = 0
        max_pages = 1000

        progress_bar.config(mode="determinate", maximum=max_pages, value=0)
        show_progress(True)
        status_var.set("Fetching player IDs...")

        while True:
            url = f"https://footballapi.pulselive.com/football/stats/ranked/players/appearances?comps=1&page={page_num}"

            try:
                response = requests.get(url)
                if response.status_code != 200:
                    break

                data = response.json()
                content = data.get("stats", {}).get("content", [])

                if not content:
                    break

                for item in content:
                    pid = item.get("owner", {}).get("id")
                    if pid:
                        player_ids.add(int(pid))

                page_num += 1
                progress_bar["value"] = page_num
                status_var.set(f"Fetching page {page_num}... ({len(player_ids)} IDs)")
                root.update_idletasks()

                time.sleep(0.2)
                if page_num >= max_pages:
                    break

            except Exception as e:
                print(f"Error fetching page {page_num}: {e}")
                break

        # Save IDs
        with open(PLAYER_ID_FILE, "w") as f:
            for pid in sorted(player_ids):
                f.write(f"{pid}\n")

        show_progress(False)
        set_buttons_state("normal")
        status_var.set(f"Done - {len(player_ids)} IDs saved.")

        messagebox.showinfo("Update Complete",
                            f"Player IDs updated.\nTotal IDs: {len(player_ids)}")

    threading.Thread(target=run, daemon=True).start()

# Fetch player statistics for each ID and store them in CSV
def update_player_stats():
    def run():
        set_buttons_state("disabled")

        headers = ["ID","First name","Last name","Nationality","Age",
                   "Position","Appearances","Goals","Assists","G+A"]

        # Load player IDs
        try:
            with open(PLAYER_ID_FILE, "r") as f:
                player_ids = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            messagebox.showerror("Error", "Player ID file not found.")
            set_buttons_state("normal")
            return

        # Load existing data (if exists)
        try:
            df_existing = pd.read_csv(PLAYER_CSV_FILE, encoding="utf-8-sig")
            df_existing["ID"] = df_existing["ID"].astype(int)
            existing_ids = set(df_existing["ID"])
        except FileNotFoundError:
            df_existing = pd.DataFrame(columns=headers)
            existing_ids = set()

        all_data = df_existing.to_dict("records")
        total = len(player_ids)

        progress_bar.config(mode="determinate", maximum=total, value=0)
        show_progress(True)

        for idx, player_id in enumerate(player_ids, start=1):
            progress_bar["value"] = idx
            status_var.set(f"Updating stats... {idx}/{total}")
            root.update_idletasks()

            pid_int = int(player_id)
            if pid_int in existing_ids:
                continue

            url = f"https://footballapi.pulselive.com/football/stats/player/{player_id}?comps=1"

            try:
                response = requests.get(url)
                if response.status_code != 200:
                    continue

                data = response.json()
                entity = data.get("entity", {})
                stats = data.get("stats", [])

                # Extract player info
                first = entity.get("name", {}).get("first") or "/"
                last = entity.get("name", {}).get("last") or "/"
                nationality = entity.get("nationalTeam", {}).get("country") or "/"

                age_text = entity.get("age", "")
                age = age_text.split(" ")[0] if age_text else "/"

                pos_raw = entity.get("info", {}).get("position")
                pos_map = {"G":"Goalkeeper","D":"Defender","M":"Midfielder","F":"Forward"}
                position = pos_map.get(pos_raw, "/")

                # Extract stats
                appearances = next((s["value"] for s in stats if s["name"] == "appearances"), 0)
                goals = next((s["value"] for s in stats if s["name"] == "goals"), 0)
                assists = next((s["value"] for s in stats if s["name"] == "goal_assist"), 0)

                all_data.append({
                    "ID": pid_int,
                    "First name": first,
                    "Last name": last,
                    "Nationality": nationality,
                    "Age": age,
                    "Position": position,
                    "Appearances": int(appearances),
                    "Goals": int(goals),
                    "Assists": int(assists),
                    "G+A": int(goals) + int(assists)
                })

                time.sleep(0.2)

            except Exception as e:
                print(f"Error fetching stats for ID {player_id}: {e}")

        # Save CSV
        df = pd.DataFrame(all_data)
        df.sort_values("ID", inplace=True)
        df.to_csv(PLAYER_CSV_FILE, index=False, encoding="utf-8-sig")

        show_progress(False)
        set_buttons_state("normal")
        populate_nationality_dropdown(df)

        status_var.set(f"Done - stats updated for {len(df)} players.")
        messagebox.showinfo("Update Complete",
                            f"Player stats updated.\nTotal players: {len(df)}")

    threading.Thread(target=run, daemon=True).start()

# Apply filters and display results in the table
def filter_data():
    try:
        df = pd.read_csv(PLAYER_CSV_FILE, encoding="utf-8-sig")
    except FileNotFoundError:
        messagebox.showerror("Error", f"{PLAYER_CSV_FILE} not found.")
        return

    # Normalize numeric columns
    for col in ["Appearances","Goals","Assists","G+A"]:
        df[col] = df[col].fillna(0).astype(int)

    # Get filter values
    fn = entry_fname.get().strip().lower()
    ln = entry_lname.get().strip().lower()
    nat = combo_nationality.get()
    pos = combo_position.get()

    # Apply filters
    if fn:
        df = df[df["First name"].str.lower().str.contains(fn)]
    if ln:
        df = df[df["Last name"].str.lower().str.contains(ln)]
    if nat != "All":
        df = df[df["Nationality"] == nat]
    if pos != "All":
        df = df[df["Position"] == pos]

    # Sorting
    metric = combo_metric.get()
    df = df.sort_values("ID") if metric == "ID" else df.sort_values(metric, ascending=False)

    # Limit results
    top = combo_top.get()
    if top == "Top 5":
        df = df.head(5)
    elif top == "Top 10":
        df = df.head(10)

    # Populate table
    tree.delete(*tree.get_children())

    for rank, (_, row) in enumerate(df.iterrows(), start=1):
        tag = "odd" if rank % 2 else "even"

        values = [rank, row["ID"], row["First name"], row["Last name"],
                  row["Nationality"], row["Age"], row["Position"],
                  row["Appearances"], row["Goals"], row["Assists"], row["G+A"]]

        tree.insert("", "end", values=values, tags=(tag,))

    status_var.set(f"Showing {len(df)} player(s).")

# Populate nationality dropdown based on dataset
def populate_nationality_dropdown(df=None):
    try:
        if df is None:
            df = pd.read_csv(PLAYER_CSV_FILE, encoding="utf-8-sig")

        countries = sorted(df["Nationality"].dropna().unique())
        countries = ["All"] + list(countries)

        combo_nationality["values"] = countries
        combo_nationality.current(0)

    except FileNotFoundError:
        combo_nationality["values"] = ["All"]
        combo_nationality.current(0)


def populate_position_dropdown():
    combo_position["values"] = POSITION_ORDER
    combo_position.current(0)

# UI Helpers
def set_buttons_state(state):
    for btn in (btn_update_ids, btn_update_stats, btn_filter):
        btn.config_state(state)

def show_progress(visible):
    if visible:
        progress_bar.grid()
    else:
        progress_bar.grid_remove()
        progress_bar["value"] = 0

# Application Setup
root = tk.Tk()
root.title("Premier League All Time Player Stats")
root.state("zoomed")
root.configure(bg=BG_DARK)

# Load icon if available
try:
    icon = tk.PhotoImage(file="icon.png")
    root.iconphoto(True, icon)
except Exception:
    pass

style = ttk.Style()
style.theme_use("clam")

style.configure("Custom.Treeview",
    background=ROW_ODD, foreground=TEXT_PRIMARY,
    fieldbackground=ROW_ODD, rowheight=28,
    font=("Segoe UI", 10), borderwidth=0, relief="flat")
style.configure("Custom.Treeview.Heading",
    background=HEADER_BG, foreground=TEXT_MUTED,
    font=("Segoe UI", 10, "bold"), relief="flat", borderwidth=0)
style.map("Custom.Treeview",
    background=[("selected", ROW_SELECT)],
    foreground=[("selected", TEXT_PRIMARY)])
style.map("Custom.Treeview.Heading",
    background=[("active", BG_INPUT)])

style.configure("Dark.TCombobox",
    fieldbackground=BG_INPUT, background=BG_INPUT,
    foreground=TEXT_PRIMARY, selectbackground=BG_INPUT,
    selectforeground=TEXT_PRIMARY, bordercolor=BORDER,
    arrowcolor=TEXT_MUTED, relief="flat")
style.map("Dark.TCombobox",
    fieldbackground=[("readonly", BG_INPUT)],
    selectbackground=[("readonly", BG_INPUT)],
    foreground=[("readonly", TEXT_PRIMARY)])
root.option_add("*TCombobox*Listbox.background",       BG_INPUT)
root.option_add("*TCombobox*Listbox.foreground",       TEXT_PRIMARY)
root.option_add("*TCombobox*Listbox.selectBackground", ROW_SELECT)
root.option_add("*TCombobox*Listbox.font",             ("Segoe UI", 10))

style.configure("Green.Horizontal.TProgressbar",
    troughcolor=BG_INPUT, background=ACCENT,
    bordercolor=BG_INPUT, lightcolor=ACCENT, darkcolor=ACCENT)
style.configure("Dark.Vertical.TScrollbar",
    background=BG_INPUT, troughcolor=BG_DARK,
    arrowcolor=TEXT_MUTED, bordercolor=BG_DARK, relief="flat")

header_frame = tk.Frame(root, bg=BG_CARD, pady=14)
header_frame.pack(fill="x")
tk.Label(header_frame, text="⚽ Premier League All Time Player Stats",
         font=("Segoe UI", 18, "bold"), bg=BG_CARD, fg=TEXT_PRIMARY
         ).pack(side="left", padx=20)

filter_card = tk.Frame(root, bg=BG_CARD, pady=12, padx=16)
filter_card.pack(fill="x", padx=10, pady=(6, 4))

def lbl(text, row, col):
    tk.Label(filter_card, text=text, bg=BG_CARD, fg=TEXT_MUTED,
             font=("Segoe UI", 9)).grid(row=row, column=col, sticky="w",
             padx=(4,2), pady=(4,2))

def make_entry(row, col):
    e = tk.Entry(filter_card, bg=BG_INPUT, fg=TEXT_PRIMARY,
                 insertbackground=TEXT_PRIMARY, relief="flat",
                 font=("Segoe UI", 10), bd=0, width=FILTER_W,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT2)
    e.grid(row=row, column=col, padx=(2,8), pady=(0,6), ipady=5)
    return e

def make_combo(row, col, values=None):
    c = ttk.Combobox(filter_card, style="Dark.TCombobox",
                     state="readonly", font=("Segoe UI", 10),
                     width=FILTER_W, values=values or [])
    c.grid(row=row, column=col, padx=(2,8), pady=(0,6), ipady=3)
    return c

lbl("First Name",  0, 0); entry_fname       = make_entry(1, 0)
lbl("Last Name",   0, 1); entry_lname       = make_entry(1, 1)
lbl("Nationality", 0, 2); combo_nationality = make_combo(1, 2)
lbl("Position",    0, 3); combo_position    = make_combo(1, 3, values=POSITION_ORDER); combo_position.current(0)
lbl("Sort by",     0, 4); combo_metric      = make_combo(1, 4, values=["ID","Appearances","Goals","Assists","G+A"]); combo_metric.current(0)
lbl("Show",        0, 5); combo_top         = make_combo(1, 5, values=["Top 5","Top 10","All"]); combo_top.current(2)

btn_filter = RoundedButton(filter_card, text="🔍  Filter & Sort",
                           command=filter_data, bg=ACCENT2, hover_bg=ACCENT2_HOVER, radius=10)
btn_filter.grid(row=1, column=6, padx=(4,4), pady=(0,6))

tk.Label(filter_card, text="Data Management", bg=BG_CARD, fg=TEXT_MUTED,
         font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", padx=(4,2), pady=(6,2))

btn_update_ids = RoundedButton(filter_card, text="↻  Update IDs",
                               command=update_player_ids, bg=BG_INPUT, hover_bg=BORDER, radius=10)
btn_update_ids.grid(row=3, column=0, padx=(4,4), pady=(0,6))

btn_update_stats = RoundedButton(filter_card, text="↻  Update Stats",
                                 command=update_player_stats, bg=BG_INPUT, hover_bg=BORDER, radius=10)
btn_update_stats.grid(row=3, column=1, padx=(4,4), pady=(0,6))

progress_bar = ttk.Progressbar(filter_card, style="Green.Horizontal.TProgressbar",
                                orient="horizontal", mode="determinate", length=500)
progress_bar.grid(row=3, column=2, columnspan=4, padx=(8,4), pady=(0,6), sticky="ew")
progress_bar.grid_remove()

status_var = tk.StringVar(value="Ready.")
tk.Frame(root, bg=BORDER, height=1).pack(fill="x", side="bottom")
tk.Label(root, textvariable=status_var, bg=BG_CARD, fg=TEXT_MUTED,
         font=("Segoe UI", 9), anchor="w", padx=14, pady=5
         ).pack(fill="x", side="bottom")

tree_frame = tk.Frame(root, bg=BG_DARK)
tree_frame.pack(fill="both", expand=True, padx=10, pady=(4,0))

columns = ["Rank","ID","First name","Last name","Nationality","Age",
           "Position","Appearances","Goals","Assists","G+A"]
tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                    style="Custom.Treeview", selectmode="browse")
tree.tag_configure("odd",  background=ROW_ODD,  foreground=TEXT_PRIMARY)
tree.tag_configure("even", background=ROW_EVEN, foreground=TEXT_PRIMARY)

root.update_idletasks()
full_w      = root.winfo_width() - 30
fixed_cols  = {"Rank":50,"ID":60,"Age":50,"Nationality":115,"Position":105,
               "Appearances":100,"Goals":70,"Assists":70,"G+A":60}
fixed_total = sum(fixed_cols.values())
name_w      = max(60, (full_w - fixed_total - 20) // 2)

for col in columns:
    tree.heading(col, text=col, command=lambda c=col: sort_column(c))
    w = fixed_cols.get(col, name_w)
    anchor  = "w" if col in ("First name","Last name") else "center"
    stretch = col in ("First name","Last name")
    tree.column(col, width=w, anchor=anchor, minwidth=40, stretch=stretch)

def sort_column(col, reverse=False):
    data = [(tree.set(k, col), k) for k in tree.get_children("")]

    try:
        data.sort(key=lambda t: int(t[0]), reverse=reverse)
    except ValueError:
        data.sort(reverse=reverse)

    for index, (_, k) in enumerate(data):
        tree.move(k, "", index)

    tree.heading(col, command=lambda: sort_column(col, not reverse))

vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview,
                    style="Dark.Vertical.TScrollbar")
tree.configure(yscrollcommand=vsb.set)
vsb.pack(side="right", fill="y")
tree.pack(fill="both", expand=True)

tk.Frame(root, bg=BG_DARK, height=8).pack()

populate_nationality_dropdown()
populate_position_dropdown()

root.mainloop()
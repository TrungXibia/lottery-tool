# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
from bs4 import BeautifulSoup
import requests
import warnings
from collections import Counter
from datetime import datetime
from io import StringIO

warnings.filterwarnings("ignore", category=FutureWarning)

# --- HÀM TIỆN ÍCH ---
def safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def _get_month_url():
    return 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauThang5So.aspx'

def _get_year_url():
    return 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauNam5So.aspx'

# --- LỚP ỨNG DỤNG CHÍNH ---
class PhoiCauApp(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.master.title('TrungNd@2025 - Tìm Cầu Tháng/Năm')
        self.master.geometry('1200x800')

        # --- BIẾN TRẠNG THÁI ---
        self.current_df = None
        self.dan_so_sets = [[] for _ in range(12)]
        self.is_year_data = False
        self.cau_patterns = []
        self.pattern_months = set()
        self.cau_positions = set()
        self.predict_positions = set()
        
        # --- CÀI ĐẶT GIAO DIỆN ---
        self.colors = ['#ffcccc', '#ccffcc', '#ccccff', '#ffcc99', '#99ccff', '#ff99cc']
        self.cau_color = '#ffff99' # Vàng nhạt
        self.predict_color = '#ff7675' # Đỏ
        self.directions_labels = ["Từ trên xuống", "Từ dưới lên"]
        
        self._setup_styles()
        self._create_widgets()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TButton', padding=6, relief="raised", background="#2196F3", foreground="white", font=('Arial', 10, 'bold'), borderwidth=1)
        style.map('TButton', background=[('active', '#1E88E5')], foreground=[('active', 'white')])
        style.configure('TLabel', font=('Arial', 10))
        style.configure('TEntry', padding=5)
        style.configure('TCombobox', padding=5)
        style.configure('TCheckbutton', font=('Arial', 9))
        style.configure('TLabelframe.Label', font=('Arial', 10, 'bold'))
        style.configure('Treeview', rowheight=25, font=('Arial', 9))
        style.configure('Treeview.Heading', font=('Arial', 10, 'bold'), background="#f0f0f0")
        style.configure('TNotebook', background="#f0f0f0")
        style.configure('TNotebook.Tab', font=('Arial', 10, 'bold'), padding=[10, 5])

    def _create_widgets(self):
        self.configure(bg="#f0f0f0")
        toolbar = ttk.Frame(self, padding=10, relief='raised', borderwidth=2)
        toolbar.pack(fill='x', padx=10, pady=10)

        ttk.Button(toolbar, text='Lấy KQ Tháng', command=lambda: self.fetch_data('month')).pack(side='left', padx=5)
        ttk.Button(toolbar, text='Lấy KQ Năm', command=lambda: self.fetch_data('year')).pack(side='left', padx=5)
        self.btn_find_cau = ttk.Button(toolbar, text='Tìm Cầu', command=self.find_cau, state='disabled')
        self.btn_find_cau.pack(side='left', padx=5)
        self.btn_save = ttk.Button(toolbar, text='Lưu CSV', command=self.save_csv, state='disabled')
        self.btn_save.pack(side='left', padx=5)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        self.notebook.bind('<<NotebookTabChanged>>', self.on_tab_changed)

        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="Kết Quả")
        self._build_tab1()

        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="Tìm Cầu")
        self._build_tab2()

        self.tab3 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab3, text="Lên Mức Số")
        self._build_tab3()

    def _build_tab1(self):
        container = ttk.Frame(self.tab1, borderwidth=1, relief='raised', padding=10)
        container.pack(fill='both', expand=True, padx=10, pady=10)
        self.tree = ttk.Treeview(container, show='headings')
        self.tree.pack(fill='both', expand=True, side='left')
        vsb = ttk.Scrollbar(container, orient='vertical', command=self.tree.yview)
        vsb.pack(side='right', fill='y')
        hsb = ttk.Scrollbar(self.tab1, orient='horizontal', command=self.tree.xview)
        hsb.pack(fill='x', padx=10)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    def _build_tab2(self):
        popup_frame = ttk.Frame(self.tab2, padding=10)
        popup_frame.pack(fill='both', expand=True, padx=10, pady=10)

        left_frame = ttk.Frame(popup_frame)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))

        right_frame = ttk.Frame(popup_frame, width=300)
        right_frame.pack(side='right', fill='y')
        right_frame.pack_propagate(False)

        ctrl_frame = ttk.LabelFrame(left_frame, text="Điều khiển", padding=10)
        ctrl_frame.pack(fill='x', pady=(0, 10))

        input_frame = ttk.Frame(ctrl_frame)
        input_frame.pack(fill='x', pady=5)
        ttk.Label(input_frame, text='Số ngày chạy cầu:').pack(side='left', padx=5)
        self.entry_num_patterns = ttk.Entry(input_frame, width=5)
        self.entry_num_patterns.pack(side='left', padx=5)
        self.entry_num_patterns.insert(0, '2')
        self.entry_num_patterns.bind('<Return>', self._on_day_changed)

        self.day_frame = ttk.Frame(input_frame)
        self.day_frame.pack(side='left', padx=10)
        ttk.Label(self.day_frame, text='Chọn ngày:').pack(side='left', padx=5)
        self.cb = ttk.Combobox(self.day_frame, values=[], width=8, state='readonly')
        self.cb.pack(side='left', padx=5)
        self.cb.bind("<<ComboboxSelected>>", self._on_day_changed)

        self.month_frame = ttk.Frame(input_frame)
        self.month_frame.pack(side='left', padx=10)
        ttk.Label(self.month_frame, text='Chọn Tháng:').pack(side='left', padx=5)
        self.cb_month = ttk.Combobox(self.month_frame, values=[f"TH{i}" for i in range(1, 13)], width=5, state='readonly')
        self.cb_month.pack(side='left', padx=5)
        self.cb_month.bind("<<ComboboxSelected>>", self._on_day_changed)
        self.month_frame.pack_forget()

        self.pattern_frame = ttk.Frame(ctrl_frame, padding=5)
        self.pattern_frame.pack(fill='x', pady=5, anchor='w')

        checkbox_frame = ttk.Frame(ctrl_frame, padding=5)
        checkbox_frame.pack(fill='x', pady=5)
        self.exact_match_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(checkbox_frame, text="Chính xác mẫu (2 số cuối)", variable=self.exact_match_var, command=self.populate_grid).pack(side='left')

        result_frame = ttk.LabelFrame(left_frame, text="Bảng Kết Quả", padding=10)
        result_frame.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(result_frame, bg="#ffffff")
        vsb = ttk.Scrollbar(result_frame, orient='vertical', command=self.canvas.yview)
        hsb = ttk.Scrollbar(result_frame, orient='horizontal', command=self.canvas.xview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')

        stats_frame = ttk.LabelFrame(right_frame, text="Thống Kê Cầu", padding=10)
        stats_frame.pack(side='top', fill='x', pady=(0, 10))
        ttk.Button(stats_frame, text="Chạy Phân Tích (Auto)", command=self.run_all_step_options).pack(fill='x', pady=5)
        
        stats_result_frame = ttk.LabelFrame(right_frame, text="Kết Quả Thống Kê", padding=10)
        stats_result_frame.pack(side='top', fill='both', expand=True)
        self.stats_result_text = tk.Text(stats_result_frame, height=10, wrap='word', font=('Arial', 9), bg="#f9f9f9", relief='flat')
        self.stats_result_text.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(stats_result_frame, orient='vertical', command=self.stats_result_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.stats_result_text.config(yscrollcommand=scrollbar.set, state='disabled')
        self.stats_result_text.tag_configure("bold", font=('Arial', 9, 'bold'))

    def _build_tab3(self):
        container = ttk.PanedWindow(self.tab3, orient=tk.HORIZONTAL)
        container.pack(fill='both', expand=True, padx=10, pady=10)

        left_frame = ttk.Frame(container, padding=10)
        container.add(left_frame, weight=3)
        self.checkbox_frame = ttk.Frame(left_frame)
        self.checkbox_frame.pack(fill='both', expand=True)
        self.checkbox_frames = []
        for dir_idx, direction in enumerate(self.directions_labels):
            for step in range(6):
                row, col = dir_idx * 2 + (step // 3), step % 3
                lf = ttk.LabelFrame(self.checkbox_frame, text=f"{direction} – Cách {step}", padding=5)
                lf.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
                canvas = tk.Canvas(lf, bg="#ffffff", highlightthickness=0)
                vsb = ttk.Scrollbar(lf, orient='vertical', command=canvas.yview)
                vsb.pack(side='right', fill='y')
                inner = ttk.Frame(canvas)
                inner.bind("<Configure>", lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
                canvas.create_window((0, 0), window=inner, anchor='nw')
                canvas.configure(yscrollcommand=vsb.set)
                canvas.pack(fill='both', expand=True)
                self.checkbox_frames.append({'frame': inner, 'vars': []})
        for i in range(4): self.checkbox_frame.grid_rowconfigure(i, weight=1)
        for j in range(3): self.checkbox_frame.grid_columnconfigure(j, weight=1)

        right_frame = ttk.Labelframe(container, text="Module Lấy Mức Cuối", padding=10)
        container.add(right_frame, weight=1)
        ttk.Button(right_frame, text="Tính Mức Cuối", command=self.calculate_final_levels).pack(fill='x', pady=5)
        self.final_levels_text = tk.Text(right_frame, height=8, wrap='word', font=('Arial', 9), bg="#f9f9f9", relief='flat')
        self.final_levels_text.pack(fill='both', expand=True, pady=5)
        self.final_levels_text.insert('1.0', "Chưa chọn mức nào.")
        self.final_levels_text.config(state='disabled')
        ttk.Button(right_frame, text="Copy Kết Quả", command=self.copy_final_levels).pack(fill='x', pady=5)

    # --- LOGIC CỐT LÕI ---

    def fetch_data(self, fetch_type):
        self.is_year_data = (fetch_type == 'year')
        status = ttk.Label(self.tab1, text="Đang tải dữ liệu...", foreground="blue")
        status.pack()
        self.update()
        try:
            url = _get_year_url() if self.is_year_data else _get_month_url()
            sess = requests.Session()
            r1 = sess.get(url, timeout=20)
            r1.raise_for_status()
            soup = BeautifulSoup(r1.text, 'lxml')
            payload = {inp['name']: inp.get('value', '') for inp in soup.find_all('input', {'type': 'hidden'})}
            y = str(datetime.now().year)
            if self.is_year_data:
                payload.update({'ctl00$ContentPlaceHolder1$ddlNam': y, 'ctl00$ContentPlaceHolder1$btnXem': 'Xem'})
            else:
                m = str(datetime.now().month)
                payload.update({'ctl00$ContentPlaceHolder1$ddlThang': m, 'ctl00$ContentPlaceHolder1$ddlNam': y, 'ctl00$ContentPlaceHolder1$btnXem': 'Xem'})
            
            r2 = sess.post(url, data=payload, timeout=20)
            r2.raise_for_status()
            soup2 = BeautifulSoup(r2.text, 'lxml')
            keyword = 'TH1' if self.is_year_data else 'Ngày'
            table = next(t for t in soup2.find_all('table') if t.find('tr') and keyword in t.find('tr').get_text())
            df = pd.read_html(StringIO(str(table)), header=0)[0].fillna('')
            
            self.current_df = self._clean_df(df)
            self._populate_treeview(self.current_df)
            self.btn_find_cau.config(state='normal')
            self.btn_save.config(state='normal')
            
        except Exception as e:
            messagebox.showerror('Lỗi', f'Kết nối thất bại: {e}')
        finally:
            status.destroy()

    def _clean_df(self, df: pd.DataFrame) -> pd.DataFrame:
        def fmt(value, col_name):
            s = str(value).strip()
            if not s or s == '-----': return ''
            if s.endswith('.0'): s = s[:-2]
            
            # --- START: SỬA LỖI ĐỊNH DẠNG NGÀY ---
            if 'ngày' in str(col_name).lower():
                return s # Giữ nguyên định dạng ngày
            # --- END: SỬA LỖI ĐỊNH DẠNG NGÀY ---

            try:
                int(s)
                return s.zfill(5)
            except (ValueError, TypeError):
                return s

        for col in df.columns:
            df[col] = df[col].map(lambda v: fmt(v, col))

        if 'Ngày.1' in df.columns: df = df.rename(columns={'Ngày.1': 'Ngày'})
        if not self.is_year_data and df.columns[0] != 'Ngày':
            df = df.rename(columns={df.columns[0]: 'Ngày'})
            
        return df

    def find_cau(self):
        if self.current_df is None: return
        self.notebook.select(self.tab2)
        
        days = [str(i) for i in range(1, len(self.current_df) + 1)]
        self.cb['values'] = days
        if days: self.cb.current(len(days) - 1)
        
        if self.is_year_data:
            self.month_frame.pack(side='left', padx=10)
            current_month = datetime.now().month
            self.cb_month.current(current_month - 1)
        else:
            self.month_frame.pack_forget()
            
        self.update_pattern_entries()
        self.populate_grid()

    # --- START: SỬA LỖI LOGIC LẤY MẪU NĂM ---
    def update_pattern_entries(self):
        for w in self.pattern_frame.winfo_children(): w.destroy()
        if self.current_df is None: return
        
        num_patterns = safe_int(self.entry_num_patterns.get(), 0)
        if num_patterns <= 0: return

        df = self.current_df
        row_idx, selected_month = self._get_selection()
        
        self.cau_patterns = []
        self.pattern_months = set()
        temp_patterns = [] # Xây dựng mẫu từ xa đến gần

        if self.is_year_data:
            if num_patterns >= 2: # Mẫu b (xa nhất): Cùng ngày, tháng trước
                try:
                    current_month_num = int(selected_month[2:])
                    if current_month_num > 1:
                        p_col = f"TH{current_month_num - 1}"
                        val = df.iloc[row_idx][p_col]
                        temp_patterns.append(val[-2:] if isinstance(val, str) and len(val) >= 2 else '')
                        self.pattern_months.add(p_col)
                    else:
                        temp_patterns.append('')
                except (ValueError, IndexError, KeyError):
                    temp_patterns.append('')
            
            if num_patterns >= 1: # Mẫu a (gần hơn): Ngày hôm trước, cùng tháng
                if row_idx > 0:
                    val = df.iloc[row_idx - 1][selected_month]
                    temp_patterns.append(val[-2:] if isinstance(val, str) and len(val) >= 2 else '')
                    self.pattern_months.add(selected_month)
                else:
                    temp_patterns.append('')
        else: # Dữ liệu tháng (logic cũ)
            year_col = str(datetime.now().year)
            # Tìm đúng cột năm hiện tại nếu tên khác
            if year_col not in df.columns and len(df.columns) > 1:
                year_col = df.columns[1]

            for offset in range(num_patterns, 0, -1):
                idx = row_idx - offset
                val = df.iloc[idx][year_col] if idx >= 0 else ''
                temp_patterns.append(val[-2:] if isinstance(val, str) and len(val) >= 2 else '')

        self.cau_patterns = list(reversed(temp_patterns)) # Đảo lại để có thứ tự [gần, xa]

        # Hiển thị mẫu lên giao diện
        for i, pat in enumerate(self.cau_patterns):
            frame = ttk.Frame(self.pattern_frame)
            frame.pack(side='left', padx=(10, 2))
            ttk.Label(frame, text=f"Mẫu {chr(97+i)}:").pack()
            ent = tk.Entry(frame, width=5, justify='center', bg=self.colors[i % len(self.colors)], relief='solid', bd=1, font=('Arial', 10, 'bold'), state='readonly', readonlybackground=self.colors[i % len(self.colors)])
            ent.config(state='normal')
            ent.insert(0, pat)
            ent.config(state='readonly')
            ent.pack()
    # --- END: SỬA LỖI LOGIC LẤY MẪU NĂM ---

    def run_all_step_options(self):
        self.stats_result_text.config(state='normal')
        self.stats_result_text.delete('1.0', tk.END)
        if self.current_df is None: return

        self.update_pattern_entries() # Đảm bảo mẫu là mới nhất
        num_patterns = len(self.cau_patterns)
        if num_patterns == 0:
            self.stats_result_text.insert('end', "Vui lòng nhập số ngày chạy cầu > 0")
            self.stats_result_text.config(state='disabled')
            return

        df = self.current_df
        row_idx, selected_month = self._get_selection()
        
        self.cau_positions.clear()
        self.predict_positions.clear()
        self.dan_so_sets = [[] for _ in range(12)]
        
        # Xác định các cột cần bỏ qua
        cols_to_skip = set(self.pattern_months)
        if self.is_year_data:
            cols_to_skip.add(selected_month)
        else:
            year_col = str(datetime.now().year)
            if year_col not in df.columns and len(df.columns) > 1: year_col = df.columns[1]
            cols_to_skip.add(year_col)
        
        cols_to_scan = [c for c in df.columns if c != 'Ngày' and c not in cols_to_skip]

        for dir_idx, inside in enumerate([True, False]): # True: trên xuống, False: dưới lên
            for step in range(6):
                gap = step + 1
                count = 0
                result_nums = []

                # --- START: SỬA LỖI TÔ MÀU CẦU ---
                for col_name in cols_to_scan:
                    col_idx = df.columns.get_loc(col_name) # Lấy chỉ số cột chính xác
                    
                    for i in range(len(df)):
                        # Kiểm tra biên
                        if (inside and (i + (num_patterns - 1) * gap) >= len(df)) or \
                           (not inside and (i - (num_patterns - 1) * gap) < 0):
                            continue
                        
                        is_match, temp_pos = True, []
                        for k in range(num_patterns):
                            row_offset = k * gap if inside else -k * gap
                            row_pos = i + row_offset
                            val = df.iloc[row_pos, col_idx]
                            
                            if not self.matches_last_two_digits(val, self.cau_patterns[k]):
                                is_match = False
                                break
                            temp_pos.append((row_pos, col_idx)) # Lưu vị trí với chỉ số cột đúng
                        
                        if is_match:
                            predict_row = i + (num_patterns * gap if inside else -num_patterns * gap)
                            if 0 <= predict_row < len(df):
                                count += 1
                                self.cau_positions.update(temp_pos)
                                predict_val = df.iloc[predict_row, col_idx]
                                if predict_val:
                                    result_nums.append(predict_val)
                                    self.predict_positions.add((predict_row, col_idx))
                # --- END: SỬA LỖI TÔ MÀU CẦU ---

                idx = dir_idx * 6 + step
                self.dan_so_sets[idx] = [[a + b for a in num for b in num] for num in result_nums if len(num) >= 2]
                
                label = self.directions_labels[dir_idx]
                self.stats_result_text.insert('end', f"{label} – Cách {step}: ", "bold")
                self.stats_result_text.insert('end', f"{count} cầu\n")
                if result_nums:
                    self.stats_result_text.insert('end', f"Giá trị: {','.join(result_nums)}\n\n")
                else:
                    self.stats_result_text.insert('end', "Giá trị: Không tìm thấy cầu\n\n")

        self.stats_result_text.config(state='disabled')
        self.populate_grid()
        self.refresh_tab3()

    def populate_grid(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        if self.current_df is None: return

        df = self.current_df
        cols = list(df.columns)
        
        # Vẽ header
        for j, col in enumerate(cols):
            ttk.Label(self.scrollable_frame, text=col, borderwidth=1, relief='solid', anchor='center', background='lightgray', font=('Arial', 9, 'bold')).grid(row=0, column=j, sticky='nsew')

        # Vẽ dữ liệu
        for i in range(len(df)):
            for j in range(len(cols)):
                val = df.iloc[i, j]
                bg = 'white'
                
                # Ưu tiên tô màu dự đoán -> cầu -> mẫu
                if (i, j) in self.predict_positions:
                    bg = self.predict_color
                elif (i, j) in self.cau_positions:
                    bg = self.cau_color
                else:
                    for k in range(len(self.cau_patterns) - 1, -1, -1):
                        pat = self.cau_patterns[k]
                        if self.matches_last_two_digits(val, pat):
                            bg = self.colors[k % len(self.colors)]
                            break
                
                ttk.Label(self.scrollable_frame, text=str(val), borderwidth=1, relief='solid', anchor='center', background=bg).grid(row=i + 1, column=j, sticky='nsew')
        
        for j in range(len(cols)): self.scrollable_frame.grid_columnconfigure(j, weight=1, uniform="grid")

    # --- CÁC HÀM GIAO DIỆN PHỤ ---

    def _populate_treeview(self, df: pd.DataFrame):
        self.tree.delete(*self.tree.get_children())
        cols = list(df.columns)
        self.tree['columns'] = cols
        for c in cols:
            self.tree.heading(c, text=c)
            w = max(len(str(c)) * 10, 70)
            self.tree.column(c, width=w, anchor='center')
        for _, r in df.iterrows():
            self.tree.insert('', 'end', values=list(r))
    
    def on_tab_changed(self, event):
        if self.notebook.index('current') == 2: # Tab Lên Mức Số
            self.refresh_tab3()

    def refresh_tab3(self):
        for idx in range(12):
            container = self.checkbox_frames[idx]
            for widget in container['frame'].winfo_children(): widget.destroy()
            container['vars'].clear()
            
            all_pairs = [pair for dan in self.dan_so_sets[idx] for pair in dan]
            if not all_pairs: continue
            
            freq = Counter(all_pairs)
            levels = {}
            for pair, count in freq.items():
                if count not in levels: levels[count] = []
                levels[count].append(pair)
                
            for level in sorted(levels.keys(), reverse=True):
                pairs = sorted(levels[level], key=int)
                var = tk.BooleanVar(value=False)
                text = f"Mức {level} ({len(pairs)} số): {','.join(pairs)}"
                chk = ttk.Checkbutton(container['frame'], text=text, variable=var)
                chk.pack(anchor='w', padx=5, pady=2)
                container['vars'].append(var)
    
    def calculate_final_levels(self):
        self.final_levels_text.config(state='normal')
        self.final_levels_text.delete('1.0', tk.END)

        selected_pairs = []
        for idx, container in enumerate(self.checkbox_frames):
            all_level_pairs = [pair for dan in self.dan_so_sets[idx] for pair in dan]
            if not all_level_pairs: continue
            
            freq = Counter(all_level_pairs)
            levels = {}
            for pair, count in freq.items():
                if count not in levels: levels[count] = []
                levels[count].append(pair)

            for i, var in enumerate(container['vars']):
                if var.get():
                    level = sorted(levels.keys(), reverse=True)[i]
                    selected_pairs.extend(levels[level])

        if not selected_pairs:
            self.final_levels_text.insert('end', "Chưa chọn mức nào.")
        else:
            final_freq = Counter(selected_pairs)
            final_levels = {}
            for pair, count in final_freq.items():
                if count not in final_levels: final_levels[count] = []
                final_levels[count].append(pair)
            
            for level in sorted(final_levels.keys(), reverse=True):
                pairs = sorted(final_levels[level], key=int)
                line = f"Mức {level} ({len(pairs)} số): {','.join(pairs)}\n"
                self.final_levels_text.insert('end', line)
                
        self.final_levels_text.config(state='disabled')

    def copy_final_levels(self):
        text = self.final_levels_text.get("1.0", tk.END).strip()
        if not text or text == "Chưa chọn mức nào.":
            messagebox.showwarning("Copy", "Không có gì để sao chép!")
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(text)
        messagebox.showinfo("Copy", "Đã sao chép kết quả vào clipboard!")

    def _get_selection(self):
        if self.current_df is None: return 0, None
        row_idx = safe_int(self.cb.get(), 1) - 1
        month = self.cb_month.get() if self.is_year_data else None
        return row_idx, month

    def _on_day_changed(self, event=None):
        self.update_pattern_entries()
        self.populate_grid()
        
    def matches_last_two_digits(self, value, pattern):
        return isinstance(value, str) and len(value) >= 2 and isinstance(pattern, str) and len(pattern) == 2 and value.endswith(pattern)

    def save_csv(self):
        if self.current_df is None: return
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if path:
            self.current_df.to_csv(path, index=False, encoding='utf-8-sig')
            messagebox.showinfo('Hoàn thành', f'Đã lưu tệp tại {path}')

# --- CHẠY ỨNG DỤNG ---
if __name__ == "__main__":
    root = tk.Tk()
    app = PhoiCauApp(master=root)
    app.pack(fill='both', expand=True)
    try:
        root.state('zoomed') # Windows
    except tk.TclError:
        root.attributes('-zoomed', True) # Linux
    root.mainloop()

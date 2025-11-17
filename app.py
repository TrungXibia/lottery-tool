# -*- coding: utf-8 -*-
import pandas as pd
from bs4 import BeautifulSoup
import requests
import warnings
from datetime import datetime
from io import StringIO
import json
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Cấu hình ứng dụng Flask
app = Flask(__name__, static_folder='.')
CORS(app)

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Serve static files ---
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('.', path)

# --- Các hàm logic cốt lõi ---

def _get_month_url():
    return 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauThang5So.aspx'

def _get_year_url():
    return 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauNam5So.aspx'
    
def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Làm sạch DataFrame và chuẩn hóa dữ liệu"""
    def fmt(v):
        s = str(v).strip()
        if not s or s == '-----': 
            return ''
        if s.endswith('.0'): 
            s = s[:-2]
        try:
            int(s)
            return s.zfill(5)
        except (ValueError, TypeError):
            return s

    df = df.apply(lambda col: col.map(fmt))
    
    # Fix encoding issues với tên cột
    if 'Ngày.1' in df.columns: 
        df = df.rename(columns={'Ngày.1': 'Ngày'})
    
    # Đảm bảo cột đầu tiên là 'Ngày' nếu không phải tháng
    if not df.columns[0].startswith('TH') and df.columns[0] != 'Ngày':
        df = df.rename(columns={df.columns[0]: 'Ngày'})
    
    return df

def fetch_data_from_source(fetch_type='month'):
    """Lấy dữ liệu từ website xổ số"""
    try:
        sess = requests.Session()
        url = _get_month_url() if fetch_type == 'month' else _get_year_url()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Request 1: Lấy form data
        r1 = sess.get(url, timeout=20, headers=headers)
        r1.raise_for_status()
        soup = BeautifulSoup(r1.text, 'lxml')
        
        # Lấy hidden inputs
        payload = {
            inp['name']: inp.get('value', '') 
            for inp in soup.find_all('input', {'type': 'hidden'})
        }
        
        y = str(datetime.now().year)
        
        # Chuẩn bị payload theo loại
        if fetch_type == 'month':
            m = str(datetime.now().month)
            payload.update({
                'ctl00$ContentPlaceHolder1$ddlThang': m,
                'ctl00$ContentPlaceHolder1$ddlNam': y,
                'ctl00$ContentPlaceHolder1$btnXem': 'Xem'
            })
        else:
            payload.update({
                'ctl00$ContentPlaceHolder1$ddlNam': y,
                'ctl00$ContentPlaceHolder1$btnXem': 'Xem'
            })
        
        # Request 2: Submit form
        r2 = sess.post(url, data=payload, timeout=20, headers=headers)
        r2.raise_for_status()
        
        # Parse bảng kết quả
        soup2 = BeautifulSoup(r2.text, 'lxml')
        keyword = 'Ngày' if fetch_type == 'month' else 'TH1'
        
        table = next(
            t for t in soup2.find_all('table') 
            if t.find('tr') and keyword in t.find('tr').get_text()
        )
        
        df = pd.read_html(StringIO(str(table)), header=0)[0].fillna('')
        return _clean_df(df)
        
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return None

# --- API Endpoints ---

@app.route('/fetch_data', methods=['POST'])
def api_fetch_data():
    """API lấy dữ liệu tháng/năm"""
    data = request.get_json()
    fetch_type = data.get('type', 'month')
    
    df = fetch_data_from_source(fetch_type)
    
    if df is not None:
        return jsonify({
            'success': True,
            'table_html': df.to_html(
                classes='table table-bordered text-center', 
                index=False
            ),
            'columns': list(df.columns),
            'rows': len(df),
            'df_json': df.to_json(orient='split'),
            'is_year_data': (fetch_type == 'year')
        })
    
    return jsonify({
        'success': False, 
        'message': f'Kết nối {fetch_type} thất bại.'
    })

@app.route('/run_analysis', methods=['POST'])
def api_run_analysis():
    """API phân tích tìm cầu"""
    data = request.get_json()
    
    # Parse dữ liệu đầu vào
    df = pd.read_json(StringIO(data['df_json']), orient='split')
    is_year_data = data.get('is_year_data', False)
    row_idx = int(data.get('day_idx', len(df) - 1))
    num_patterns = int(data.get('num_patterns', 2))
    exact_match = data.get('exact_match', False)
    selected_month_col = data.get('month_col')
    
    if is_year_data and not selected_month_col:
        return jsonify({
            'success': False,
            'message': 'Vui lòng chọn tháng trước khi phân tích!'
        })
    
    patterns = []
    pattern_months = set()
    
    def _last_non_empty_row(col_name: str) -> int:
        """Tìm dòng cuối cùng có dữ liệu trong cột"""
        if col_name not in df.columns: 
            return -1
        col = df[col_name]
        for r in range(len(col)-1, -1, -1):
            v = col.iloc[r]
            if isinstance(v, str) and v.strip() != '': 
                return r
        return -1

    def _prev_cell_year(day_idx: int, month_col: str):
        """Tìm ô trước đó (cho dữ liệu năm)"""
        if day_idx > 0: 
            return day_idx - 1, month_col
        
        if not (isinstance(month_col, str) and month_col.startswith("TH")): 
            return -1, None
        
        m = int(month_col[2:])
        pm = 12 if m == 1 else m - 1
        pcol = f"TH{pm}"
        prow = _last_non_empty_row(pcol)
        
        return (prow, pcol) if prow >= 0 else (-1, pcol)

    # Xây dựng patterns (mẫu cầu)
    if is_year_data:
        cur_day, cur_col = row_idx, selected_month_col
        for _ in range(num_patterns):
            p_day, p_col = _prev_cell_year(cur_day, cur_col)
            pat = df.iloc[p_day][p_col] if p_day >= 0 and p_col is not None else ''
            pattern_months.add(p_col)
            patterns.append(pat[-2:] if isinstance(pat, str) and len(pat) >= 2 else '')
            cur_day, cur_col = (p_day, p_col)
    else:
        # Dữ liệu tháng
        year_col = str(datetime.now().year)
        if year_col not in df.columns and len(df.columns) > 1: 
            year_col = df.columns[1]
        
        for offset in range(1, num_patterns + 1):
            idx = row_idx - offset
            pat = df.iloc[idx][year_col] if idx >= 0 else ''
            patterns.append(pat[-2:] if isinstance(pat, str) and len(pat) >= 2 else '')
    
    patterns.reverse()
    
    # Hàm kiểm tra match
    def matches_last_two_digits(v, p): 
        return isinstance(v, str) and len(v) >= 2 and v[-2:] == p
    
    def contains_two_digits(v, p):
        if not (isinstance(v, str) and len(v) >= 2 and isinstance(p, str) and len(p) == 2): 
            return False
        return p[0] in v and p[1] in v
    
    match_func = matches_last_two_digits if exact_match else contains_two_digits
    
    # Khởi tạo kết quả
    all_results = []
    cau_positions = []
    predict_positions = []
    dan_so_sets = [[] for _ in range(12)]
    
    cols_full = list(df.columns)
    cols_to_scan = [c for c in cols_full if c != 'Ngày']
    
    # --- START: SỬA LỖI TẠI ĐÂY ---
    if is_year_data:
        # Xử lý cho dữ liệu năm (khi các cột là TH1, TH2...)
        # Loại bỏ các cột đã dùng để tạo mẫu
        for month in pattern_months:
            if month in cols_to_scan:
                cols_to_scan.remove(month)
        # Loại bỏ cột đang chọn
        if selected_month_col in cols_to_scan:
            cols_to_scan.remove(selected_month_col)
    else:
        # Xử lý cho dữ liệu tháng (khi các cột là 2023, 2024...)
        # Xác định cột nguồn đã được dùng để tạo mẫu
        source_year_col = str(datetime.now().year)
        if source_year_col not in df.columns and len(df.columns) > 1: 
            source_year_col = df.columns[1] # Thường là cột thứ hai
        
        # Chỉ loại bỏ cột nguồn ra khỏi danh sách quét
        if source_year_col in cols_to_scan:
            cols_to_scan.remove(source_year_col)
    # --- END: KẾT THÚC SỬA LỖI ---
            
    # Vòng lặp chính: Tìm cầu
    for dir_idx, inside in enumerate([True, False]):
        direction_label = "Từ trên xuống" if inside else "Từ dưới lên"
        
        for step in range(6):
            gap = step + 1
            count = 0
            result_nums = []
            
            for col_name in cols_to_scan:
                col_index = cols_full.index(col_name)
                
                for i in range(len(df)):
                    # Kiểm tra biên
                    if inside and (i + (num_patterns - 1) * gap) >= len(df):
                        continue
                    if not inside and (i - (num_patterns - 1) * gap) < 0:
                        continue
                    
                    ok = True
                    pos = []
                    
                    for k in range(num_patterns):
                        row_offset = k * gap if inside else -k * gap
                        row_pos = i + row_offset
                        v = df.iloc[row_pos][col_name]
                        
                        if not match_func(v, patterns[k]):
                            ok = False
                            break
                        
                        pos.append({'row': row_pos, 'col': col_index})
                    
                    if ok:
                        predict_idx = i + (num_patterns * gap if inside else -num_patterns * gap)
                        
                        if 0 <= predict_idx < len(df):
                            count += 1
                            cau_positions.extend(pos)
                            
                            pv = df.iloc[predict_idx][col_name]
                            if pv:
                                result_nums.append(pv)
                                predict_positions.append({'row': predict_idx, 'col': col_index})
            
            idx = dir_idx * 6 + step
            dan_so_sets[idx] = [
                [a + b for a in num for b in num] 
                for num in result_nums if len(num) >= 2 # Đảm bảo số có ít nhất 2 chữ số
            ]
            
            result_text = f"<b>{direction_label} – Cách {step}:</b> {count} cầu"
            if result_nums: 
                result_text += f"<br><i>Giá trị:</i> {','.join(result_nums)}"
            else: 
                result_text += "<br><i>Giá trị:</i> Không tìm thấy cầu"
            
            all_results.append(result_text)
    
    return jsonify({
        'success': True, 
        'patterns': patterns, 
        'stats_html': '<hr>'.join(all_results),
        'cau_positions': cau_positions,
        'predict_positions': predict_positions,
        'dan_so_sets': dan_so_sets
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True) # Bật debug để dễ phát triển

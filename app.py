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

app = Flask(__name__, static_folder='.')
CORS(app)
warnings.filterwarnings("ignore", category=FutureWarning)

@app.route('/')
def serve_index(): return send_from_directory('.', 'index.html')
@app.route('/<path:path>')
def serve_static(path): return send_from_directory('.', path)

def _get_month_url(): return 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauThang5So.aspx'
def _get_year_url(): return 'https://congcuxoso.com/MienBac/DacBiet/PhoiCauDacBiet/PhoiCauNam5So.aspx'

def _clean_df(df: pd.DataFrame):
    def format_result(v, col_name):
        s = str(v).strip()
        if not s or s == '-----': return ''
        if s.endswith('.0'): s = s[:-2]
        if 'ngày' in str(col_name).lower(): return s
        try:
            int(s); return s.zfill(5)
        except (ValueError, TypeError): return s
    for col in df.columns: df[col] = df[col].map(lambda v: format_result(v, col))
    if 'Ngày.1' in df.columns: df = df.rename(columns={'Ngày.1': 'Ngày'})
    if not df.columns[0].startswith('TH') and df.columns[0] != 'Ngày': df = df.rename(columns={df.columns[0]: 'Ngày'})
    return df

def fetch_data_from_source(fetch_type='month'):
    try:
        url = _get_month_url() if fetch_type == 'month' else _get_year_url()
        sess = requests.Session(); headers = {'User-Agent': 'Mozilla/5.0'}
        r1 = sess.get(url, timeout=20, headers=headers); r1.raise_for_status()
        soup = BeautifulSoup(r1.text, 'lxml')
        payload = {inp['name']: inp.get('value', '') for inp in soup.find_all('input', {'type': 'hidden'})}
        y = str(datetime.now().year)
        if fetch_type == 'month':
            payload.update({'ctl00$ContentPlaceHolder1$ddlThang': str(datetime.now().month), 'ctl00$ContentPlaceHolder1$ddlNam': y, 'ctl00$ContentPlaceHolder1$btnXem': 'Xem'})
        else:
            payload.update({'ctl00$ContentPlaceHolder1$ddlNam': y, 'ctl00$ContentPlaceHolder1$btnXem': 'Xem'})
        r2 = sess.post(url, data=payload, timeout=20, headers=headers); r2.raise_for_status()
        soup2 = BeautifulSoup(r2.text, 'lxml')
        keyword = 'Ngày' if fetch_type == 'month' else 'TH1'
        table = next(t for t in soup2.find_all('table') if t.find('tr') and keyword in t.find('tr').get_text())
        df = pd.read_html(StringIO(str(table)), header=0)[0].fillna(''); return _clean_df(df)
    except Exception as e:
        print(f"Error fetching: {e}"); return None

@app.route('/fetch_data', methods=['POST'])
def api_fetch_data():
    fetch_type = request.get_json().get('type', 'month'); df = fetch_data_from_source(fetch_type)
    if df is not None:
        return jsonify({'success': True, 'table_html': df.to_html(classes='table table-bordered', index=False), 'columns': list(df.columns), 'rows': len(df), 'df_json': df.to_json(orient='split'), 'is_year_data': (fetch_type == 'year')})
    return jsonify({'success': False, 'message': f'Kết nối {fetch_type} thất bại.'})

@app.route('/run_analysis', methods=['POST'])
def api_run_analysis():
    data = request.get_json()
    df, is_year_data, row_idx, num_patterns, selected_month_col, step = pd.read_json(StringIO(data['df_json']), orient='split'), data.get('is_year_data', False), int(data.get('day_idx', -1)), int(data.get('num_patterns', 2)), data.get('month_col'), data.get('step')
    if is_year_data and not selected_month_col: return jsonify({'success': False, 'message': 'Vui lòng chọn tháng!'})
    
    patterns, pattern_months = [], set()
    if is_year_data:
        temp = []
        if num_patterns >= 2:
            try:
                m_num = int(selected_month_col[2:])
                if m_num > 1: p_col = f"TH{m_num - 1}"; val = df.iloc[row_idx][p_col]; temp.append(val[-2:] if len(val) >= 2 else ''); pattern_months.add(p_col)
                else: temp.append('')
            except: temp.append('')
        if num_patterns >= 1:
            if row_idx > 0: val = df.iloc[row_idx - 1][selected_month_col]; temp.append(val[-2:] if len(val) >= 2 else ''); pattern_months.add(selected_month_col)
            else: temp.append('')
        patterns = list(reversed(temp))
    else:
        year_col = str(datetime.now().year)
        if year_col not in df.columns and len(df.columns) > 1: year_col = df.columns[1]
        for offset in range(1, num_patterns + 1):
            idx = row_idx - offset; pat = df.iloc[idx][year_col] if idx >= 0 else ''; patterns.append(pat[-2:] if len(pat) >= 2 else '')
        patterns.reverse()
    
    match_func = lambda v, p: isinstance(v, str) and len(v) >= 2 and p and v.endswith(p)
    all_results, cau_positions, predict_positions, dan_so_sets = [], [], [], [[] for _ in range(12)]
    
    cols_to_skip = pattern_months.copy()
    if is_year_data: cols_to_skip.add(selected_month_col)
    else:
        year_col = str(datetime.now().year)
        if year_col not in df.columns and len(df.columns) > 1: year_col = df.columns[1]
        cols_to_skip.add(year_col)
    cols_to_scan = [c for c in df.columns if c != 'Ngày' and c not in cols_to_skip]
    
    steps_to_run = range(6) if step is None else [step]

    for dir_idx, inside in enumerate([True, False]):
        for s in range(6):
            if s not in steps_to_run: continue
            gap, count, result_nums = s + 1, 0, []
            for col_name in cols_to_scan:
                col_index = df.columns.get_loc(col_name)
                for i in range(len(df)):
                    if (inside and (i + (num_patterns - 1) * gap) >= len(df)) or (not inside and (i - (num_patterns - 1) * gap) < 0): continue
                    ok, pos = True, []
                    for k in range(num_patterns):
                        row_pos = i + (k * gap if inside else -k * gap)
                        if not match_func(df.iloc[row_pos][col_name], patterns[k]): ok = False; break
                        pos.append({'row': row_pos, 'col': col_index})
                    if ok:
                        predict_idx = i + (num_patterns * gap if inside else -num_patterns * gap)
                        if 0 <= predict_idx < len(df):
                            count += 1; cau_positions.extend(pos)
                            pv = df.iloc[predict_idx][col_name]
                            if pv: result_nums.append(pv); predict_positions.append({'row': predict_idx, 'col': col_index})
            
            idx = dir_idx * 6 + s
            if step is None: dan_so_sets[idx] = [[a + b for a in num for b in num] for num in result_nums if len(num) >= 2]
            label = "Từ trên xuống" if inside else "Từ dưới lên"
            text = f"<b>{label} – Cách {s}:</b> {count} cầu"
            text += f"<br><i>Giá trị:</i> {','.join(result_nums)}" if result_nums else "<br><i>Giá trị:</i> Không tìm thấy cầu"
            all_results.append(text)
    
    return jsonify({'success': True, 'patterns': patterns, 'stats_html': '<hr>'.join(all_results), 'cau_positions': cau_positions, 'predict_positions': predict_positions, 'dan_so_sets': dan_so_sets})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

$(document).ready(function() {
    // API Base URL - để trống vì cùng domain
    const API_BASE_URL = '';

    let currentData = {
        df_html: '',
        df_json: null,
        is_year_data: false,
        column_names: [],
        dan_so_sets: []
    };
    
    const colors = ['#ffcccc', '#ccffcc', '#ccccff', '#ffcc99', '#99ccff', '#ff99cc'];

    function showLoader(show) { 
        $('#loader').toggle(show); 
        $('#table-container').toggle(!show); 
    }
    
    function enableTabs() { 
        $('#timcau-tab, #lenmuc-tab').prop('disabled', false); 
    }
    
    // Tự động hiển thị bảng khi chuyển sang tab "Tìm Cầu"
    $('button[data-bs-target="#timcau"]').on('shown.bs.tab', function() {
        if (currentData.df_html && !$('#grid-container').html().trim()) {
            $('#grid-container').html(currentData.df_html);
        }
    });

    function fetchData(fetchType) {
        showLoader(true);
        
        // Reset tất cả các khu vực hiển thị
        $('#table-container, #grid-container, #stats-results, #pattern-display').html('');
        $('#stats-results').html('Chưa có thống kê.');
        $('#month-selector-group').hide();

        $.ajax({
            url: `${API_BASE_URL}/fetch_data`,
            type: 'POST', 
            contentType: 'application/json',
            data: JSON.stringify({ type: fetchType }),
            success: function(response) {
                if (response.success) {
                    // Lưu lại tất cả dữ liệu cần thiết
                    currentData.is_year_data = response.is_year_data;
                    currentData.df_json = response.df_json;
                    currentData.df_html = response.table_html; 
                    currentData.column_names = response.columns;
                    
                    // Vẽ bảng kết quả ở cả hai nơi
                    $('#table-container').html(response.table_html);
                    $('#grid-container').html(response.table_html);
                    
                    // Tạo dropdown chọn ngày
                    let dayOptions = '';
                    for (let i = 1; i <= response.rows; i++) {
                        dayOptions += `<option value="${i}">${i}</option>`;
                    }
                    $('#daySelector').html(dayOptions).val(response.rows);
                    
                    // Nếu là dữ liệu năm, hiển thị dropdown chọn tháng
                    if (response.is_year_data) {
                        $('#month-selector-group').show(); 
                        let monthOptions = '';
                        response.columns.forEach((col) => {
                           if(col.startsWith('TH')) {
                               monthOptions += `<option value="${col}">Tháng ${col.substring(2)}</option>`;
                           }
                        });
                        const currentMonth = `TH${new Date().getMonth() + 1}`;
                        $('#monthSelector').html(monthOptions).val(currentMonth);
                    }
                    
                    enableTabs();
                } else { 
                    alert('Lỗi: ' + response.message); 
                }
            },
            error: function(xhr, status, error) { 
                alert('Lỗi kết nối tới Backend API: ' + error); 
            },
            complete: function() { 
                showLoader(false); 
            }
        });
    }

    $('#btnFetchMonth').on('click', () => fetchData('month'));
    $('#btnFetchYear').on('click', () => fetchData('year'));

    // Hàm tô màu theo Mẫu
    function highlightPatternsInGrid(patterns) {
        const isExactMatch = $('#exactMatchCheck').is(':checked');
        const $table = $('#grid-container table');
        if (!$table.length) return;

        $table.find('tbody tr').each(function() {
            $(this).find('td').each(function(colIndex) {
                // Bỏ qua cột "Ngày"
                if (currentData.column_names[colIndex] === 'Ngày') return;
                
                const cellValue = $(this).text();
                
                // Xóa tất cả class highlight cũ
                $(this).removeClass('pattern-highlight-0 pattern-highlight-1 pattern-highlight-2 pattern-highlight-3 pattern-highlight-4 pattern-highlight-5');
                
                if (!cellValue) return;

                // Kiểm tra từng pattern (từ cuối lên để ưu tiên pattern mới nhất)
                for (let i = patterns.length - 1; i >= 0; i--) {
                    const pattern = patterns[i];
                    if (!pattern || pattern.length < 2) continue;
                    
                    let match = false;
                    if (isExactMatch) {
                        match = (cellValue.slice(-2) === pattern);
                    } else {
                        match = (cellValue.includes(pattern[0]) && cellValue.includes(pattern[1]));
                    }
                    
                    if (match) { 
                        $(this).addClass(`pattern-highlight-${i}`); 
                        break; 
                    }
                }
            });
        });
    }

    // Hàm chạy phân tích
    function runAnalysis(step = null) {
        if (!currentData.df_json) {
            alert("Vui lòng lấy dữ liệu trước khi phân tích.");
            return;
        }
        
        const params = {
            df_json: currentData.df_json, 
            is_year_data: currentData.is_year_data,
            num_patterns: parseInt($('#numPatterns').val()), 
            day_idx: parseInt($('#daySelector').val()) - 1,
            month_col: currentData.is_year_data ? $('#monthSelector').val() : null,
            exact_match: $('#exactMatchCheck').is(':checked'), 
            step: step
        };
        
        $('#stats-results').html('Đang phân tích...');
        $('#grid-container').html(currentData.df_html); // Luôn vẽ lại bảng gốc

        $.ajax({
            url: `${API_BASE_URL}/run_analysis`,
            type: 'POST', 
            contentType: 'application/json',
            data: JSON.stringify(params),
            success: function(res) {
                if (res.success) {
                    // Hiển thị patterns
                    let patternHTML = '';
                    res.patterns.forEach((p, i) => {
                        patternHTML += `<div class="pattern-box" style="background-color: ${colors[i % colors.length]};">
                            <label class="form-label mb-0 small">Mẫu ${String.fromCharCode(97 + i)}</label>
                            <input type="text" value="${p}" readonly>
                        </div>`;
                    });
                    $('#pattern-display').html(patternHTML);
                    $('#stats-results').html(res.stats_html);

                    // Khôi phục TÔ MÀU THEO MẪU
                    highlightPatternsInGrid(res.patterns);

                    const $table = $('#grid-container table');
                    
                    // FIX: Hàm tô màu cầu - Dùng pos.col trực tiếp (không phải pos.col_name)
                    const highlightCell = (pos, className) => {
                        if (typeof pos.col !== 'number') {
                            console.error('Invalid pos.col:', pos);
                            return;
                        }
                        
                        // Tô màu trực tiếp bằng index
                        $table.find('tbody tr').eq(pos.row).find('td').eq(pos.col).addClass(className);
                    };

                    // Tô màu các cầu tìm được
                    res.cau_positions.forEach(pos => highlightCell(pos, 'cau-highlight'));
                    
                    // Tô màu dự đoán
                    res.predict_positions.forEach(pos => highlightCell(pos, 'predict-highlight'));
                    
                    // Nếu là phân tích auto, lưu dan_so_sets
                    if (step === null) {
                        currentData.dan_so_sets = res.dan_so_sets;
                        populateLevelSelectionTab(); // Cập nhật Tab 3
                    }
                } else { 
                    alert('Lỗi phân tích: ' + res.message); 
                }
            },
            error: function(xhr, status, error) { 
                alert('Lỗi kết nối khi phân tích: ' + error); 
            }
        });
    }

    $('#btnRunAnalysisAuto').on('click', () => runAnalysis(null));
    $('.btn-run-step').on('click', function() { 
        runAnalysis($(this).data('step')); 
    });
    
    // Các hàm cho Tab 3: Lên Mức Số
    function populateLevelSelectionTab() {
        const container = $('#level-selection-container');
        container.html('');
        
        if (!currentData.dan_so_sets || 
            currentData.dan_so_sets.length === 0 || 
            currentData.dan_so_sets.every(s => s.length === 0)) {
            container.html('<p class="text-muted">Không có dữ liệu mức số. Hãy chạy Phân Tích (Auto) trước.</p>');
            return;
        }
        
        const directions = ["Từ trên xuống", "Từ dưới lên"];
        
        currentData.dan_so_sets.forEach((set, index) => {
            const dirIdx = Math.floor(index / 6);
            const step = index % 6;
            
            // Gộp tất cả các cặp số
            const allPairs = [].concat.apply([], set);
            if (allPairs.length === 0) return;
            
            // Đếm tần suất
            const freq = allPairs.reduce((acc, pair) => {
                acc[pair] = (acc[pair] || 0) + 1;
                return acc;
            }, {});
            
            // Nhóm theo mức
            const levels = {};
            for (const pair in freq) {
                const count = freq[pair];
                if (!levels[count]) levels[count] = [];
                levels[count].push(pair);
            }
            
            // Tạo HTML
            let content = `<div class="col-md-4 mb-3">
                <div class="card h-100">
                    <div class="card-header">${directions[dirIdx]} - Cách ${step}</div>
                    <div class="card-body" style="max-height: 200px; overflow-y: auto;">`;
            
            const sortedLevels = Object.keys(levels).sort((a, b) => b - a);
            sortedLevels.forEach(level => {
                const pairs = levels[level].sort((a,b) => a - b);
                content += `<div class="form-check">
                    <input class="form-check-input level-checkbox" type="checkbox" 
                           value='${JSON.stringify(pairs)}' id="chk-${index}-${level}">
                    <label class="form-check-label small" for="chk-${index}-${level}">
                        <b>Mức ${level}</b> (${pairs.length} số): ${pairs.join(',')}
                    </label>
                </div>`;
            });
            
            content += `</div></div></div>`;
            container.append(content);
        });
    }
    
    $('#btnCalculateFinal').on('click', function() {
        const allSelectedPairs = [];
        
        $('.level-checkbox:checked').each(function() { 
            allSelectedPairs.push(...JSON.parse($(this).val())); 
        });
        
        if (allSelectedPairs.length === 0) {
            $('#final-levels-output').text('Chưa chọn mức nào.');
            return;
        }
        
        // Đếm tần suất
        const freq = allSelectedPairs.reduce((acc, pair) => {
            acc[pair] = (acc[pair] || 0) + 1;
            return acc;
        }, {});
        
        // Nhóm theo mức
        const levels = {};
        for (const pair in freq) {
            const count = freq[pair];
            if (!levels[count]) levels[count] = [];
            levels[count].push(pair);
        }
        
        // Tạo output
        let output = '';
        const sortedLevels = Object.keys(levels).sort((a, b) => b - a);
        sortedLevels.forEach(level => {
            const pairs = levels[level].sort((a, b) => a - b);
            output += `Mức ${level}: ${pairs.length} số: ${pairs.join(',')}\n`;
        });
        
        $('#final-levels-output').text(output);
    });
    
    $('#btnCopyFinal').on('click', function() {
        const text = $('#final-levels-output').text();
        navigator.clipboard.writeText(text).then(
            () => alert('Đã sao chép vào clipboard!'), 
            (err) => alert('Lỗi khi sao chép: ' + err)
        );
    });
});

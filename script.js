$(document).ready(function() {
    // ĐỔI URL API - Bỏ domain cũ vì giờ backend + frontend cùng domain
    const API_BASE_URL = '';  // Để trống = dùng relative path

    let currentData = {
        df_html: '',
        df_json: null,
        is_year_data: false,
        column_names: [],
        dan_so_sets: []
    };
    const colors = ['#ffcccc', '#ccffcc', '#ccccff', '#ffcc99', '#99ccff', '#ff99cc'];
    const all_highlight_classes = ['pattern-highlight-0', 'pattern-highlight-1', 'pattern-highlight-2', 'pattern-highlight-3', 'pattern-highlight-4', 'pattern-highlight-5', 'cau-highlight', 'predict-highlight'];

    function showLoader(show) { $('#loader').toggle(show); $('#table-container').toggle(!show); }
    function enableTabs() { $('#timcau-tab, #lenmuc-tab').prop('disabled', false); }
    
    // Logic mới: Tự động hiển thị bảng khi chuyển sang tab "Tìm Cầu"
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
            type: 'POST', contentType: 'application/json',
            data: JSON.stringify({ type: fetchType }),
            success: function(response) {
                if (response.success) {
                    // Lưu lại tất cả dữ liệu cần thiết từ backend
                    currentData.is_year_data = response.is_year_data;
                    currentData.df_json = response.df_json;
                    currentData.df_html = response.table_html; 
                    currentData.column_names = response.columns;
                    
                    // Vẽ bảng kết quả ở cả hai nơi
                    $('#table-container').html(response.table_html);
                    $('#grid-container').html(response.table_html); // Quan trọng: Vẽ cả ở tab Tìm Cầu
                    
                    let dayOptions = '';
                    for (let i = 1; i <= response.rows; i++) dayOptions += `<option value="${i}">${i}</option>`;
                    $('#daySelector').html(dayOptions).val(response.rows);
                    
                    if (response.is_year_data) {
                        $('#month-selector-group').show(); 
                        let monthOptions = '';
                        response.columns.forEach((col) => {
                           if(col.startsWith('TH')) monthOptions += `<option value="${col}">Tháng ${col.substring(2)}</option>`;
                        });
                        const currentMonth = `TH${new Date().getMonth() + 1}`;
                        $('#monthSelector').html(monthOptions).val(currentMonth);
                    }
                    enableTabs();
                    // Tự động chạy phân tích sau khi tải dữ liệu thành công
                    if (currentData.df_json) {
                        runAnalysis(null);
                    }
                } else { alert('Lỗi: ' + response.message); }
            },
            error: function() { alert('Lỗi kết nối tới Backend API.'); },
            complete: function() { showLoader(false); }
        });
    }

    $('#btnFetchMonth').on('click', () => fetchData('month'));
    $('#btnFetchYear').on('click', () => fetchData('year'));

    // Hàm chỉ chạy phân tích đầy đủ (null) khi các input điều khiển thay đổi
    // Để đảm bảo pattern và thống kê luôn cập nhật
    function updatePatternAndRunAnalysis() {
        if (currentData.df_json && !$('#loader').is(':visible')) {
            runAnalysis(null); 
        }
    }

    // Gán sự kiện cho các control để tự động cập nhật
    $('#daySelector, #numPatterns, #monthSelector, #exactMatchCheck').on('change', updatePatternAndRunAnalysis);
    
    // Hàm tô màu theo Mẫu (Đã bị loại bỏ để chỉ tô màu các ô MẪU GỐC, CẦU, DỰ ĐOÁN)
    // function highlightPatternsInGrid(patterns) { /* ... (logic cũ) ... */ }

    // Hàm chạy phân tích (Đã sửa logic tô màu)
    function runAnalysis(step = null) {
        if (!currentData.df_json) {
            return;
        }
        const params = {
            df_json: currentData.df_json, is_year_data: currentData.is_year_data,
            num_patterns: $('#numPatterns').val(), day_idx: parseInt($('#daySelector').val()) - 1,
            month_col: currentData.is_year_data ? $('#monthSelector').val() : null,
            exact_match: $('#exactMatchCheck').is(':checked'), step: step
        };
        
        $('#stats-results').html('Đang phân tích...');
        
        // Luôn vẽ lại bảng gốc và xóa tất cả highlight cũ
        $('#grid-container').html(currentData.df_html); 
        const $table = $('#grid-container table');
        $table.find('td').each(function() {
            $(this).removeClass(all_highlight_classes.join(' ')).css('border', '1px solid #dee2e6');
        });


        $.ajax({
            url: `${API_BASE_URL}/run_analysis`,
            type: 'POST', contentType: 'application/json',
            data: JSON.stringify(params),
            success: function(res) {
                if (res.success) {
                    let patternHTML = '';
                    res.patterns.forEach((p, i) => {
                        patternHTML += `<div class="pattern-box" style="background-color: ${colors[i % colors.length]};"><label class="form-label mb-0 small">Mẫu ${String.fromCharCode(97 + i)}</label><input type="text" value="${p}" readonly></div>`;
                    });
                    $('#pattern-display').html(patternHTML);
                    $('#stats-results').html(res.stats_html);

                    
                    const highlightCell = (pos, className) => {
                        const colIndex = currentData.column_names.indexOf(pos.col_name);
                        if (colIndex !== -1) {
                            $table.find('tbody tr').eq(pos.row).find('td').eq(colIndex).addClass(className);
                        }
                    };

                    // BƯỚC 1: TÔ MÀU VÀ LÀM NỔI BẬT CÁC Ô ĐƯỢC DÙNG LÀM MẪU (pattern_positions)
                    if (res.pattern_positions) {
                        res.pattern_positions.forEach((pos, i) => {
                            const colIndex = currentData.column_names.indexOf(pos.col_name);
                            if (colIndex !== -1) {
                                // Tô màu theo pattern index (i) và thêm viền
                                $table.find('tbody tr').eq(pos.row).find('td').eq(colIndex).addClass(`pattern-highlight-${i}`).css('border', '2px solid black');
                            }
                        });
                    }
                    
                    // BƯỚC 2: TÔ MÀU CẦU ĐƯỢC TÌM THẤY
                    res.cau_positions.forEach(pos => highlightCell(pos, 'cau-highlight'));
                    
                    // BƯỚC 3: TÔ MÀU DỰ ĐOÁN
                    res.predict_positions.forEach(pos => highlightCell(pos, 'predict-highlight'));
                    
                    if (step === null) {
                        currentData.dan_so_sets = res.dan_so_sets;
                        populateLevelSelectionTab(); // Cập nhật Tab 3
                    }
                } else { alert('Lỗi phân tích: ' + res.message); }
            },
            error: function() { alert('Lỗi kết nối khi phân tích.'); }
        });
    }

    // Nút chạy chính (dù nút mới không có trong file gốc, vẫn gán sự kiện)
    $('#btnRunAnalysisAuto, #btnRunAnalysisPrimary').on('click', () => runAnalysis(null)); 
    $('.btn-run-step').on('click', function() { runAnalysis($(this).data('step')); });
    
    // Các hàm cho Tab 3 (đã hoạt động)
    function populateLevelSelectionTab() {
        const container = $('#level-selection-container');
        container.html('');
        if (!currentData.dan_so_sets || currentData.dan_so_sets.length === 0 || currentData.dan_so_sets.every(s => s.length === 0)) {
            container.html('<p class="text-muted">Không có dữ liệu mức số. Hãy chạy Phân Tích (Auto) trước.</p>');
            return;
        }
        const directions = ["Từ trên xuống", "Từ dưới lên"];
        currentData.dan_so_sets.forEach((set, index) => {
            const dirIdx = Math.floor(index / 6), step = index % 6;
            const allPairs = [].concat.apply([], set);
            if (allPairs.length === 0) return;
            const freq = allPairs.reduce((acc, pair) => ({ ...acc, [pair]: (acc[pair] || 0) + 1 }), {});
            const levels = {};
            for (const pair in freq) {
                const count = freq[pair];
                if (!levels[count]) levels[count] = [];
                levels[count].push(pair);
            }
            let content = `<div class="col-md-4 mb-3"><div class="card h-100"><div class="card-header">${directions[dirIdx]} - Cách ${step}</div><div class="card-body" style="max-height: 200px; overflow-y: auto;">`;
            const sortedLevels = Object.keys(levels).sort((a, b) => b - a);
            sortedLevels.forEach(level => {
                const pairs = levels[level].sort((a,b) => a-b);
                content += `<div class="form-check"><input class="form-check-input level-checkbox" type="checkbox" value='${JSON.stringify(pairs)}' id="chk-${index}-${level}"><label class="form-check-label small" for="chk-${index}-${level}"><b>Mức ${level}</b> (${pairs.length} số): ${pairs.join(',')}</label></div>`;
            });
            content += `</div></div></div>`;
            container.append(content);
        });
    }
    $('#btnCalculateFinal').on('click', function() {
        const allSelectedPairs = [];
        $('.level-checkbox:checked').each(function() { allSelectedPairs.push(...JSON.parse($(this).val())); });
        if (allSelectedPairs.length === 0) {
            $('#final-levels-output').text('Chưa chọn mức nào.');
            return;
        }
        const freq = allSelectedPairs.reduce((acc, pair) => ({ ...acc, [pair]: (acc[pair] || 0) + 1 }), {});
        const levels = {};
        for (const pair in freq) {
            const count = freq[pair];
            if (!levels[count]) levels[count] = [];
            levels[count].push(pair);
        }
        let output = '';
        const sortedLevels = Object.keys(levels).sort((a, b) => b - a);
        sortedLevels.forEach(level => {
            const pairs = levels[level].sort((a, b) => a - b);
            output += `Mức ${level}: ${pairs.length} số: ${pairs.join(',')}\n`;
        });
        $('#final-levels-output').text(output);
    });
    $('#btnCopyFinal').on('click', function() {
        navigator.clipboard.writeText($('#final-levels-output').text()).then(() => alert('Đã sao chép vào clipboard!'), (err) => alert('Lỗi khi sao chép: ', err));
    });
});

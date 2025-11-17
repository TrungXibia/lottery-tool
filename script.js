$(document).ready(function() {
    const API_BASE_URL = '';
    let currentData = { df_json: null, dan_so_sets: [] };
    const colors = ['#ffcccc', '#ccffcc', '#ccccff'];

    const showLoader = (show) => { $('#loader').toggle(show); $('#table-container').toggle(!show); };
    const enableTabs = (enable) => { $('#timcau-tab-btn, #lenmuc-tab-btn').toggleClass('disabled', !enable); };

    function fetchData(fetchType) {
        showLoader(true);
        enableTabs(false);
        $.ajax({
            url: `${API_BASE_URL}/fetch_data`, type: 'POST', contentType: 'application/json',
            data: JSON.stringify({ type: fetchType }),
            success: function(res) {
                if (res.success) {
                    currentData = { ...currentData, ...res };
                    $('#table-container, #grid-container').html(res.table_html);
                    let dayOptions = Array.from({length: res.rows}, (_, i) => `<option value="${i+1}">${i+1}</option>`).join('');
                    $('#daySelector').html(dayOptions).val(res.rows);
                    if (res.is_year_data) {
                        $('#month-selector-group').show();
                        let monthOptions = res.columns.filter(c => c.startsWith('TH')).map(c => `<option value="${c}">Tháng ${c.substring(2)}</option>`).join('');
                        $('#monthSelector').html(monthOptions).val(`TH${new Date().getMonth() + 1}`);
                    } else {
                        $('#month-selector-group').hide();
                    }
                    enableTabs(true);
                } else { alert('Lỗi: ' + res.message); }
            },
            error: (xhr, status, error) => alert('Lỗi kết nối: ' + error),
            complete: () => showLoader(false)
        });
    }

    $('#btnFetchMonth').on('click', () => fetchData('month'));
    $('#btnFetchYear').on('click', () => fetchData('year'));

    function runAnalysis(step = null) { // step = null for Auto, 0-5 for specific steps
        if (!currentData.df_json) { alert("Vui lòng lấy dữ liệu trước."); return; }
        $('#stats-results').html('Đang phân tích...');
        
        const params = {
            df_json: currentData.df_json, is_year_data: currentData.is_year_data,
            num_patterns: parseInt($('#numPatterns').val()), day_idx: parseInt($('#daySelector').val()) - 1,
            month_col: currentData.is_year_data ? $('#monthSelector').val() : null,
            step: step // Send step to backend
        };

        $.ajax({
            url: `${API_BASE_URL}/run_analysis`, type: 'POST', contentType: 'application/json',
            data: JSON.stringify(params),
            success: function(res) {
                if (res.success) {
                    if (step === null) { // Only update dan_so_sets on Auto run
                        currentData.dan_so_sets = res.dan_so_sets;
                        populateLevelSelectionTab();
                    }
                    $('#stats-results').html(res.stats_html);
                    let patternHTML = res.patterns.map((p, i) => `<div class="pattern-box" style="border-left: 5px solid ${colors[i % colors.length]}; padding-left: 8px;"> Mẫu ${String.fromCharCode(97 + i)} <input type="text" value="${p}" readonly></div>`).join('');
                    $('#pattern-display').html(patternHTML);
                    
                    $('#grid-container').html(currentData.table_html); // Reset grid
                    const $table = $('#grid-container table');
                    const highlightCell = (pos, className) => $table.find('tbody tr').eq(pos.row).find('td').eq(pos.col).addClass(className);
                    
                    res.cau_positions.forEach(pos => highlightCell(pos, 'cau-highlight'));
                    res.predict_positions.forEach(pos => highlightCell(pos, 'predict-highlight'));
                    
                    // Highlight pattern occurrences separately to avoid overriding cau/predict colors
                    res.patterns.forEach((p, i) => {
                        if (!p) return;
                         $table.find('td').filter(function() { 
                            return $(this).text().slice(-2) === p && !$(this).hasClass('cau-highlight') && !$(this).hasClass('predict-highlight'); 
                        }).addClass(`pattern-highlight-${i}`);
                    });
                } else { alert('Lỗi phân tích: ' + res.message); }
            },
            error: (xhr, status, error) => alert('Lỗi kết nối phân tích: ' + error)
        });
    }
    $('#btnRunAnalysisAuto').on('click', () => runAnalysis(null));
    $('.btn-run-step').on('click', function() { runAnalysis($(this).data('step')); });
    $('#daySelector, #monthSelector, #numPatterns').on('change', function() {
        $('#stats-results').html('');
        $('#pattern-display').html('');
        $('#grid-container').html(currentData.table_html);
    });

    function populateLevelSelectionTab() {
        const container = $('#level-selection-container').html('');
        if (!currentData.dan_so_sets || currentData.dan_so_sets.every(s => s.length === 0)) {
            container.html('<div class="col-12"><p class="text-muted">Không có dữ liệu mức số. Hãy chạy Phân Tích (Auto) trước.</p></div>');
            return;
        }
        
        const directions = ["Từ trên xuống", "Từ dưới lên"];
        currentData.dan_so_sets.forEach((set, index) => {
            const allPairs = [].concat.apply([], set);
            if (allPairs.length === 0) return;
            
            const freq = allPairs.reduce((acc, pair) => ({...acc, [pair]: (acc[pair] || 0) + 1 }), {});
            const levels = {};
            for (const pair in freq) { (levels[freq[pair]] = levels[freq[pair]] || []).push(pair); }
            
            const dirIdx = Math.floor(index / 6), step = index % 6;
            let content = `<div class="col-md-4 mb-3"><div class="card h-100"><div class="card-header">${directions[dirIdx]} - Cách ${step}</div><div class="card-body">`;
            
            Object.keys(levels).sort((a, b) => b - a).forEach(level => {
                const pairs = levels[level].sort((a,b) => a - b);
                content += `<div class="form-check"><input class="form-check-input level-checkbox" type="checkbox" value='${JSON.stringify(pairs)}' id="chk-${index}-${level}"><label class="form-check-label" for="chk-${index}-${level}"><b>Mức ${level}</b> (${pairs.length} số): ${pairs.join(',')}</label></div>`;
            });
            container.append(content + `</div></div></div>`);
        });
    }
    
    $('#btnCalculateFinal').on('click', function() {
        const allSelectedPairs = [];
        $('.level-checkbox:checked').each(function() { allSelectedPairs.push(...JSON.parse($(this).val())); });
        if (allSelectedPairs.length === 0) { $('#final-levels-output').text('Chưa chọn mức nào.'); return; }
        
        const freq = allSelectedPairs.reduce((acc, pair) => ({...acc, [pair]: (acc[pair] || 0) + 1 }), {});
        const levels = {};
        for (const pair in freq) { (levels[freq[pair]] = levels[freq[pair]] || []).push(pair); }
        
        let output = '';
        Object.keys(levels).sort((a, b) => b - a).forEach(level => {
            const pairs = levels[level].sort((a, b) => a - b);
            output += `Mức ${level}: ${pairs.length} số: ${pairs.join(',')}\n`;
        });
        $('#final-levels-output').text(output);
    });
    
    $('#btnCopyFinal').on('click', function() {
        navigator.clipboard.writeText($('#final-levels-output').text()).then(() => alert('Đã sao chép!'), () => alert('Lỗi khi sao chép.'));
    });
});

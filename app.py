import os
import sqlite3
import pandas as pd
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'  # 請記得修改為隨機安全的金鑰

DB_FILE = 'student_health.db'

# ==================== 資料庫初始化 ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 建立授權使用者表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS authorized_users (
            gmail TEXT PRIMARY KEY,
            role TEXT NOT NULL
        )
    ''')
    
    # 建立學生健康紀錄表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grade INTEGER,
            class_num INTEGER,
            seat INTEGER,
            name TEXT,
            disease_name TEXT,
            disease_content TEXT,
            care_instructions TEXT
        )
    ''')
    
    # 預設寫入系統管理者帳號
    cursor.execute('INSERT OR IGNORE INTO authorized_users (gmail, role) VALUES (?, ?)', ('b113002@yuteh.ntpc.edu.tw', 'admin'))
    conn.commit()
    conn.close()

init_db()

# ==================== HTML 模組 ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>學生健康照護查詢系統</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .record-card { border-left: 4px solid #0d6efd; }
        .care-box { background-color: #fff3cd; border: 1px solid #ffe69c; }
    </style>
</head>
<body class="bg-light">

<nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-4">
    <div class="container">
        <a class="navbar-brand fw-bold" href="/">學生健康照護查詢系統</a>
        {% if session.get('user') %}
            <div class="d-flex align-items-center">
                <span class="text-white me-3">{{ session['user']['email'] }} ({{ session['user']['role'] }})</span>
                <a href="/logout" class="btn btn-outline-light btn-sm">登出</a>
            </div>
        {% endif %}
    </div>
</nav>

<div class="container pb-5">
    {% if not session.get('user') %}
        <!-- 登入區塊 -->
        <div class="row justify-content-center mt-5">
            <div class="col-md-6 text-center">
                <div class="card shadow">
                    <div class="card-body py-5">
                        <h3 class="mb-4 fw-bold">請先登入系統</h3>
                        <form action="/dev_login" method="POST">
                            <div class="mb-3">
                                <input type="email" name="email" class="form-control form-control-lg" placeholder="請輸入已授權之 Gmail 帳號" required>
                            </div>
                            <button type="submit" class="btn btn-danger btn-lg w-100">模擬 Google 帳號登入</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    {% else %}
        <!-- 主要頁籤選單 -->
        <ul class="nav nav-tabs mb-4 fw-bold" id="myTab" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" id="single-search-tab" data-bs-toggle="tab" data-bs-target="#single-search" type="button">個人健康查詢</button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="class-search-tab" data-bs-toggle="tab" data-bs-target="#class-search" type="button">全班健康查詢</button>
            </li>
            {% if session['user']['role'] == 'admin' %}
            <li class="nav-item">
                <button class="nav-link" id="admin-tab" data-bs-toggle="tab" data-bs-target="#admin" type="button">後臺管理與資料上傳</button>
            </li>
            {% endif %}
        </ul>

        <div class="tab-content" id="myTabContent">
            
            <!-- 1. 個人健康紀錄查詢 -->
            <div class="tab-pane fade show active" id="single-search">
                <div class="card shadow-sm mb-4">
                    <div class="card-header bg-white"><h5 class="mb-0 fw-bold">個人健康資料查詢</h5></div>
                    <div class="card-body">
                        <div class="row g-3">
                            <div class="col-md-3">
                                <label class="form-label fw-bold">年級 (1~12)</label>
                                <select id="single_grade" class="form-select">
                                    <option value="">請選擇年級</option>
                                    {% for g in range(1, 13) %}<option value="{{ g }}">{{ g }} 年級</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label fw-bold">班級 (1~8)</label>
                                <select id="single_class" class="form-select">
                                    <option value="">請選擇班級</option>
                                    {% for c in range(1, 9) %}<option value="{{ c }}">{{ c }} 班</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label fw-bold">座號 (1~40)</label>
                                <select id="single_seat" class="form-select">
                                    <option value="">請選擇座號</option>
                                    {% for s in range(1, 41) %}<option value="{{ s }}">{{ s }} 號</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label fw-bold">學生姓名 (選填)</label>
                                <input type="text" id="single_name" class="form-control" placeholder="輸入姓名可進行比對">
                            </div>
                            <div class="col-12 mt-3">
                                <button type="button" onclick="searchSingleStudent()" class="btn btn-primary w-100 fs-5">查詢學生健康紀錄</button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 個人查詢結果區 -->
                <div id="singleResultArea" style="display: none;">
                    <div class="alert alert-info d-flex justify-content-between align-items-center">
                        <h4 id="singleStudentHeader" class="mb-0 fw-bold"></h4>
                        <span id="recordCountBadge" class="badge bg-primary fs-6"></span>
                    </div>
                    <div id="singleRecordsContainer"></div>
                </div>
            </div>

            <!-- 2. 全班健康紀錄查詢 -->
            <div class="tab-pane fade" id="class-search">
                <div class="card shadow-sm mb-4">
                    <div class="card-header bg-white"><h5 class="mb-0 fw-bold">班級全體學生健康資料查詢</h5></div>
                    <div class="card-body">
                        <div class="row g-3">
                            <div class="col-md-5">
                                <label class="form-label fw-bold">年級 (1~12)</label>
                                <select id="class_grade" class="form-select">
                                    <option value="">請選擇年級</option>
                                    {% for g in range(1, 13) %}<option value="{{ g }}">{{ g }} 年級</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-5">
                                <label class="form-label fw-bold">班級 (1~8)</label>
                                <select id="class_num" class="form-select">
                                    <option value="">請選擇班級</option>
                                    {% for c in range(1, 9) %}<option value="{{ c }}">{{ c }} 班</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-2 d-flex align-items-end">
                                <button type="button" onclick="searchClassStudents()" class="btn btn-success w-100 fs-5">查詢全班</button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 班級查詢結果區 -->
                <div id="classResultArea" style="display: none;">
                    <div class="alert alert-success fw-bold fs-5" id="classResultHeader"></div>
                    <div class="table-responsive bg-white shadow-sm rounded">
                        <table class="table table-hover table-bordered mb-0 align-middle">
                            <thead class="table-light">
                                <tr>
                                    <th style="width: 80px;">座號</th>
                                    <th style="width: 120px;">姓名</th>
                                    <th style="width: 180px;">疾病名稱</th>
                                    <th>疾病內容</th>
                                    <th>照護/注意事項</th>
                                </tr>
                            </thead>
                            <tbody id="classTableBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>

            {% if session['user']['role'] == 'admin' %}
            <!-- 3. 後臺管理頁面 (僅管理員) -->
            <div class="tab-pane fade" id="admin">
                <div class="row">
                    <!-- 上傳 Excel 資料 -->
                    <div class="col-md-6 mb-4">
                        <div class="card shadow-sm h-100">
                            <div class="card-header bg-white"><h5 class="mb-0 fw-bold">上傳學生健康資料 Excel</h5></div>
                            <div class="card-body">
                                <form action="/upload_excel" method="POST" enctype="multipart/form-data">
                                    <div class="mb-3">
                                        <label class="form-label fw-bold">請選擇 Excel 檔案 (.xlsx / .xls)</label>
                                        <input type="file" name="excel_file" class="form-control" accept=".xlsx, .xls" required>
                                        <div class="form-text mt-2">
                                            <strong>格式提醒：</strong>上傳將會更新/覆蓋資料庫。Excel 標題列需包含：<br>
                                            <code>年級</code> | <code>班級</code> | <code>座號</code> | <code>姓名</code> | <code>疾病名稱</code> | <code>疾病內容</code> | <code>照護注意事項</code>
                                        </div>
                                    </div>
                                    <button type="submit" class="btn btn-success w-100">批次匯入/更新資料</button>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- 新增與管理 Gmail 授權 -->
                    <div class="col-md-6 mb-4">
                        <div class="card shadow-sm h-100">
                            <div class="card-header bg-white"><h5 class="mb-0 fw-bold">授權 Gmail 帳號管理</h5></div>
                            <div class="card-body">
                                <form action="/add_user" method="POST" class="mb-4">
                                    <div class="mb-2">
                                        <label class="form-label fw-bold">Gmail 帳號</label>
                                        <input type="email" name="new_email" class="form-control" placeholder="example@gmail.com" required>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label fw-bold">權限角色</label>
                                        <select name="role" class="form-select">
                                            <option value="viewer">一般查詢者 (viewer)</option>
                                            <option value="admin">管理者 (admin)</option>
                                        </select>
                                    </div>
                                    <button type="submit" class="btn btn-primary w-100">新增或更新授權</button>
                                </form>

                                <h6 class="fw-bold border-bottom pb-2">目前已授權帳號：</h6>
                                <ul class="list-group list-group-flush small" style="max-height: 200px; overflow-y: auto;">
                                    {% for u in users %}
                                    <li class="list-group-item d-flex justify-content-between align-items-center">
                                        <div>
                                            <strong>{{ u[0] }}</strong> 
                                            <span class="badge {% if u[1]=='admin' %}bg-danger{% else %}bg-secondary{% endif %} ms-1">{{ u[1] }}</span>
                                        </div>
                                        {% if u[0] != session['user']['email'] %}
                                        <form action="/delete_user" method="POST" style="margin: 0;" onsubmit="return confirm('確定移除此帳號授權？');">
                                            <input type="hidden" name="email" value="{{ u[0] }}">
                                            <button type="submit" class="btn btn-outline-danger btn-sm py-0">刪除</button>
                                        </form>
                                        {% endif %}
                                    </li>
                                    {% endfor %}
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            {% endif %}
        </div>
    {% endif %}
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
// 1. 單人查詢邏輯
function searchSingleStudent() {
    const grade = document.getElementById('single_grade').value;
    const class_num = document.getElementById('single_class').value;
    const seat = document.getElementById('single_seat').value;
    const name = document.getElementById('single_name').value.trim();

    if (!grade || !class_num || !seat) {
        alert("請選擇完整的年級、班級與座號！");
        return;
    }

    let queryUrl = `/api/search_single?grade=${grade}&class_num=${class_num}&seat=${seat}`;
    if (name) queryUrl += `&name=${encodeURIComponent(name)}`;

    fetch(queryUrl)
        .then(res => res.json())
        .then(data => {
            const resultArea = document.getElementById('singleResultArea');
            const container = document.getElementById('singleRecordsContainer');
            
            if (data.status === 'success') {
                document.getElementById('singleStudentHeader').innerText = `${data.student.grade} 年級 ${data.student.class_num} 班 ${data.student.seat} 號 - ${data.student.name}`;
                document.getElementById('recordCountBadge').innerText = `共有 ${data.records.length} 筆健康紀錄`;

                container.innerHTML = '';
                data.records.forEach((rec, idx) => {
                    const card = document.createElement('div');
                    card.className = 'card shadow-sm mb-3 record-card';
                    card.innerHTML = `
                        <div class="card-body">
                            <h5 class="card-title text-danger fw-bold">紀錄 #${idx + 1}：${rec.disease_name || '無特定疾病名稱'}</h5>
                            <div class="mb-2">
                                <strong>疾病內容：</strong>
                                <div class="p-2 bg-light rounded mt-1">${rec.disease_content || '無資料'}</div>
                            </div>
                            <div>
                                <strong>照護/注意事項：</strong>
                                <div class="p-2 rounded mt-1 care-box">${rec.care_instructions || '無特定注意事項'}</div>
                            </div>
                        </div>
                    `;
                    container.appendChild(card);
                });

                resultArea.style.display = 'block';
            } else {
                alert(data.message);
                resultArea.style.display = 'none';
            }
        })
        .catch(err => {
            alert("查詢時發生錯誤");
            console.error(err);
        });
}

// 2. 班級查詢邏輯
function searchClassStudents() {
    const grade = document.getElementById('class_grade').value;
    const class_num = document.getElementById('class_num').value;

    if (!grade || !class_num) {
        alert("請選擇年級與班級！");
        return;
    }

    fetch(`/api/search_class?grade=${grade}&class_num=${class_num}`)
        .then(res => res.json())
        .then(data => {
            const resultArea = document.getElementById('classResultArea');
            const tbody = document.getElementById('classTableBody');

            if (data.status === 'success') {
                document.getElementById('classResultHeader').innerText = `${grade} 年級 ${class_num} 班 - 全班學生健康紀錄 (共 ${data.data.length} 筆紀錄)`;
                tbody.innerHTML = '';

                data.data.forEach(row => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td class="fw-bold text-center">${row.seat}</td>
                        <td>${row.name}</td>
                        <td class="text-danger fw-bold">${row.disease_name || '無'}</td>
                        <td>${row.disease_content || '無'}</td>
                        <td>${row.care_instructions || '無'}</td>
                    `;
                    tbody.appendChild(tr);
                });

                resultArea.style.display = 'block';
            } else {
                alert(data.message);
                resultArea.style.display = 'none';
            }
        })
        .catch(err => {
            alert("查詢時發生錯誤");
            console.error(err);
        });
}
</script>
</body>
</html>
"""

# ==================== 路由與邏輯控制 ====================

@app.route('/')
def index():
    users = []
    if session.get('user') and session['user']['role'] == 'admin':
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT gmail, role FROM authorized_users')
        users = cursor.fetchall()
        conn.close()

    return render_template_string(HTML_TEMPLATE, users=users)

@app.route('/dev_login', methods=['POST'])
def dev_login():
    email = request.form.get('email', '').strip()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM authorized_users WHERE gmail = ?', (email,))
    user = cursor.fetchone()
    conn.close()

    if user:
        session['user'] = {'email': email, 'role': user[0]}
    else:
        return "<script>alert('無權限登入！請聯繫管理員新增授權'); window.location.href='/';</script>"
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/upload_excel', methods=['POST'])
def upload_excel():
    if not session.get('user') or session['user']['role'] != 'admin':
        return "權限不足", 403

    file = request.files.get('excel_file')
    if file:
        try:
            df = pd.read_excel(file)
            # 清理欄位空格
            df.columns = [str(c).strip() for c in df.columns]

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            # 清空舊紀錄
            cursor.execute('DELETE FROM health_records')
            
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO health_records (grade, class_num, seat, name, disease_name, disease_content, care_instructions)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    int(row['年級']),
                    int(row['班級']),
                    int(row['座號']),
                    str(row['姓名']).strip(),
                    str(row.get('疾病名稱', '') if pd.notna(row.get('疾病名稱')) else ''),
                    str(row.get('疾病內容', '') if pd.notna(row.get('疾病內容')) else ''),
                    str(row.get('照護注意事項', '') if pd.notna(row.get('照護注意事項')) else '')
                ))
            conn.commit()
            conn.close()
            return "<script>alert('Excel 資料批次匯入成功！'); window.location.href='/';</script>"
        except Exception as e:
            return f"<script>alert('匯入失敗，請確認欄位名稱與格式是否正確。錯誤訊息: {str(e)}'); window.location.href='/';</script>"
    return "上傳失敗", 400

@app.route('/add_user', methods=['POST'])
def add_user():
    if not session.get('user') or session['user']['role'] != 'admin':
        return "權限不足", 403

    new_email = request.form.get('new_email', '').strip()
    role = request.form.get('role')
    
    if new_email:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO authorized_users (gmail, role) VALUES (?, ?)', (new_email, role))
        conn.commit()
        conn.close()
    
    return "<script>alert('授權設定成功！'); window.location.href='/';</script>"

@app.route('/delete_user', methods=['POST'])
def delete_user():
    if not session.get('user') or session['user']['role'] != 'admin':
        return "權限不足", 403

    email = request.form.get('email')
    if email and email != session['user']['email']:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM authorized_users WHERE gmail = ?', (email,))
        conn.commit()
        conn.close()

    return "<script>alert('已成功刪除該授權帳號！'); window.location.href='/';</script>"

# API: 個人健康紀錄查詢 (可回傳多筆)
@app.route('/api/search_single')
def api_search_single():
    if not session.get('user'):
        return jsonify({'status': 'error', 'message': '請先登入系統'}), 401

    grade = request.args.get('grade')
    class_num = request.args.get('class_num')
    seat = request.args.get('seat')
    name = request.args.get('name')

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    query = 'SELECT name, disease_name, disease_content, care_instructions FROM health_records WHERE grade = ? AND class_num = ? AND seat = ?'
    params = [grade, class_num, seat]

    if name:
        query += ' AND name LIKE ?'
        params.append(f'%{name}%')

    cursor.execute(query, params)
    records = cursor.fetchall()
    conn.close()

    if records:
        student_name = records[0][0]
        rec_list = []
        for r in records:
            rec_list.append({
                'disease_name': r[1],
                'disease_content': r[2],
                'care_instructions': r[3]
            })

        return jsonify({
            'status': 'success',
            'student': {
                'grade': grade,
                'class_num': class_num,
                'seat': seat,
                'name': student_name
            },
            'records': rec_list
        })
    else:
        return jsonify({'status': 'error', 'message': '查無符合條件之學生健康紀錄'})

# API: 班級健康紀錄查詢 (顯示全班)
@app.route('/api/search_class')
def api_search_class():
    if not session.get('user'):
        return jsonify({'status': 'error', 'message': '請先登入系統'}), 401

    grade = request.args.get('grade')
    class_num = request.args.get('class_num')

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT seat, name, disease_name, disease_content, care_instructions
        FROM health_records
        WHERE grade = ? AND class_num = ?
        ORDER BY seat ASC
    ''', (grade, class_num))
    records = cursor.fetchall()
    conn.close()

    if records:
        data = []
        for r in records:
            data.append({
                'seat': r[0],
                'name': r[1],
                'disease_name': r[2],
                'disease_content': r[3],
                'care_instructions': r[4]
            })
        return jsonify({'status': 'success', 'data': data})
    else:
        return jsonify({'status': 'error', 'message': '該班級目前無任何學生健康紀錄'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
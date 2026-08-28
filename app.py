import os
import sqlite3
import pandas as pd
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'  # 請更換為自訂密鑰

DB_FILE = 'student_health.db'

# ==================== 資料庫初始化 ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 建立權限表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS authorized_users (
            gmail TEXT PRIMARY KEY,
            role TEXT NOT NULL
        )
    ''')
    
    # 建立健康資料表 (統一修正欄位名稱)
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
    
    # 預設寫入管理者帳號
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
    <title>學生健康照護查詢系統</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">

<nav class="navbar navbar-dark bg-primary mb-4">
    <div class="container">
        <a class="navbar-brand" href="/">學生健康照護查詢系統</a>
        {% if session.get('user') %}
            <div>
                <span class="text-white me-3">{{ session['user']['email'] }} ({{ session['user']['role'] }})</span>
                <a href="/logout" class="btn btn-outline-light btn-sm">登出</a>
            </div>
        {% endif %}
    </div>
</nav>

<div class="container">
    {% if not session.get('user') %}
        <div class="row justify-content-center mt-5">
            <div class="col-md-6 text-center">
                <div class="card shadow">
                    <div class="card-body py-5">
                        <h3 class="mb-4">請先登入系統</h3>
                        <form action="/dev_login" method="POST">
                            <div class="mb-3">
                                <input type="email" name="email" class="form-control" placeholder="請輸入 Gmail 帳號" required>
                            </div>
                            <button type="submit" class="btn btn-danger btn-lg w-100">模擬 Google 帳號登入</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    {% else %}
        <ul class="nav nav-tabs mb-4" id="myTab" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" id="search-tab" data-bs-toggle="tab" data-bs-target="#search" type="button">學生資料查詢</button>
            </li>
            {% if session['user']['role'] == 'admin' %}
            <li class="nav-item">
                <button class="nav-link" id="admin-tab" data-bs-toggle="tab" data-bs-target="#admin" type="button">後臺管理權限與上傳</button>
            </li>
            {% endif %}
        </ul>

        <div class="tab-content" id="myTabContent">
            <div class="tab-pane fade show active" id="search">
                <div class="card shadow">
                    <div class="card-header bg-white"><h4>學生健康資料查詢</h4></div>
                    <div class="card-body">
                        <div class="row g-3">
                            <div class="col-md-3">
                                <label class="form-label">年級</label>
                                <select id="grade" class="form-select">
                                    <option value="">請選擇年級</option>
                                    {% for g in grades %}<option value="{{ g }}">{{ g }} 年級</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">班級</label>
                                <select id="class_num" class="form-select">
                                    <option value="">請選擇班級</option>
                                    {% for c in classes %}<option value="{{ c }}">{{ c }} 班</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">座號</label>
                                <select id="seat" class="form-select">
                                    <option value="">請選擇座號</option>
                                    {% for s in seats %}<option value="{{ s }}">{{ s }} 號</option>{% endfor %}
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label class="form-label">學生姓名 (選填)</label>
                                <input type="text" id="name" class="form-control" placeholder="輔助比對姓名">
                            </div>
                            <div class="col-12 mt-3">
                                <button type="button" onclick="searchData()" class="btn btn-primary w-100">查詢學生健康紀錄</button>
                            </div>
                        </div>

                        <div id="resultArea" class="mt-4" style="display: none;">
                            <hr>
                            <h5 id="resStudentName" class="text-primary mb-3"></h5>
                            <div class="mb-3">
                                <strong>疾病名稱：</strong>
                                <p id="resDiseaseName" class="text-danger fs-5 fw-bold"></p>
                            </div>
                            <div class="mb-3">
                                <strong>疾病內容：</strong>
                                <p id="resDiseaseContent" class="bg-light p-2 rounded"></p>
                            </div>
                            <div class="mb-3">
                                <strong>照護/注意事項：</strong>
                                <p id="resCare" class="bg-warning-subtle p-2 rounded"></p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {% if session['user']['role'] == 'admin' %}
            <div class="tab-pane fade" id="admin">
                <div class="row">
                    <div class="col-md-6">
                        <div class="card shadow mb-4">
                            <div class="card-header bg-white"><h5>上傳學生健康資料 Excel</h5></div>
                            <div class="card-body">
                                <form action="/upload_excel" method="POST" enctype="multipart/form-data">
                                    <div class="mb-3">
                                        <label class="form-label">請選擇 Excel 檔案 (.xlsx)</label>
                                        <input type="file" name="excel_file" class="form-control" accept=".xlsx" required>
                                        <small class="text-muted">格式要求：標題列需包含「年級、班級、座號、姓名、疾病名稱、疾病內容、照護注意事項」</small>
                                    </div>
                                    <button type="submit" class="btn btn-success">批次匯入/更新資料</button>
                                </form>
                            </div>
                        </div>
                    </div>

                    <div class="col-md-6">
                        <div class="card shadow mb-4">
                            <div class="card-header bg-white"><h5>新增授權 Gmail 帳號</h5></div>
                            <div class="card-body">
                                <form action="/add_user" method="POST">
                                    <div class="mb-3">
                                        <input type="email" name="new_email" class="form-control" placeholder="輸入要授權的 Gmail" required>
                                    </div>
                                    <div class="mb-3">
                                        <select name="role" class="form-select">
                                            <option value="viewer">一般查詢者 (viewer)</option>
                                            <option value="admin">管理者 (admin)</option>
                                        </select>
                                    </div>
                                    <button type="submit" class="btn btn-primary">新增授權</button>
                                </form>
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
function searchData() {
    const grade = document.getElementById('grade').value;
    const class_num = document.getElementById('class_num').value;
    const seat = document.getElementById('seat').value;

    if (!grade || !class_num || !seat) {
        alert("請完整選擇年級、班級與座號！");
        return;
    }

    fetch(`/api/search?grade=${grade}&class_num=${class_num}&seat=${seat}`)
        .then(response => response.json())
        .then(data => {
            const resultArea = document.getElementById('resultArea');
            if (data.status === 'success') {
                document.getElementById('resStudentName').innerText = `${grade} 年級 ${class_num} 班 ${seat} 號 - 學生姓名：${data.data.name}`;
                document.getElementById('resDiseaseName').innerText = data.data.disease_name || "無紀錄";
                document.getElementById('resDiseaseContent').innerText = data.data.disease_content || "無特殊疾病內容";
                document.getElementById('resCare').innerText = data.data.care_instructions || "無特殊照護事項";
                resultArea.style.display = 'block';
            } else {
                alert(data.message);
                resultArea.style.display = 'none';
            }
        });
}
</script>
</body>
</html>
"""

# ==================== 路由與邏輯控制 ====================
@app.route('/')
def index():
    # 傳入選單範圍給 HTML
    return render_template_string(
        HTML_TEMPLATE,
        grades=list(range(1, 13)),
        classes=list(range(1, 9)),
        seats=list(range(1, 41))
    )

@app.route('/dev_login', methods=['POST'])
def dev_login():
    email = request.form.get('email')
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT role FROM authorized_users WHERE gmail = ?', (email,))
    user = cursor.fetchone()
    conn.close()

    if user:
        session['user'] = {'email': email, 'role': user[0]}
    else:
        return "<script>alert('無權限登入！請請管理員新增授權'); window.location.href='/';</script>"
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
        df = pd.read_excel(file)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM health_records')
        
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT INTO health_records (grade, class_num, seat, name, disease_name, disease_content, care_instructions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                int(row['年級']),
                int(row['班級']),
                int(row['座號']),
                str(row['姓名']),
                str(row.get('疾病名稱', '')),
                str(row.get('疾病內容', '')),
                str(row.get('照護注意事項', ''))
            ))
        conn.commit()
        conn.close()
        return "<script>alert('資料上傳成功！'); window.location.href='/';</script>"
    return "上傳失敗", 400

@app.route('/add_user', methods=['POST'])
def add_user():
    if not session.get('user') or session['user']['role'] != 'admin':
        return "權限不足", 403

    new_email = request.form.get('new_email')
    role = request.form.get('role')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO authorized_users (gmail, role) VALUES (?, ?)', (new_email, role))
    conn.commit()
    conn.close()
    
    return "<script>alert('新增帳號成功！'); window.location.href='/';</script>"

@app.route('/api/search')
def api_search():
    if not session.get('user'):
        return jsonify({'status': 'error', 'message': '請先登入'}), 401

    grade = request.args.get('grade')
    class_num = request.args.get('class_num')
    seat = request.args.get('seat')

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, disease_name, disease_content, care_instructions 
        FROM health_records 
        WHERE grade = ? AND class_num = ? AND seat = ?
    ''', (grade, class_num, seat))
    record = cursor.fetchone()
    conn.close()

    if record:
        return jsonify({
            'status': 'success',
            'data': {
                'name': record[0],
                'disease_name': record[1],
                'disease_content': record[2],
                'care_instructions': record[3]
            }
        })
    else:
        return jsonify({'status': 'error', 'message': '查無該年級、班級與座號之學生資料'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
import calendar
from datetime import datetime, timedelta
from flask import Flask, render_template_string, redirect, request, jsonify
from supabase import create_client, Client

app = Flask(__name__)

# ==========================================================
# ⚠️ BƯỚC NÀY QUAN TRỌNG: Hãy thay 2 thông tin bạn vừa lấy từ Supabase vào đây nhé!
SUPABASE_URL = "https://leuwptvyrmqueyfgdeuo.supabase.co/rest/v1/"
SUPABASE_KEY = "sb_publishable_YY_dluN8BsDK7wM04ZyRig_gX6AEzC2"
# ==========================================================

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TASKS = [
    "1. Dậy sớm trước 8:00", "2. Uống một cốc nước", "3. Đánh răng rửa mặt",
    "4. Ăn sáng trước 8:00", "5. Không dùng ĐT 30p đầu ngày", "6. Làm việc",
    "7. Hít đất 200 cái", "8. Kéo xà 100 cái", "9. Uống đủ 2 lít nước",
    "10. Học 30p kiến thức mới & Ghi lại", "11. Dành ra 1 tiếng để học tập"
]

CHILD_CATEGORIES = {
    "Ăn uống": {"color": "#f97316", "parent": "Chi tiêu - sinh hoạt", "icon": "🍲"},
    "Hóa đơn": {"color": "#34d399", "parent": "Chi phí cố định", "icon": "🧾"},
    "Mua sắm": {"color": "#facc15", "parent": "Chi tiêu - sinh hoạt", "icon": "🛒"},
    "Di chuyển": {"color": "#60a5fa", "parent": "Chi tiêu - sinh hoạt", "icon": "🚗"},
    "Giải trí": {"color": "#fb7185", "parent": "Chi phí phát sinh", "icon": "🎬"},
    "Chưa phân loại": {"color": "#f472b6", "parent": "Chưa phân loại", "icon": "❔"}
}

PARENT_CATEGORIES = {
    "Chi tiêu - sinh hoạt": {"color": "#f97316", "icon": "📄"},
    "Chi phí phát sinh": {"color": "#facc15", "icon": "💰"},
    "Chi phí cố định": {"color": "#60a5fa", "icon": "🏠"},
    "Chưa phân loại": {"color": "#f472b6", "icon": "❔"}
}

INCOME_CATEGORIES = {
    "Tiền lương": {"color": "#22c55e", "icon": "💵"},
    "Tiền thưởng": {"color": "#3b82f6", "icon": "🎁"},
    "Đầu tư/Lãi": {"color": "#8b5cf6", "icon": "📈"},
    "Khác (Thu)": {"color": "#ec4899", "icon": "💰"}
}

def process_financials(data):
    if not data:
        return {"status": [False]*len(TASKS), "expenses": [], "total_in": 0, "total_out": 0, "list_in": [], "list_out": []}
    if "expenses" not in data or data["expenses"] is None:
        data["expenses"] = []
    if "status" not in data or data["status"] is None:
        data["status"] = [False]*len(TASKS)
        
    data["list_in"] = [e for e in data["expenses"] if e.get("type") == "in"]
    data["list_out"] = [e for e in data["expenses"] if e.get("type", "out") == "out"]
    data["total_in"] = sum(e.get("amount", 0) for e in data["list_in"])
    data["total_out"] = sum(e.get("amount", 0) for e in data["list_out"])
    return data

def get_or_create_data(date_str):
    response = supabase.table("user_tasks").select("*").eq("date_str", date_str).execute()
    if response.data:
        row = response.data[0]
        return process_financials({
            "date": row["date_str"], "status": row["status"], "expenses": row["expenses"]
        })
    else:
        default_status = [False] * len(TASKS)
        default_expenses = []
        new_row = {"date_str": date_str, "status": default_status, "expenses": default_expenses}
        supabase.table("user_tasks").insert(new_row).execute()
        return process_financials({"date": date_str, "status": default_status, "expenses": default_expenses})

def save_data(date_str, data):
    payload = {
        "status": data.get("status", [False]*len(TASKS)),
        "expenses": data.get("expenses", [])
    }
    supabase.table("user_tasks").update(payload).eq("date_str", date_str).execute()

def generate_chart_info(totals_dict, color_map, total_amount):
    active_cats = {k: v for k, v in totals_dict.items() if v > 0}
    sorted_cats = sorted(active_cats.items(), key=lambda x: x[1], reverse=True)
    chart_data = []
    conic_gradient = []
    current_percent = 0
    
    for cat, amount in sorted_cats:
        pct = (amount / total_amount) * 100 if total_amount > 0 else 0
        info = color_map.get(cat, {"color": "#9ca3af", "icon": "📦"})
        chart_data.append({
            "name": cat, "amount": amount, "pct": round(pct), "color": info["color"], "icon": info["icon"]
        })
        next_percent = current_percent + pct
        if len(sorted_cats) > 1 and pct > 1.5:
            conic_gradient.append(f"{info['color']} {current_percent}% {next_percent - 1.5}%")
            conic_gradient.append(f"white {next_percent - 1.5}% {next_percent}%")
        else:
            conic_gradient.append(f"{info['color']} {current_percent}% {next_percent}%")
        current_percent = next_percent

    if not conic_gradient:
        conic_gradient = ["#e2e8f0 0% 100%"]
    return chart_data, ", ".join(conic_gradient)

def get_financials_in_range(start_date, end_date):
    total_in = 0
    total_out = 0
    child_totals = {cat: 0 for cat in CHILD_CATEGORIES.keys()}
    parent_totals = {cat: 0 for cat in PARENT_CATEGORIES.keys()}
    income_totals = {cat: 0 for cat in INCOME_CATEGORIES.keys()}
    all_transactions = []
    
    response = supabase.table("user_tasks").select("*").gte("date_str", start_date.strftime("%Y-%m-%d")).lte("date_str", end_date.strftime("%Y-%m-%d")).execute()
    db_data = {row["date_str"]: row for row in response.data}
    
    current_date = start_date
    while current_date <= end_date:
        d_str = current_date.strftime("%Y-%m-%d")
        if d_str in db_data:
            data = db_data[d_str]
            expenses_list = data.get("expenses") or []
            for e in expenses_list:
                amt = e.get("amount", 0)
                t_type = e.get("type", "out")
                t_detail = {"date": d_str, "time": e.get("time", ""), "desc": e.get("desc", "Không có diễn giải"), "amount": amt, "type": t_type}

                if t_type == "in":
                    total_in += amt
                    cat = e.get("category", "Khác (Thu)")
                    if cat not in INCOME_CATEGORIES: cat = "Khác (Thu)"
                    income_totals[cat] += amt
                    t_detail["category"] = cat
                    t_detail["icon"] = INCOME_CATEGORIES[cat]["icon"]
                else:
                    total_out += amt
                    cat = e.get("category", "Chưa phân loại")
                    if cat not in CHILD_CATEGORIES: cat = "Chưa phân loại"
                    child_totals[cat] += amt
                    parent_cat = CHILD_CATEGORIES[cat]["parent"]
                    parent_totals[parent_cat] += amt
                    t_detail["category"] = cat
                    t_detail["parent_category"] = parent_cat
                    t_detail["icon"] = CHILD_CATEGORIES[cat]["icon"]
                all_transactions.append(t_detail)
        current_date += timedelta(days=1)

    child_chart_data, child_gradient = generate_chart_info(child_totals, CHILD_CATEGORIES, total_out)
    parent_chart_data, parent_gradient = generate_chart_info(parent_totals, PARENT_CATEGORIES, total_out)
    income_chart_data, income_gradient = generate_chart_info(income_totals, INCOME_CATEGORIES, total_in)
    all_transactions.sort(key=lambda x: (x["date"], x["time"]), reverse=True)

    return {
        "total_in": total_in, "total_out": total_out,
        "child_chart_data": child_chart_data, "child_gradient": child_gradient,
        "parent_chart_data": parent_chart_data, "parent_gradient": parent_gradient,
        "income_chart_data": income_chart_data, "income_gradient": income_gradient,
        "transactions": all_transactions
    }

def get_all_expense_data(year, month):
    today = datetime.today()
    _, num_days = calendar.monthrange(year, month)
    exp_monthly = get_financials_in_range(datetime(year, month, 1), datetime(year, month, num_days))
    
    curr_month_days = calendar.monthrange(today.year, today.month)[1]
    prev_m_date = datetime(today.year, today.month, 1) - timedelta(days=1)
    prev_month_days = calendar.monthrange(prev_m_date.year, prev_m_date.month)[1]

    curr_week_start = today - timedelta(days=today.weekday())
    prev_week_start = curr_week_start - timedelta(days=7)

    return {
        "exp_monthly": exp_monthly,
        "bdData": {
            "month": {
                "curr": get_financials_in_range(datetime(today.year, today.month, 1), datetime(today.year, today.month, curr_month_days)),
                "prev": get_financials_in_range(datetime(prev_m_date.year, prev_m_date.month, 1), datetime(prev_m_date.year, prev_m_date.month, prev_month_days))
            },
            "week": {
                "curr": get_financials_in_range(curr_week_start, curr_week_start + timedelta(days=6)),
                "prev": get_financials_in_range(prev_week_start, prev_week_start + timedelta(days=6))
            },
            "year": {
                "curr": get_financials_in_range(datetime(today.year, 1, 1), datetime(today.year, 12, 31)),
                "prev": get_financials_in_range(datetime(today.year - 1, 1, 1), datetime(today.year - 1, 12, 31))
            }
        }
    }

# ==========================================================
# ⚠️ HÃY THAY TOÀN BỘ CHUỖI GIAO DIỆN HTML GỐC CỦA BẠN VÀO GIỮA CẶP DẤU """ KHỔNG LỒ NÀY NHÉ
# Đừng quên thêm 4 dòng thẻ <meta> và đoạn <script> đăng ký sw.js như mình hướng dẫn ở trên vào HTML của bạn nhé!
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bình Kỷ Luật</title>
    <link rel="manifest" href="/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#d82d8b">
</head>
<body>
    <h1>App Kỷ Luật Đã Sẵn Sàng</h1>
    <p>Hãy dán toàn bộ mã giao diện HTML đẹp đẽ trước đó của bạn vào đây thay thế cho đoạn này.</p>
    
    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => { navigator.serviceWorker.register('/sw.js'); });
        }
    </script>
</body>
</html>
"""
# ==========================================================

def get_prev_next_month(year, month):
    curr = datetime(year, month, 1)
    prev_m = curr - timedelta(days=1)
    num_days = calendar.monthrange(year, month)[1]
    next_m = curr + timedelta(days=num_days)
    return prev_m.year, prev_m.month, next_m.year, next_m.month

@app.route('/')
def index():
    today = datetime.today()
    start_week = today - timedelta(days=today.weekday())
    week_data = []
    selected_date = request.args.get('date', today.strftime("%Y-%m-%d"))
    day_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ Nhật"]
    
    for i in range(7):
        d = start_week + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        week_data.append({"date": d_str, "name": day_names[i], "data": get_or_create_data(d_str)})
    return render_template_string(HTML_TEMPLATE, active="tasks", week_data=week_data, tasks=TASKS, selected_date=selected_date)

@app.route('/expenses')
def expenses():
    today = datetime.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)
    tab = request.args.get('tab', 'out')
    sec = request.args.get('sec', 'tinh-hinh')
    
    prev_y, prev_m, next_y, next_m = get_prev_next_month(year, month)
    all_expense_data = get_all_expense_data(year, month)
    return render_template_string(HTML_TEMPLATE, active="exp", selected_year=year, selected_month=month, prev_year=prev_y, prev_month=prev_m, next_year=next_y, next_month=next_m, init_tab=tab, init_sec=sec, exp_monthly=all_expense_data["exp_monthly"], bdData=all_expense_data["bdData"])

@app.route('/api/expenses_data')
def api_expenses_data():
    year = request.args.get('year', datetime.today().year, type=int)
    month = request.args.get('month', datetime.today().month, type=int)
    return jsonify(get_all_expense_data(year, month))

@app.route('/add', methods=['POST'])
def add_transaction():
    t_type = request.form.get('type', 'out')
    desc = request.form.get('desc', 'Không rõ')
    try: amount = float(request.form.get('amount', 0))
    except ValueError: amount = 0
    category = request.form.get('category_out', 'Chưa phân loại') if t_type == 'out' else request.form.get('category_in', 'Khác (Thu)')
    
    today_str = datetime.today().strftime("%Y-%m-%d")
    data = get_or_create_data(today_str)
    data["expenses"].append({"type": t_type, "category": category, "desc": desc, "amount": amount, "time": datetime.now().strftime("%H:%M")})
    save_data(today_str, data)
    return jsonify({"success": True})

@app.route('/complete/<date_str>/<int:index>')
def complete_task(date_str, index):
    uncheck = request.args.get('uncheck', '0')
    data = get_or_create_data(date_str)
    if index < len(data["status"]):
        data["status"][index] = (uncheck != '1')
        save_data(date_str, data)
    return jsonify({"success": True})

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "Bình Kỷ Luật", "short_name": "Kỷ Luật", "start_url": "/", "display": "standalone",
        "background_color": "#f8f9fa", "theme_color": "#d82d8b",
        "icons": [{"src": "https://cdn-icons-png.flaticon.com/512/10166/10166680.png", "sizes": "512x512", "type": "image/png"}]
    })

@app.route('/sw.js')
def sw():
    return app.response_class("self.addEventListener('fetch', function() {});", mimetype='application/javascript')

if __name__ == '__main__':
    app.run(debug=True, port=8080)

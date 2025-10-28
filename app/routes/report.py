import os
import csv
from io import StringIO
from urllib.parse import quote
from flask import Blueprint, render_template, jsonify, request, flash, Response, stream_with_context, redirect, url_for
from flask_login import login_required
# 确保导入了所有模型，包括 Member
from app.models import Order, OrderItem, Product, Member
from app.extensions import db
from datetime import datetime, timedelta
from sqlalchemy import func, extract, cast
from sqlalchemy.types import Date
# 引入 DeepSeek 兼容的客户端
from openai import OpenAI
# 假设 OrderSearchForm 存在于 app.forms 中
from app.forms import OrderSearchForm

report = Blueprint('report', __name__)

# --- DeepSeek 客户端初始化 ---
# 注意：确保您在运行环境中设置了 DEEPSEEK_API_KEY 环境变量
client = OpenAI(
    api_key=os.environ.get('DEEPSEEK_API_KEY'),
    base_url="https://api.deepseek.com"
)


# --- 1. 数据看板主页 (E.1, E.2) ---
@report.route('/dashboard')
@login_required
def dashboard():
    """数据看板主页，加载可视化图表"""

    # 简单的总览数据 (可直接查询并传递给模板)
    total_sales = db.session.query(func.sum(Order.final_amount)).scalar() or 0
    completed_orders = db.session.query(func.count(Order.id)).filter_by(status='Completed').scalar() or 0

    # 获取今天零点
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sales = db.session.query(func.sum(Order.final_amount)).filter(Order.order_date >= today).scalar() or 0

    context = {
        'title': '数据看板',
        'total_sales': f"{total_sales:,.2f}",
        'completed_orders': completed_orders,
        'today_sales': f"{today_sales:,.2f}"
    }
    return render_template('report/dashboard.html', **context)


# --- 2. API 接口：销售趋势数据 (E.1 可视化数据) ---
@report.route('/api/sales_trend', methods=['GET'])
@login_required
def sales_trend():
    """提供近30天销售额趋势数据"""

    # 计算30天前的日期
    thirty_days_ago = datetime.now() - timedelta(days=30)

    # SQL 查询：按日期聚合销售总额
    sales_data = db.session.query(
        cast(Order.order_date, Date).label('date'),
        func.sum(Order.final_amount).label('total_amount')
    ).filter(
        Order.status == 'Completed',
        Order.order_date >= thirty_days_ago
    ).group_by(
        'date'
    ).order_by(
        'date'
    ).all()

    # 填充数据，确保连续30天都有数据点（即使为0）
    date_map = {str(row.date): float(row.total_amount) for row in sales_data}

    dates = []
    amounts = []
    current_date = thirty_days_ago

    while current_date <= datetime.now():
        date_str = current_date.strftime('%Y-%m-%d')
        dates.append(date_str)
        amounts.append(date_map.get(date_str, 0.00))
        current_date += timedelta(days=1)

    return jsonify({
        'success': True,
        'dates': dates,
        'amounts': amounts
    })


# --- 3. API 接口：商品利润/销量排行 (E.2, E.3 可视化数据) ---
@report.route('/api/product_ranking', methods=['GET'])
@login_required
def product_ranking():
    """提供销量和利润排行的聚合数据"""

    # 默认查看最近90天数据
    ninety_days_ago = datetime.now() - timedelta(days=90)

    # 聚合订单详情 (OrderItem)
    ranking_data = db.session.query(
        Product.name.label('product_name'),
        func.sum(OrderItem.quantity).label('total_quantity'),
        # 计算毛利润: (销售单价 - 成本单价) * 数量
        func.sum((OrderItem.price_at_sale - OrderItem.cost_at_sale) * OrderItem.quantity).label('gross_profit')
    ).join(
        Product, Product.id == OrderItem.product_id
    ).join(
        Order, Order.id == OrderItem.order_id
    ).filter(
        Order.status == 'Completed',
        Order.order_date >= ninety_days_ago
    ).group_by(
        Product.name
    ).all()

    # 分离数据，并按需排序
    quantity_rank = sorted([
        {'name': row.product_name, 'value': float(row.total_quantity)}
        for row in ranking_data
    ], key=lambda x: x['value'], reverse=True)[:10]  # Top 10 销量

    profit_rank = sorted([
        {'name': row.product_name, 'value': float(row.gross_profit)}
        for row in ranking_data
    ], key=lambda x: x['value'], reverse=True)[:10]  # Top 10 利润

    return jsonify({
        'success': True,
        'quantity_rank': quantity_rank,
        'profit_rank': profit_rank
    })


# --- 4. API 接口：AI 销售数据分析 ---
@report.route('/api/sales_summary_ai', methods=['GET'])
@login_required
def sales_summary_ai():
    """获取AI对销售数据的评价和建议"""

    # 1. 获取核心数据
    total_sales = db.session.query(func.sum(Order.final_amount)).scalar() or 0
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_sales = db.session.query(func.sum(Order.final_amount)).filter(
        Order.order_date >= today
    ).scalar() or 0

    thirty_days_ago = datetime.now() - timedelta(days=30)
    total_sales_30 = db.session.query(
        func.sum(Order.final_amount)
    ).filter(
        Order.status == 'Completed',
        Order.order_date >= thirty_days_ago
    ).scalar() or 0

    num_days = (datetime.now() - thirty_days_ago).days
    avg_daily_sales_30 = total_sales_30 / num_days if num_days > 0 else 0

    # 获取Top 3 商品名称和销量
    ranking_data = db.session.query(
        Product.name.label('product_name'),
        func.sum(OrderItem.quantity).label('total_quantity')
    ).join(
        Product, Product.id == OrderItem.product_id
    ).join(
        Order, Order.id == OrderItem.order_id
    ).filter(
        Order.status == 'Completed',
        Order.order_date >= thirty_days_ago
    ).group_by(
        Product.name
    ).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(3).all()

    top_products_str = ", ".join([f"{row.product_name} ({int(row.total_quantity)}件)" for row in ranking_data])

    # 2. 构建 Prompt
    prompt_template = """
    请你作为一名零售行业分析师，根据以下销售数据，对业务表现进行评价，并提出 actionable 的运营建议。

    **数据总览 (基于已完成订单):**
    - 累计总销售额: ¥{total_sales:,.2f}
    - 今日销售额: ¥{today_sales:,.2f}
    - 近30天总销售额: ¥{total_sales_30:,.2f}
    - 近30天平均日销售额: ¥{avg_daily_sales_30:,.2f}
    - 近30天畅销商品 Top 3: {top_products}

    **分析要求:**
    1. **评价**: 总结当前业务亮点和潜在风险。
    2. **建议**: 针对 Top 畅销品和销售趋势，给出具体的促销或库存管理建议。
    3. **格式**: 以纯中文文本形式清晰返回，不要包含任何前言和后记，不要用markdowm格式。
    """

    prompt = prompt_template.format(
        total_sales=total_sales,
        today_sales=today_sales,
        total_sales_30=total_sales_30,
        avg_daily_sales_30=avg_daily_sales_30,
        top_products=top_products_str
    )

    # 3. 调用 DeepSeek API
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system",
                 "content": "You are a professional retail data analyst. Analyze the data and provide concise, actionable feedback in Chinese Markdown format."},
                {"role": "user", "content": prompt},
            ],
            stream=False
        )
        ai_analysis_result = response.choices[0].message.content

    except Exception as e:
        ai_analysis_result = f"AI 分析服务调用失败，请检查 DEEPSEEK_API_KEY 配置和网络连接。错误详情: {e}"
        print(f"DeepSeek API Error: {e}")

        # 4. 返回结果
    return jsonify({
        'success': True,
        'analysis': ai_analysis_result
    })


# --- 5. 数据导出功能 (E.4) ---
# 辅助函数：生成 CSV 数据流 (这里假设已包含您最新的修复，能正确导出商品数据)
def generate_csv(query, headers, field_names, data_type):
    data_stream = StringIO()
    writer = csv.writer(data_stream)

    # 写入 CSV 文件头
    writer.writerow(headers)
    yield data_stream.getvalue()
    data_stream.seek(0)
    data_stream.truncate(0)

    # 写入数据行
    for item in query.all():
        row = []
        if data_type == 'products':
            for field in field_names:
                value = getattr(item, field, '')

                if isinstance(value, (float)):
                    row.append(f'{value:.2f}')
                elif isinstance(value, int):
                    row.append(str(value))
                elif isinstance(value, datetime):
                    row.append(value.strftime('%Y-%m-%d %H:%M:%S'))
                else:
                    row.append(str(value))

        elif data_type == 'sales':
            # 处理销售数据行
            member_name = item.member.name if item.member else '非会员'
            member_phone = item.member.phone_number if item.member else ''

            row = [
                item.id,
                item.order_date.strftime('%Y-%m-%d %H:%M:%S'),
                member_name,
                member_phone,
                f'{item.original_amount:.2f}',
                f'{item.discount_amount:.2f}',
                f'{item.final_amount:.2f}',
                item.status
            ]

        writer.writerow(row)
        yield data_stream.getvalue()
        data_stream.seek(0)
        data_stream.truncate(0)


@report.route('/export/<string:data_type>', methods=['GET'])
@login_required
def export_data(data_type):
    """数据导出 CSV/Excel"""

    # --- 1. 导出商品数据 (PRODUCTS) ---
    if data_type == 'products':
        query = Product.query.order_by(Product.id.asc())

        # 确保 field_names 与您的模型属性一致
        headers = ['商品ID', '名称', '分类id', '进货成本', '零售单价', '单位', '总库存']
        field_names = ['id', 'name', 'category_id', 'cost_price', 'price', 'unit', 'stock_quantity']
        filename_raw = f'商品数据_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv'
        filename_encoded = quote(filename_raw)
        disposition = f"attachment; filename*=utf-8''{filename_encoded}"

        response = Response(
            stream_with_context(generate_csv(query, headers, field_names, data_type)),
            mimetype='text/csv',
            headers={
                "Content-Disposition": disposition,
                "Content-type": "text/csv; charset=UTF-8"
            }
        )
        return response

    # --- 2. 导出销售数据 (SALES) ---
    elif data_type == 'sales':
        # 重建订单查询逻辑
        form = OrderSearchForm(request.args)
        query = Order.query.order_by(Order.id.desc())

        # 应用筛选逻辑
        if form.order_id.data:
            try:
                order_id_int = int(form.order_id.data)
                query = query.filter(Order.id == order_id_int)
            except ValueError:
                pass

        if form.member_phone.data:
            phone_search_term = form.member_phone.data
            search_pattern = f'%{phone_search_term}%'
            matching_member_ids = db.session.query(Member.id).filter(Member.phone_number.like(search_pattern)).all()
            member_id_list = [mid[0] for mid in matching_member_ids]
            if member_id_list:
                query = query.filter(Order.member_id.in_(member_id_list))
            else:
                query = query.filter(Order.member_id == -1)

                # 日期筛选... (如果需要，请在这里添加)

        # 定义 CSV 文件头
        headers = ['订单ID', '交易时间', '会员姓名', '会员手机', '原始总额', '折扣金额', '实付金额', '订单状态']
        field_names = []

        filename_raw = f'销售订单数据_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv'
        filename_encoded = quote(filename_raw)
        disposition = f"attachment; filename*=utf-8''{filename_encoded}"

        response = Response(
            stream_with_context(generate_csv(query, headers, field_names, data_type)),
            mimetype='text/csv',
            headers={
                "Content-Disposition": disposition,
                "Content-type": "text/csv; charset=UTF-8"
            }
        )
        return response

    else:
        flash("无效的导出类型。", 'danger')
        return redirect(url_for('.dashboard'))

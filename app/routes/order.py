# app/routes/order.py
import decimal

from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required
from app.models import Product, Member, Order, OrderItem
from app.forms import OrderSearchForm
from app.extensions import db
from sqlalchemy.exc import IntegrityError
from datetime import datetime, date, timedelta

order = Blueprint('order', __name__)


# --- 1. 销售开单/订单创建视图 (D.1, D.2, D.3 核心) ---
@order.route('/create', methods=['GET'])
@login_required
def create_order():
    """销售开单页面 (主要依赖前端 AJAX)"""
    # 预加载所有商品信息供前端使用
    products = Product.query.filter(Product.stock_quantity > 0).all()

    # 转换为字典列表，只传递必要信息，避免暴露 cost_price 给前端 (安全优化)
    products_data = [
        {
            'id': p.id,
            'name': p.name,
            'unit': p.unit,
            'retail_price': float(p.retail_price),
            'stock': p.stock_quantity
        } for p in products
    ]

    # 获取所有会员信息（用于前端搜索）
    members = Member.query.all()

    return render_template('order/create.html',
                           title='销售开单',
                           products_data=products_data,
                           members=members)


# --- 2. AJAX 接口：查找会员 (D.1 辅助) ---
@order.route('/api/member_lookup', methods=['GET'])
@login_required
def member_lookup():
    phone = request.args.get('phone')
    member_obj = Member.query.filter_by(phone_number=phone).first()

    if member_obj:
        return jsonify({
            'success': True,
            'id': member_obj.id,
            'name': member_obj.name,
            'discount': float(member_obj.discount_rate)
        })
    return jsonify({'success': False, 'message': '未找到该手机号码的会员'}), 404


# --- 3. AJAX 接口：提交订单 (D.3 核心事务处理) ---
@order.route('/api/submit_order', methods=['POST'])
@login_required
def submit_order():
    data = request.get_json()
    items = data.get('items')
    member_id = data.get('member_id')
    final_amount = data.get('final_amount')

    if not items:
        return jsonify({'success': False, 'message': '订单不能为空！'}), 400

    try:
        # 1. 创建订单头
        order_obj = Order(
            member_id=member_id if member_id else None,
            original_amount=data['original_amount'],
            discount_amount=data['discount_amount'],
            final_amount=final_amount,
            status='Completed'
        )
        db.session.add(order_obj)
        db.session.flush()  # 立即获取 order_obj.id

        # 2. 批量处理订单详情和库存扣减 (事务关键)
        for item_data in items:
            product_id = item_data['product_id']
            quantity = item_data['quantity']

            product = db.session.get(Product, product_id)
            if not product or product.stock_quantity < quantity:
                # 检查库存
                db.session.rollback()
                return jsonify({'success': False,
                                'message': f'商品 "{product.name}" 库存不足 ({quantity} > {product.stock_quantity})'}), 400

            # 扣减库存
            product.stock_quantity -= quantity

            # 查找销售时点的成本价
            cost_at_sale = product.cost_price

            # 创建订单详情项
            order_item = OrderItem(
                order_id=order_obj.id,
                product_id=product_id,
                quantity=quantity,
                price_at_sale=item_data['price'],
                cost_at_sale=cost_at_sale,
                line_subtotal=item_data['subtotal']
            )
            db.session.add(order_item)

        # 3. 更新会员累计消费 (D.2 辅助)
        if member_id:
            member_obj = db.session.get(Member, member_id)
            if member_obj:
                member_obj.total_spent += decimal.Decimal(final_amount)
                db.session.add(member_obj)

        # 4. 提交所有更改
        db.session.commit()
        return jsonify({'success': True, 'message': '订单创建成功', 'order_id': order_obj.id})

    except Exception as e:
        db.session.rollback()
        # 记录详细日志（生产环境）
        print(f"订单创建失败: {e}")
        return jsonify({'success': False, 'message': f'订单处理失败，请检查数据。错误: {str(e)}'}), 500


# --- 4. 订单列表查询 (D.4) ---
@order.route('/list', methods=['GET', 'POST'])
@login_required
def list_orders():
    # 为了让 GET 请求（点击分页链接）也能正确加载筛选条件，
    # 我们应该在 GET 请求时从 URL 参数中加载表单数据
    if request.method == 'POST':
        form = OrderSearchForm(request.form)
    else:
        # 从 URL 参数中加载数据，这样分页链接才能保留筛选条件
        form = OrderSearchForm(request.args)

    # 获取当前页码和每页数量
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示 10 个订单

    # 默认查询
    query = Order.query.order_by(Order.id.asc())

    # --- 应用筛选逻辑 ---
    # 我们使用 form.data 来获取数据，并总是应用筛选逻辑，
    # 这样GET请求（分页链接）也能保留筛选状态。
    if form.order_id.data:
        target_index = int(form.order_id.data)
        if target_index >= 1:
            # 1. 使用 original_query 来查找目标记录
            target_order = query.offset(target_index - 1).limit(1).first()

            if target_order:
                # 2. 将 query 变量（用于分页）替换为一个新的、精确的查询对象
                query = Order.query.filter(Order.id == target_order.id)
            else:
                # 3. 如果没找到，替换为一个空查询
                query = Order.query.filter(Order.id == -1)
        else:
            # 3. 如果没找到，替换为一个空查询
            query = Order.query.filter(Order.id == -1)

    if form.member_phone.data:
        # 联合查询会员手机号
        phone_search_term = form.member_phone.data
        search_pattern = f'%{phone_search_term}%'
        # 1. 找到所有匹配模糊手机号的会员ID
        #    使用 .filter(Member.phone_number.like(...))
        # 获取所有匹配的 ID 列表
        matching_member_ids = db.session.query(Member.id).filter(Member.phone_number.like(search_pattern)).all()
        # 提取 ID 列表 (例如：[1, 5, 12])
        member_id_list = [mid[0] for mid in matching_member_ids]
        # 2. 应用到订单查询
        if member_id_list:
            # 如果找到匹配的会员，查询这些会员的所有订单
            query = query.filter(Order.member_id.in_(member_id_list))
        else:
            # 如果没有找到任何匹配的会员，则返回空结果集
            query = query.filter(Order.member_id == -1)

    # 日期筛选逻辑
    start_dt = None
    end_dt = None

    # 尝试从表单或 URL 中获取日期数据
    start_date_str = form.start_date.data
    end_date_str = form.end_date.data

    # 处理起始日期
    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Order.order_date >= start_dt)
        except ValueError:
            # 只有在 POST 提交时才闪烁错误，GET 请求（分页）时不闪烁
            if request.method == 'POST':
                flash("起始日期格式错误，请使用 YYYY-MM-DD。", 'danger')

    # 处理结束日期
    if end_date_str:
        try:
            # 结束日期包含当天
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Order.order_date < end_dt)
        except ValueError:
            if request.method == 'POST':
                flash("结束日期格式错误，请使用 YYYY-MM-DD。", 'danger')

    # 4. 执行分页查询 (替换 query.all())
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    orders = pagination.items

    return render_template('order/list.html',
                           title='订单记录',
                           orders=orders,
                           form=form,
                           pagination=pagination)  # 传递分页对象


# --- 5. 订单详情与删除 (D.5) ---
@order.route('/detail/<int:order_id>')
@login_required
def order_detail(order_id):
    order_obj = db.session.get(Order, order_id)
    if order_obj is None:
        flash('订单不存在。', 'danger')
        return redirect(url_for('.list_orders'))

    # 关联查询订单详情
    items = order_obj.items.all()

    # 计算毛利润 (用于内部详情查看，不暴露给顾客)
    total_cost = sum(float(item.cost_at_sale) * item.quantity for item in items)
    gross_profit = order_obj.final_amount - decimal.Decimal(total_cost)

    return render_template('order/detail.html',
                           title=f'订单 #{order_id} 详情',
                           order=order_obj,
                           items=items,
                           gross_profit=gross_profit)


@order.route('/delete/<int:order_id>', methods=['POST'])
@login_required
def delete_order(order_id):
    order_obj = db.session.get(Order, order_id)
    if order_obj is None:
        flash('订单不存在。', 'danger')
        return redirect(url_for('.list_orders'))

    # **核心事务：删除订单并回滚库存**
    try:
        if order_obj.status == 'Completed':
            # 1. 回滚库存
            for item in order_obj.items:
                product = item.product
                product.stock_quantity += item.quantity

            # 2. 回滚会员消费
            if order_obj.member:
                order_obj.member.total_spent -= order_obj.final_amount

            # 3. 彻底删除订单 (CASCADE 自动删除 OrderItems)
            db.session.delete(order_obj)
            db.session.commit()
            flash(f'订单 #{order_id} 已成功删除并回滚库存。', 'success')
        else:
            flash(f'订单 #{order_id} 状态不允许删除。', 'warning')

    except Exception as e:
        db.session.rollback()
        flash(f'订单删除失败: {e}', 'danger')

    return redirect(url_for('.list_orders'))

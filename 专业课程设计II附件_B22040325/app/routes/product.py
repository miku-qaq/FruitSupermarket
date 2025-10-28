# app/routes/product.py

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.models import Product, Category
from app.forms import ProductForm, CategoryForm,ProductSearchForm
from app.extensions import db
from wtforms_sqlalchemy.fields import QuerySelectField  # 用于动态选择分类

# 创建蓝图
product = Blueprint('product', __name__)


# --- 辅助函数：动态生成分类选项 ---
def category_choices():
    return Category.query.all()


# --- 商品列表视图 (包含搜索和分页) ---
@product.route('/list', methods=['GET'])
@login_required
def list_products():
    """显示所有商品的列表，支持搜索和分页"""

    # 1. 初始化表单和分页参数
    form = ProductSearchForm(request.args)  # 从 URL 参数中加载搜索数据
    page = request.args.get('page', 1, type=int)
    per_page = 10 # 每页显示数量，默认为 10

    query = Product.query.order_by(Product.id.asc())

    # 2. 应用搜索条件
    search_term = form.search_term.data
    if search_term:
        # 关键词搜索：搜索名称包含关键词 或 ID 匹配关键词
        search_pattern = f'%{search_term}%'
        query = query.filter(Product.name.like(search_pattern))

    # 3. 执行分页查询
    # 使用 paginate 方法
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)

    products = pagination.items

    return render_template('product/list.html',
                           title='商品列表',
                           products=products,
                           form=form,  # 传递搜索表单
                           pagination=pagination)  # 传递分页对象


# --- 商品创建/编辑视图 ---
@product.route('/create', methods=['GET', 'POST'])
@product.route('/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def manage_product(product_id=None):
    if product_id:
        product = db.session.get(Product, product_id)
        if product is None:
            flash('商品不存在。', 'danger')
            return redirect(url_for('.list_products'))
        title = '编辑商品'
    else:
        product = Product()
        title = '创建新商品'

    # **优化：动态设置分类选项**
    class DynamicProductForm(ProductForm):
        # 覆盖 category_id 字段，使其成为一个下拉选择框
        category_id = QuerySelectField(
            '商品分类',
            query_factory=category_choices,
            get_pk=lambda a: a.id,
            get_label=lambda a: a.name,
            allow_blank=False,
            validators=[]  # 假设分类不能为空，已在 model 中设定
        )

    form = DynamicProductForm(obj=product)

    if form.validate_on_submit():
        # 数据填充
        form.populate_obj(product)
        # 手动处理 category_id 字段的赋值 (QuerySelectField 返回的是对象)
        product.category_id = form.category_id.data.id

        # 确保库存量不小于 0
        if product.stock_quantity < 0:
            flash('库存量不能为负数。', 'danger')
            return render_template('product/manage.html', title=title, form=form, product=product)

        try:
            db.session.add(product)
            db.session.commit()
            flash(f'商品 "{product.name}" 已保存成功！', 'success')
            return redirect(url_for('.list_products'))
        except Exception as e:
            db.session.rollback()
            flash(f'保存失败: {e}', 'danger')

    return render_template('product/manage.html', title=title, form=form, product=product)


# --- 商品删除视图 ---
@product.route('/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        flash('商品不存在。', 'danger')
    else:
        try:
            # 检查是否有订单关联，如果简化版，暂时允许删除
            # 严格模式下应检查是否有 OrderItem 关联，并阻止删除
            db.session.delete(product)
            db.session.commit()
            flash(f'商品 "{product.name}" 已成功删除。', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'删除失败，可能该商品仍有历史订单关联: {e}', 'danger')

    return redirect(url_for('.list_products'))



# --- 分类管理视图 ---
@product.route('/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    form = CategoryForm()
    if form.validate_on_submit():
        # 检查分类是否已存在
        if Category.query.filter_by(name=form.name.data).first():
            flash('该分类已存在。', 'warning')
        else:
            new_category = Category(name=form.name.data)
            db.session.add(new_category)
            db.session.commit()
            flash(f'分类 "{new_category.name}" 已创建。', 'success')
        return redirect(url_for('.manage_categories'))

    categories = Category.query.all()
    return render_template('product/categories.html', title='商品分类管理', form=form, categories=categories)


# --- 分类删除视图 ---
@product.route('/categories/delete/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None:
        flash('分类不存在。', 'danger')
    else:
        # 检查该分类下是否有商品
        if category.products.count() > 0:
            flash(f'无法删除分类 "{category.name}"，请先删除或转移该分类下的所有商品。', 'danger')
        else:
            try:
                db.session.delete(category)
                db.session.commit()
                flash(f'分类 "{category.name}" 已成功删除。', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'删除失败: {e}', 'danger')

    return redirect(url_for('.manage_categories'))
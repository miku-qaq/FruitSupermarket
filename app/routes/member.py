# app/routes/member.py

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app.models import Member
from app.forms import MemberForm, MemberSearchForm
from app.extensions import db
from sqlalchemy.exc import IntegrityError  # 捕获唯一约束错误
from flask import request

member = Blueprint('member', __name__)


# --- 会员列表视图 (C.2 会员消费记录查询 - 聚合信息) ---
@member.route('/list', methods=['GET'])  # 确保允许 GET 请求
@login_required
def list_members():
    """显示所有会员列表，支持手机号搜索和分页"""
    # 1. 初始化表单和分页参数
    form = MemberSearchForm(request.args)  # 从 URL 参数中加载搜索数据
    page = request.args.get('page', 1, type=int)
    per_page = 10  # 每页显示数量

    # 默认查询：按累计消费金额升序排列
    query = Member.query.order_by(Member.id.asc())

    # 2. 应用搜索条件
    search_term = form.search_term.data
    if search_term:
        # 关键词搜索：按手机号进行模糊查询
        search_pattern = f'%{search_term}%'
        query = query.filter(Member.phone_number.like(search_pattern))

    # 3. 执行分页查询
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    members = pagination.items
    return render_template('member/list.html',
                           title='会员列表',
                           members=members,
                           form=form,  # 传递搜索表单
                           pagination=pagination)  # 传递分页对象


# --- 会员创建/编辑视图 (C.1 会员信息 CRUD) ---
@member.route('/create', methods=['GET', 'POST'])
@member.route('/edit/<int:member_id>', methods=['GET', 'POST'])
@login_required
def manage_member(member_id=None):
    if member_id:
        member_obj = db.session.get(Member, member_id)
        if member_obj is None:
            flash('会员不存在。', 'danger')
            return redirect(url_for('.list_members'))
        title = '编辑会员信息'
    else:
        member_obj = Member()
        title = '新增会员'

    form = MemberForm(obj=member_obj)

    if form.validate_on_submit():
        try:
            # 填充数据
            form.populate_obj(member_obj)
            db.session.add(member_obj)
            db.session.commit()
            flash(f'会员 "{member_obj.name}" 信息已保存成功！', 'success')
            return redirect(url_for('.list_members'))
        except IntegrityError:
            db.session.rollback()
            flash('保存失败：手机号码可能已被其他会员使用。', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'保存失败: {e}', 'danger')

    return render_template('member/manage.html', title=title, form=form, member=member_obj)


# --- 会员删除视图 (C.1 会员信息 CRUD) ---
@member.route('/delete/<int:member_id>', methods=['POST'])
@login_required
def delete_member(member_id):
    member_obj = db.session.get(Member, member_id)
    if member_obj is None:
        flash('会员不存在。', 'danger')
    else:
        try:
            # 严格模式下应检查是否有历史订单关联（外键约束）
            # 如果 MySQL 启用了 ON DELETE SET NULL，则订单的 member_id 会被设为 NULL
            db.session.delete(member_obj)
            db.session.commit()
            flash(f'会员 "{member_obj.name}" 已成功删除。', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'删除失败，该会员可能有订单关联。请先处理相关订单或在数据库中取消关联。', 'danger')

    return redirect(url_for('.list_members'))

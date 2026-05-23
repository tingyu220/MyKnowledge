# -*- coding: utf-8 -*-
"""
用户认证路由
"""
from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': '请求数据不能为空'}), 400
        
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip() if data.get('email') else None
        
        # 验证必填字段
        if not username:
            return jsonify({'error': '用户名不能为空'}), 400
        if not password:
            return jsonify({'error': '密码不能为空'}), 400
        if len(password) < 6:
            return jsonify({'error': '密码长度至少6位'}), 400
        
        # 验证邮箱格式（如果提供了邮箱）
        if email and '@' not in email:
            return jsonify({'error': '邮箱格式不正确'}), 400
        
        # 检查用户名是否已存在
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return jsonify({'error': '用户名已存在'}), 400
        
        # 检查邮箱是否已存在（只检查非空邮箱）
        if email:
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                return jsonify({'error': '邮箱已被注册'}), 400
        
        # 创建新用户
        user = User(
            username=username,
            password=generate_password_hash(password),
            email=email if email else None  # 确保空字符串转换为None
        )
        
        db.session.add(user)
        db.session.commit()
        
        # 重新加载用户以获取ID
        db.session.refresh(user)
        
        return jsonify({
            'message': '注册成功',
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_detail = traceback.format_exc()
        print(f"注册错误: {error_detail}")  # 在控制台输出详细错误
        
        return jsonify({
            'error': f'注册失败: {str(e)}',
            'detail': error_detail if current_app.debug else str(e)
        }), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    user = User.query.filter_by(username=username).first()
    
    if not user or not check_password_hash(user.password, password):
        return jsonify({'error': '用户名或密码错误'}), 401
    
    # 设置session
    session['user_id'] = user.id
    session['username'] = user.username
    
    return jsonify({
        'message': '登录成功',
        'user': user.to_dict()
    }), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """用户登出"""
    session.clear()
    return jsonify({'message': '登出成功'}), 200

@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    """获取当前用户信息"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    return jsonify({'user': user.to_dict()}), 200


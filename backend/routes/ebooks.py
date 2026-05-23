# -*- coding: utf-8 -*-
"""
电子书管理路由
"""
import re
from flask import Blueprint, request, jsonify, session, send_file
from werkzeug.utils import secure_filename
from models import db, Ebook, Book
from routes.auth import login_required
from config import Config
import os
import shutil
import subprocess
import uuid
import unicodedata
from urllib.parse import quote

ebooks_bp = Blueprint('ebooks', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'epub', 'mobi', 'txt', 'doc', 'docx'}
VIEWABLE_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx'}

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _guess_mimetype(ext: str) -> str:
    ext = (ext or '').lower()
    if ext == 'pdf':
        return 'application/pdf'
    if ext == 'txt':
        return 'text/plain; charset=utf-8'
    if ext in ('doc', 'docx'):
        return 'application/pdf'
    return 'application/octet-stream'


def _set_content_disposition(resp, filename: str, inline: bool):
    """
    设置 Content-Disposition，兼容中文文件名（RFC5987 filename*）。
    避免 Werkzeug 开发服务器对 header 进行 latin-1 编码时报 UnicodeEncodeError。
    """
    name = unicodedata.normalize('NFKC', (filename or '')).strip()
    if not name:
        name = 'download'

    # filename 只放 ASCII 安全兜底，filename* 放 UTF-8
    ascii_fallback = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('._') or 'download'
    quoted = quote(name, safe='')
    disp = 'inline' if inline else 'attachment'
    resp.headers['Content-Disposition'] = f"{disp}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quoted}"
    return resp


def _convert_to_pdf_with_libreoffice(src_path: str) -> str | None:
    """
    将 Office 文档转成 PDF（需要系统安装 LibreOffice，并提供 soffice 命令）。
    输出会缓存到与源文件同目录的 .converted 目录下。
    """
    soffice = shutil.which('soffice') or shutil.which('soffice.exe')
    if not soffice:
        return None
    if not os.path.exists(src_path):
        return None

    base_dir = os.path.dirname(src_path)
    out_dir = os.path.join(base_dir, '.converted')
    os.makedirs(out_dir, exist_ok=True)

    stem = os.path.splitext(os.path.basename(src_path))[0]
    # 为避免文件名包含特殊字符导致转换失败，输出名固定加 hash 后缀
    out_pdf = os.path.join(out_dir, f'{stem}_{uuid.uuid4().hex[:8]}.pdf')
    # LibreOffice 输出名固定为同 stem.pdf，因此我们先在 out_dir 里转换，再找到最新 pdf
    try:
        subprocess.run(
            [
                soffice,
                '--headless',
                '--nologo',
                '--norestore',
                '--convert-to',
                'pdf',
                '--outdir',
                out_dir,
                src_path,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
        )
        candidate = os.path.join(out_dir, f'{stem}.pdf')
        if os.path.exists(candidate):
            # 重命名为带随机后缀的文件，避免并发覆盖
            try:
                os.replace(candidate, out_pdf)
            except Exception:
                out_pdf = candidate
            return out_pdf
        # 兜底：找 out_dir 中最新的 pdf
        pdfs = [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.lower().endswith('.pdf')]
        if not pdfs:
            return None
        pdfs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return pdfs[0]
    except Exception:
        return None

@ebooks_bp.route('', methods=['GET'])
@login_required
def get_ebooks():
    """获取电子书列表"""
    user_id = session.get('user_id')
    book_id = request.args.get('book_id', type=int)
    
    query = Ebook.query.filter_by(user_id=user_id)
    
    if book_id:
        query = query.filter_by(book_id=book_id)
    
    ebooks = query.order_by(Ebook.uploaded_at.desc()).all()
    
    return jsonify({
        'ebooks': [ebook.to_dict() for ebook in ebooks]
    }), 200

@ebooks_bp.route('/upload', methods=['POST'])
@login_required
def upload_ebook():
    """上传电子书"""
    user_id = session.get('user_id')
    
    if 'file' not in request.files:
        return jsonify({'error': '没有选择文件'}), 400
    
    file = request.files['file']
    book_id = request.form.get('book_id', type=int)
    
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    original_filename = file.filename or ''
    if not allowed_file(original_filename):
        return jsonify({'error': '不支持的文件类型'}), 400
    
    # 确保上传目录存在
    upload_dir = Config.UPLOAD_FOLDER
    user_dir = os.path.join(upload_dir, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    
    def _sanitize_filename_keep_unicode(name: str) -> str:
        """
        尽量保留原始文件名（含中文），仅替换 Windows 不允许的字符，避免路径穿越与结尾空格/点。
        """
        n = unicodedata.normalize('NFKC', (name or '')).strip()
        # 防止路径穿越：只保留 basename
        n = os.path.basename(n)
        # Windows 不允许字符：<>:"/\|?* 以及控制字符
        invalid = '<>:"/\\\\|?*'
        n = ''.join(('_' if (ch in invalid or ord(ch) < 32) else ch) for ch in n)
        # Windows 末尾不允许空格和点
        n = n.rstrip(' .')
        return n

    # 展示文件名：使用用户上传时的原始文件名（用于列表展示与下载）
    file_ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    if not file_ext:
        return jsonify({'error': '文件缺少扩展名（如 .pdf/.epub/.mobi/.txt）'}), 400

    disk_filename = _sanitize_filename_keep_unicode(original_filename)
    if not disk_filename:
        disk_filename = f"ebook.{file_ext}"
    # 确保扩展名匹配（避免被用户上传的文件名里扩展名被清理掉）
    if '.' not in disk_filename:
        disk_filename = f"{disk_filename}.{file_ext}"
    file_path = os.path.join(user_dir, disk_filename)
    # 同名冲突：追加短 uuid 后缀，避免覆盖
    if os.path.exists(file_path):
        stem, ext = os.path.splitext(disk_filename)
        suffix = uuid.uuid4().hex[:8]
        disk_filename = f"{stem}_{suffix}{ext or ('.' + file_ext)}"
        file_path = os.path.join(user_dir, disk_filename)
    
    try:
        # 保存文件
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        
        # 创建电子书记录
        ebook = Ebook(
            user_id=user_id,
            book_id=book_id if book_id else None,
            file_path=file_path,
            file_name=original_filename,
            file_size=file_size,
            file_type=file_ext
        )
        
        db.session.add(ebook)
        db.session.commit()
        
        return jsonify({
            'message': '上传成功',
            'ebook': ebook.to_dict()
        }), 201
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        db.session.rollback()
        return jsonify({'error': f'上传失败: {str(e)}'}), 500

@ebooks_bp.route('/<int:ebook_id>', methods=['GET'])
@login_required
def download_ebook(ebook_id):
    """下载电子书"""
    user_id = session.get('user_id')
    ebook = Ebook.query.filter_by(id=ebook_id, user_id=user_id).first()
    
    if not ebook:
        return jsonify({'error': '电子书不存在'}), 404
    
    if not os.path.exists(ebook.file_path):
        return jsonify({'error': '文件不存在'}), 404
    
    resp = send_file(
        ebook.file_path,
        as_attachment=True,
        download_name=ebook.file_name
    )
    return _set_content_disposition(resp, ebook.file_name, inline=False)


@ebooks_bp.route('/<int:ebook_id>/view', methods=['GET'])
@login_required
def view_ebook(ebook_id):
    """
    在线查看电子书：
    - PDF: 直接 inline 返回
    - TXT: text/plain inline 返回
    - DOC/DOCX: 通过 LibreOffice 转成 PDF 后 inline 返回
    """
    user_id = session.get('user_id')
    ebook = Ebook.query.filter_by(id=ebook_id, user_id=user_id).first()
    if not ebook:
        return jsonify({'error': '电子书不存在'}), 404
    if not os.path.exists(ebook.file_path):
        return jsonify({'error': '文件不存在'}), 404

    ext = (ebook.file_type or '').lower()
    if not ext and '.' in (ebook.file_path or ''):
        ext = ebook.file_path.rsplit('.', 1)[1].lower()

    if ext not in VIEWABLE_EXTENSIONS:
        return jsonify({'error': '该格式暂不支持在线预览，请下载后查看'}), 415

    # PDF / TXT 直接返回
    if ext in ('pdf', 'txt'):
        resp = send_file(
            ebook.file_path,
            as_attachment=False,
            mimetype=_guess_mimetype(ext),
            download_name=ebook.file_name,
            conditional=True,
        )
        return _set_content_disposition(resp, ebook.file_name, inline=True)

    # DOC/DOCX 转 PDF
    pdf_path = _convert_to_pdf_with_libreoffice(ebook.file_path)
    if not pdf_path:
        return jsonify({'error': '预览 Word 需要安装 LibreOffice（soffice 命令）。请先安装后重试，或直接下载查看。'}), 501

    resp = send_file(
        pdf_path,
        as_attachment=False,
        mimetype='application/pdf',
        download_name=os.path.splitext(ebook.file_name)[0] + '.pdf' if ebook.file_name else 'preview.pdf',
        conditional=True,
    )
    view_name = (os.path.splitext(ebook.file_name)[0] + '.pdf') if ebook.file_name else 'preview.pdf'
    return _set_content_disposition(resp, view_name, inline=True)

@ebooks_bp.route('/<int:ebook_id>', methods=['DELETE'])
@login_required
def delete_ebook(ebook_id):
    """删除电子书"""
    user_id = session.get('user_id')
    ebook = Ebook.query.filter_by(id=ebook_id, user_id=user_id).first()
    
    if not ebook:
        return jsonify({'error': '电子书不存在'}), 404
    
    try:
        # 删除文件
        if os.path.exists(ebook.file_path):
            os.remove(ebook.file_path)
        
        # 删除记录
        db.session.delete(ebook)
        db.session.commit()
        
        return jsonify({'message': '删除成功'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'删除失败: {str(e)}'}), 500

@ebooks_bp.route('/<int:ebook_id>/link', methods=['POST'])
@login_required
def link_ebook_to_book(ebook_id):
    """关联电子书到图书。POST body: { "book_id": 123 } 或 { "book_id": null } 解除关联。"""
    user_id = session.get('user_id')
    data = (request.get_json() or {})
    book_id = data.get('book_id') if 'book_id' in data else None

    ebook = Ebook.query.filter_by(id=ebook_id, user_id=user_id).first()
    if not ebook:
        return jsonify({'error': '电子书不存在'}), 404
    
    if book_id:
        book = Book.query.filter_by(id=book_id, user_id=user_id).first()
        if not book:
            return jsonify({'error': '图书不存在'}), 404
    
    try:
        ebook.book_id = book_id
        db.session.commit()
        
        return jsonify({
            'message': '关联成功',
            'ebook': ebook.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'关联失败: {str(e)}'}), 500


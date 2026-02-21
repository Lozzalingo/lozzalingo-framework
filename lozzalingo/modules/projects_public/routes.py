"""
Projects Public Routes
======================

Public-facing project portfolio pages and API.
"""

from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, request
import re

projects_public_bp = Blueprint('projects', __name__, url_prefix='/projects', template_folder='templates')


def format_content(content):
    """Format content by converting line breaks to HTML and handling basic formatting"""
    if not content:
        return ""

    content = re.sub(r'\n\s*\n', '</p><p>', content)
    content = re.sub(r'\n', '<br>', content)
    content = f'<p>{content}</p>'
    content = re.sub(r'<p>\s*</p>', '', content)
    content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
    content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
    content = re.sub(r'`(.*?)`', r'<code>\1</code>', content)
    content = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', content)

    return content


@projects_public_bp.app_template_filter('format_project_content')
def format_content_filter(content):
    return format_content(content)


# ===== Routes =====

@projects_public_bp.route('/')
def projects_list():
    """Public projects listing - shows all published projects (active + inactive)."""
    from lozzalingo.modules.projects.routes import get_all_projects_db, init_projects_db, get_all_tech_categories
    init_projects_db()
    projects = get_all_projects_db(status='published')
    tech_categories = get_all_tech_categories()
    return render_template('projects_public/projects.html', projects=projects, tech_categories=tech_categories)


@projects_public_bp.route('/<slug>')
def project_detail(slug):
    """Individual project page."""
    from lozzalingo.modules.projects.routes import get_project_by_slug_db, get_all_projects_db, init_projects_db, get_all_tech_categories
    init_projects_db()
    project = get_project_by_slug_db(slug)

    if not project or project.get('status') != 'published':
        flash('Project not found', 'error')
        return redirect(url_for('projects.projects_list'))

    all_projects = get_all_projects_db(status='published')
    related_projects = [p for p in all_projects if p['slug'] != slug][:3]
    tech_categories = get_all_tech_categories()

    return render_template('projects_public/project_detail.html',
                         project=project, related_projects=related_projects,
                         tech_categories=tech_categories)


# ===== API Routes =====

@projects_public_bp.route('/api/projects', methods=['GET'])
def get_projects():
    """Get published projects API - public endpoint."""
    from lozzalingo.modules.projects.routes import get_all_projects_db, init_projects_db
    init_projects_db()
    projects = get_all_projects_db(status='published')
    return jsonify(projects)

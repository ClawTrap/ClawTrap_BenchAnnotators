from flask import Blueprint, jsonify, render_template, request, session

from . import contract_review

blueprint = Blueprint('review_workspace', __name__)


def workspace_page(view='review'):
    return render_template('workspace.html', view=view, user=session.get('username', ''))


@blueprint.before_request
def human_reviewer_only():
    if session.get('role') not in ('admin', 'annotator'):
        return jsonify(error='请先登录审核账号'), 401


@blueprint.get('/api/review/catalog')
def catalog():
    return jsonify(error='旧版审核已下线，请使用新题审核'), 410


@blueprint.get('/api/contracts/catalog')
def contract_catalog():
    return jsonify(contract_review.catalog())


@blueprint.post('/api/contracts/cases/<case_id>')
def save_contract_review(case_id):
    try:
        review = contract_review.save_review(case_id, request.get_json(silent=True), session['username'])
    except KeyError:
        return jsonify(error='题目不在合同审核清单中'), 404
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(id=case_id, review=review)


@blueprint.patch('/api/contracts/cases/<case_id>/content')
def save_contract_content(case_id):
    try:
        edit = contract_review.save_content_edit(case_id, request.get_json(silent=True), session['username'])
    except KeyError:
        return jsonify(error='题目不在新题审核清单中'), 404
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(id=case_id, edit=edit)


@blueprint.get('/api/contracts/confirmed-export')
def export_confirmed_contracts():
    return jsonify(contract_review.confirmed_export())


@blueprint.get('/api/contracts/selected-export')
def export_selected_contracts():
    return jsonify(contract_review.selected_export())


@blueprint.get('/api/review/cases/<case_id>')
def detail(case_id):
    return jsonify(error='旧版审核已下线，请使用新题审核'), 410


@blueprint.post('/api/review/cases/<case_id>')
def save(case_id):
    return jsonify(error='旧版审核已下线，请使用新题审核'), 410

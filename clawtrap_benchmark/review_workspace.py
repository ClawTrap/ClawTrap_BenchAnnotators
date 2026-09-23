from flask import Blueprint, jsonify, render_template, request, session

from . import contract_review, review_design, storage

blueprint = Blueprint('review_workspace', __name__)


def workspace_page(view='review'):
    return render_template('workspace.html', view=view, user=session.get('username', ''))


@blueprint.before_request
def human_reviewer_only():
    if session.get('role') not in ('admin', 'annotator'):
        return jsonify(error='请先登录审核账号'), 401


@blueprint.get('/api/review/catalog')
def catalog():
    return jsonify(review_design.catalog())


@blueprint.get('/api/contracts/catalog')
def contract_catalog():
    return jsonify(contract_review.catalog())


@blueprint.post('/api/contracts/cases/<case_id>')
def save_contract_review(case_id):
    try:
        review = contract_review.save_review(case_id, request.get_json(silent=True), session['username'])
    except KeyError:
        return jsonify(error='题目不在80题合同审核清单中'), 404
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(id=case_id, review=review)


def get_case(case_id):
    item = next((r for r in review_design.base_catalog() if r['id'] == case_id), None)
    return storage.find_case(case_id, dataset=item['dataset']) if item else None


@blueprint.get('/api/review/cases/<case_id>')
def detail(case_id):
    case = get_case(case_id)
    if not case:
        return jsonify(error='题目不存在'), 404
    return jsonify(case=case)


@blueprint.post('/api/review/cases/<case_id>')
def save(case_id):
    raw = request.get_json(silent=True)
    if not isinstance(raw, dict):
        return jsonify(error='请求格式不正确'), 400
    case = get_case(case_id)
    if not case:
        return jsonify(error='题目不存在'), 404
    try:
        assessment = review_design.validate_assessment(raw.get('assessment'))
        decision = raw.get('decision')
        if decision is not None and decision not in storage.EXPERT_DECISIONS:
            raise ValueError('审核结论不正确')
        saved = storage.set_expert_decision(case_id, decision, decided_by=session['username'],
                    dataset=case['dataset'], comment=assessment['notes'], assessment=assessment)
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 503
    return jsonify(id=saved['id'], decision=saved.get('expert_decision', ''),
                   selected=saved.get('benchmark_selected', False),
                   assessment=saved.get('design_review', {}), comment=saved.get('expert_decision_comment', ''))

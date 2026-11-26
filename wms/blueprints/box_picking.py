import re
from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..models import Box, BoxPickingTask, BoxPickingTaskLine, MVB_ROLES, User, Warehouse
from ..utils.numbering import next_number


bp = Blueprint("box_picking", __name__)

STATUS_LABELS = {
    "new": "Новое",
    "in_progress": "В работе",
    "completed": "Выполнено",
}


def _active_users():
    return (
        User.query.filter(
            User.is_active_user.is_(True),
            User.role.notin_(list(MVB_ROLES) + ["production"]),
        )
        .order_by(User.full_name, User.username)
        .all()
    )


def _codes(raw):
    return [value for value in re.split(r"[\s,;]+", (raw or "").strip()) if value]


def _add_codes(task, raw):
    added = 0
    errors = []
    existing_ids = {line.box_id for line in task.lines.all()}
    for code in _codes(raw):
        # Цифровая часть номера может совпадать у коробов разных кабинетов.
        # Ищем сразу внутри склада задания, иначе первым мог найтись короб
        # другого склада и корректный короб ошибочно отклонялся.
        box = Box.find_by_scanned_code(code, warehouse_id=task.warehouse_id)
        if box is None:
            errors.append(f"Короб {code} не найден")
            continue
        if box.id in existing_ids:
            continue
        db.session.add(BoxPickingTaskLine(task=task, box=box))
        existing_ids.add(box.id)
        added += 1
    return added, errors


@bp.route("/")
def list_tasks():
    status = request.args.get("status", "open")
    query = BoxPickingTask.query
    if status == "open":
        query = query.filter(BoxPickingTask.status != "completed")
    elif status in STATUS_LABELS:
        query = query.filter_by(status=status)
    tasks = query.order_by(BoxPickingTask.created_at.desc()).all()
    return render_template(
        "box_picking/list.html",
        tasks=tasks,
        status=status,
        status_labels=STATUS_LABELS,
    )


@bp.route("/create", methods=["GET", "POST"])
def create_task():
    warehouses = Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name).all()
    users = _active_users()
    if request.method == "GET":
        return render_template("box_picking/create.html", warehouses=warehouses, users=users)

    warehouse_id = request.form.get("warehouse_id", type=int)
    warehouse = Warehouse.query.filter_by(id=warehouse_id, is_active=True).first()
    if warehouse is None:
        flash("Выберите склад", "danger")
        return render_template("box_picking/create.html", warehouses=warehouses, users=users)

    assigned_to_id = request.form.get("assigned_to_id", type=int)
    assigned_to = User.query.filter_by(id=assigned_to_id, is_active_user=True).first() if assigned_to_id else None
    task = BoxPickingTask(
        number=next_number("box_picking"),
        title=request.form.get("title", "").strip() or None,
        warehouse=warehouse,
        created_by=current_user,
        assigned_to=assigned_to,
    )
    db.session.add(task)
    db.session.flush()
    added, errors = _add_codes(task, request.form.get("box_codes", ""))
    db.session.commit()
    flash(f"Задание {task.number} создано, добавлено коробов: {added}", "success")
    for error in errors[:10]:
        flash(error, "warning")
    if len(errors) > 10:
        flash(f"И ещё ошибок: {len(errors) - 10}", "warning")
    return redirect(url_for("box_picking.detail", task_id=task.id))


@bp.route("/add-selected-boxes", methods=["POST"])
def add_selected_boxes():
    """Добавляет отмеченные в общем списке короба в открытое задание.

    Здесь передаются первичные ID коробов, поэтому массовое добавление не
    зависит от неоднозначных цифровых штрихкодов разных кабинетов.
    """
    task_id = request.form.get("task_id", type=int)
    task = db.session.get(BoxPickingTask, task_id) if task_id else None
    if task is None:
        flash("Выберите задание на подбор", "danger")
        return redirect(url_for("boxes.list_boxes"))
    if task.status == "completed":
        flash("Выполненное задание сначала нужно открыть заново", "warning")
        return redirect(url_for("box_picking.detail", task_id=task.id))

    box_ids = []
    for raw_id in request.form.getlist("ids"):
        try:
            box_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if box_id not in box_ids:
            box_ids.append(box_id)

    if not box_ids:
        flash("Отметьте хотя бы один короб", "warning")
        return redirect(url_for("boxes.list_boxes"))

    boxes_by_id = {
        box.id: box for box in Box.query.filter(Box.id.in_(box_ids)).all()
    }
    existing_ids = {line.box_id for line in task.lines.all()}
    added = 0
    wrong_warehouse = []
    for box_id in box_ids:
        box = boxes_by_id.get(box_id)
        if box is None or box.id in existing_ids:
            continue
        if box.warehouse_id != task.warehouse_id:
            wrong_warehouse.append(box.box_number)
            continue
        db.session.add(BoxPickingTaskLine(task=task, box=box))
        existing_ids.add(box.id)
        added += 1

    db.session.commit()
    if added:
        flash(f"Добавлено коробов: {added}", "success")
    elif not wrong_warehouse:
        flash("Выбранные короба уже находятся в этом задании", "info")
    if wrong_warehouse:
        preview = ", ".join(wrong_warehouse[:10])
        suffix = f" и ещё {len(wrong_warehouse) - 10}" if len(wrong_warehouse) > 10 else ""
        flash(
            f"Не добавлены короба с другого склада: {preview}{suffix}",
            "warning",
        )
    return redirect(url_for("box_picking.detail", task_id=task.id))


@bp.route("/<int:task_id>")
def detail(task_id):
    task = BoxPickingTask.query.get_or_404(task_id)
    lines = task.lines.all()
    lines.sort(
        key=lambda line: (
            line.picked_at is not None,
            line.box.location_label() is None,
            line.box.location_label() or "",
            line.box.box_number,
        )
    )
    return render_template(
        "box_picking/detail.html",
        task=task,
        lines=lines,
        status_labels=STATUS_LABELS,
    )


@bp.route("/<int:task_id>/boxes", methods=["POST"])
def add_boxes(task_id):
    task = BoxPickingTask.query.get_or_404(task_id)
    if task.status == "completed":
        flash("Выполненное задание сначала нужно открыть заново", "warning")
        return redirect(url_for("box_picking.detail", task_id=task.id))
    added, errors = _add_codes(task, request.form.get("box_codes", ""))
    db.session.commit()
    if added:
        flash(f"Добавлено коробов: {added}", "success")
    for error in errors[:10]:
        flash(error, "warning")
    return redirect(url_for("box_picking.detail", task_id=task.id))


@bp.route("/<int:task_id>/scan", methods=["POST"])
def scan(task_id):
    task = BoxPickingTask.query.get_or_404(task_id)
    if task.status == "completed":
        flash("Задание уже выполнено", "warning")
        return redirect(url_for("box_picking.detail", task_id=task.id))

    code = request.form.get("box_code", "").strip()
    # Как и при наполнении задания, цифровой штрихкод разрешаем только на
    # складе этого задания: одинаковая цифровая часть встречается у разных
    # кабинетов и не должна уводить скан в чужой короб.
    box = Box.find_by_scanned_code(code, warehouse_id=task.warehouse_id)
    line = (
        BoxPickingTaskLine.query.filter_by(task_id=task.id, box_id=box.id).first()
        if box
        else None
    )
    if box is None:
        flash(f"Короб {code or '—'} не найден", "danger")
    elif line is None:
        flash(f"Короб {box.box_number} не входит в это задание", "danger")
    elif line.picked_at is not None:
        flash(f"Короб {box.box_number} уже подобран", "warning")
    else:
        now = datetime.utcnow()
        line.picked_at = now
        line.picked_by = current_user
        box.mark_scanned(current_user)
        if task.status == "new":
            task.status = "in_progress"
            task.started_at = now
        db.session.flush()
        remaining = task.lines.filter(BoxPickingTaskLine.picked_at.is_(None)).count()
        if remaining == 0:
            task.status = "completed"
            task.completed_at = now
            flash(f"Короб {box.box_number} подобран. Задание выполнено", "success")
        else:
            flash(f"Короб {box.box_number} подобран. Осталось: {remaining}", "success")
        db.session.commit()
    return redirect(url_for("box_picking.detail", task_id=task.id))


@bp.route("/<int:task_id>/lines/<int:line_id>/remove", methods=["POST"])
def remove_line(task_id, line_id):
    task = BoxPickingTask.query.get_or_404(task_id)
    line = BoxPickingTaskLine.query.filter_by(id=line_id, task_id=task.id).first_or_404()
    if not current_user.is_admin and task.created_by_id != current_user.id:
        flash("Удалять короба может автор задания или администратор", "danger")
        return redirect(url_for("box_picking.detail", task_id=task.id))
    db.session.delete(line)
    db.session.commit()
    flash("Короб удален из задания", "success")
    return redirect(url_for("box_picking.detail", task_id=task.id))


@bp.route("/<int:task_id>/reopen", methods=["POST"])
def reopen(task_id):
    task = BoxPickingTask.query.get_or_404(task_id)
    if not current_user.is_admin:
        flash("Открыть задание заново может только администратор", "danger")
        return redirect(url_for("box_picking.detail", task_id=task.id))
    task.status = "in_progress" if task.picked_count() else "new"
    task.completed_at = None
    db.session.commit()
    flash("Задание открыто заново", "success")
    return redirect(url_for("box_picking.detail", task_id=task.id))


@bp.route("/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    task = BoxPickingTask.query.get_or_404(task_id)
    if not current_user.is_admin:
        flash("Удалять задания может только администратор", "danger")
        return redirect(url_for("box_picking.detail", task_id=task.id))
    db.session.delete(task)
    db.session.commit()
    flash("Задание удалено", "success")
    return redirect(url_for("box_picking.list_tasks"))

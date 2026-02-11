# inventory/routes/partners.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func

from inventory.extensions import db
from inventory.models import Partner, Transaction
from inventory.utils.translations import _
from inventory.utils.decorators import roles_required

bp = Blueprint("partners", __name__)


def _get_owner_id():
    # тук решавам към коя фирма (owner) е вързан user-а
    # admin owner е самия owner
    # другите са вързани към owner през created_by_id
    # developer е специален случай и не го филтрирам по owner
    # но пак внимавам да не създава данни без owner по грешка
    if current_user.role == "Developer":
        return None
    if current_user.role == "Admin / Owner":
        return current_user.id
    return current_user.created_by_id


@bp.route("/partners", methods=["GET", "POST"])
@login_required
@roles_required("Admin / Owner", "Warehouse Manager", "Sales Agent")
def partners():
    owner_id = _get_owner_id()

    # -------------------- СЪЗДАВАНЕ НА ПАРТНЬОР -------------------- #
    if request.method == "POST":
        # sales agent не трябва да пипа master data
        if current_user.role == "Sales Agent":
            flash(_("Sales Agents cannot create partners."), "danger")
            return redirect(url_for("partners.partners"))

        # ако owner_id е None значи developer е влязъл без owner контекст
        # и не искам да правя партньори без owner
        if owner_id is None:
            flash(_("Developer must create partners from an owner context."), "warning")
            return redirect(url_for("partners.partners"))

        name = (request.form.get("name") or "").strip()
        ptype = (request.form.get("type") or "").strip()

        # базова валидация
        if not name or not ptype:
            flash(_("Please provide partner name and type."), "danger")
            return redirect(url_for("partners.partners"))

        # позволявам само тези типове
        if ptype not in ["Customer", "Supplier", "Both"]:
            flash(_("Invalid partner type."), "danger")
            return redirect(url_for("partners.partners"))

        # пазя от дубликати в рамките на фирмата
        # тук гледам име (case-insensitive) + тип
        exists = Partner.query.filter(
            Partner.owner_id == owner_id,
            func.lower(Partner.name) == name.lower(),
            Partner.type == ptype,
        ).first()

        if exists:
            flash(_("This partner already exists."), "warning")
            return redirect(url_for("partners.partners"))

        new_p = Partner(name=name, type=ptype, owner_id=owner_id)
        db.session.add(new_p)
        db.session.commit()

        flash(_('%(ptype)s "%(name)s" added.') % {"ptype": ptype, "name": name}, "success")
        return redirect(url_for("partners.partners"))

    # -------------------- СПИСЪК + ФИЛТРИ -------------------- #
    q = (request.args.get("q") or "").strip()
    f_type = (request.args.get("type") or "").strip()

    query = Partner.query

    # ако не е developer филтрирам по фирма
    if owner_id is not None:
        query = query.filter(Partner.owner_id == owner_id)

    # търсене по име
    if q:
        query = query.filter(Partner.name.ilike(f"%{q}%"))

    # филтър по тип
    if f_type in ["Customer", "Supplier", "Both"]:
        query = query.filter(Partner.type == f_type)

    partners_list = query.order_by(Partner.name.asc()).all()

    return render_template(
        "partners.html",
        partners=partners_list,
        q=q,
        f_type=f_type,
    )


@bp.route("/partners/edit/<int:id>", methods=["POST"])
@login_required
@roles_required("Admin / Owner", "Warehouse Manager")
def edit_partner(id):
    owner_id = _get_owner_id()

    # намирам партньора и пак пазя org scoping
    # warehouse manager може да редактира ако така си решил с roles_required
    q = Partner.query.filter(Partner.id == id)
    if owner_id is not None:
        q = q.filter(Partner.owner_id == owner_id)

    partner = q.first_or_404()

    name = (request.form.get("name") or "").strip()
    ptype = (request.form.get("type") or "").strip()

    # име е задължително
    if not name:
        flash(_("Name is required."), "danger")
        return redirect(url_for("partners.partners"))

    # пазя да не вкараш странен тип
    if ptype not in ["Customer", "Supplier", "Both"]:
        flash(_("Invalid partner type."), "danger")
        return redirect(url_for("partners.partners"))

    # след edit пак пазя от дубликати
    # тук добавям Partner.id != partner.id за да не се засечеш сам
    if owner_id is not None:
        dup = Partner.query.filter(
            Partner.owner_id == owner_id,
            func.lower(Partner.name) == name.lower(),
            Partner.type == ptype,
            Partner.id != partner.id,
        ).first()
        if dup:
            flash(_("A partner with the same name and type already exists."), "warning")
            return redirect(url_for("partners.partners"))

    partner.name = name
    partner.type = ptype

    db.session.commit()
    flash(_("Partner updated."), "success")
    return redirect(url_for("partners.partners"))


@bp.route("/partners/delete/<int:id>", methods=["POST"])
@login_required
@roles_required("Admin / Owner")
def delete_partner(id):
    owner_id = _get_owner_id()

    # намирам партньора и пак пазя org scoping
    q = Partner.query.filter(Partner.id == id)
    if owner_id is not None:
        q = q.filter(Partner.owner_id == owner_id)

    partner = q.first_or_404()

    # ако има транзакции с този партньор не го трия
    # историята е важна
    used = Transaction.query.filter_by(partner_id=partner.id).first() is not None
    if used:
        flash(_("Cannot delete a partner that is used in transactions."), "warning")
        return redirect(url_for("partners.partners"))

    db.session.delete(partner)
    db.session.commit()
    flash(_("Partner deleted."), "success")
    return redirect(url_for("partners.partners"))

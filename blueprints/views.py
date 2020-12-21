from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.html import format_html
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from allianceauth.authentication.decorators import permissions_required
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from esi.decorators import token_required

from . import __title__, tasks
from .app_settings import (
    BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED,
    BLUEPRINTS_DEFAULT_PAGE_LENGTH,
    BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
    BLUEPRINTS_PAGING_ENABLED,
)
from .models import Blueprint, Owner, Request
from .utils import messages_plus, notify_admins


@login_required
@permissions_required("blueprints.basic_access")
def index(request):

    context = {
        "page_title": gettext_lazy(__title__),
        "data_tables_page_length": BLUEPRINTS_DEFAULT_PAGE_LENGTH,
        "data_tables_paging": BLUEPRINTS_PAGING_ENABLED,
    }
    return render(request, "blueprints/index.html", context)


@login_required
@permissions_required("blueprints.add_corporate_blueprint_owner")
@token_required(
    scopes=[
        "esi-universe.read_structures.v1",
        "esi-corporations.read_blueprints.v1",
        "esi-assets.read_corporation_assets.v1",
    ]
)
def add_corporate_blueprint_owner(request, token):
    token_char = EveCharacter.objects.get(character_id=token.character_id)

    success = True
    try:
        owned_char = CharacterOwnership.objects.get(
            user=request.user, character=token_char
        )
    except CharacterOwnership.DoesNotExist:
        messages_plus.error(
            request,
            format_html(
                gettext_lazy(
                    "You can only use your main or alt characters "
                    "to add corporations. "
                    "However, character %s is neither. "
                )
                % format_html("<strong>{}</strong>", token_char.character_name)
            ),
        )
        success = False
        owned_char = None

    if success:
        try:
            corporation = EveCorporationInfo.objects.get(
                corporation_id=token_char.corporation_id
            )
        except EveCorporationInfo.DoesNotExist:
            corporation = EveCorporationInfo.objects.create_corporation(
                token_char.corporation_id
            )

        with transaction.atomic():
            owner, _ = Owner.objects.update_or_create(
                corporation=corporation, defaults={"character": owned_char}
            )

            owner.save()

        tasks.update_blueprints_for_owner.delay(owner_pk=owner.pk)
        tasks.update_locations_for_owner.delay(owner_pk=owner.pk)
        messages_plus.info(
            request,
            format_html(
                gettext_lazy(
                    "%(corporation)s has been added with %(character)s "
                    "as sync character. We have started fetching blueprints "
                    "for this corporation. You will receive a report once "
                    "the process is finished."
                )
                % {
                    "corporation": format_html("<strong>{}</strong>", owner),
                    "character": format_html(
                        "<strong>{}</strong>", owner.character.character.character_name
                    ),
                }
            ),
        )
        if BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED:
            notify_admins(
                message=gettext_lazy(
                    "%(corporation)s was added as new " "blueprint owner by %(user)s."
                )
                % {
                    "corporation": owner.corporation.corporation_name,
                    "user": request.user.username,
                },
                title="{}: blueprint owner added: {}".format(
                    __title__, owner.corporation.corporation_name
                ),
            )
    return redirect("blueprints:index")


@login_required
@permissions_required("blueprints.add_personal_blueprint_owner")
@token_required(
    scopes=[
        "esi-universe.read_structures.v1",
        "esi-characters.read_blueprints.v1",
        "esi-assets.read_assets.v1",
    ]
)
def add_personal_blueprint_owner(request, token):
    token_char = EveCharacter.objects.get(character_id=token.character_id)

    success = True
    try:
        owned_char = CharacterOwnership.objects.get(
            user=request.user, character=token_char
        )
    except CharacterOwnership.DoesNotExist:
        messages_plus.error(
            request,
            format_html(
                gettext_lazy(
                    "You can only use your main or alt characters "
                    "to add corporations. "
                    "However, character %s is neither. "
                )
                % format_html("<strong>{}</strong>", token_char.character_name)
            ),
        )
        success = False
        owned_char = None

    if success:

        with transaction.atomic():
            owner, _ = Owner.objects.update_or_create(
                corporation=None, character=owned_char
            )

            owner.save()

        tasks.update_blueprints_for_owner.delay(owner_pk=owner.pk)
        tasks.update_locations_for_owner.delay(owner_pk=owner.pk)
        messages_plus.info(
            request,
            format_html(
                gettext_lazy(
                    "%(character)s has been added. We have started fetching blueprints "
                    "for this character. You will receive a report once "
                    "the process is finished."
                )
                % {
                    "character": format_html(
                        "<strong>{}</strong>", owner.character.character.character_name
                    ),
                }
            ),
        )
        if BLUEPRINTS_ADMIN_NOTIFICATIONS_ENABLED:
            notify_admins(
                message=gettext_lazy(
                    "%(character)s was added as a new personal blueprint owner."
                )
                % {
                    "character": owner.character.character.character_name,
                },
                title="{}: blueprint owner added: {}".format(
                    __title__, owner.character.character.character_name
                ),
            )
    return redirect("blueprints:index")


def convert_blueprint(blueprint) -> dict:
    icon = format_html(
        '<img src="{}" width="{}" height="{}">',
        blueprint.eve_type.icon_url(size=64, is_blueprint=True),
        BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
        BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
    )
    runs = "" if not blueprint.runs or blueprint.runs < 1 else blueprint.runs
    original = "✓" if not blueprint.runs or blueprint.runs == -1 else ""
    filter_is_original = (
        gettext_lazy("Yes")
        if not blueprint.runs or blueprint.runs == -1
        else gettext_lazy("No")
    )
    if blueprint.owner.corporation:
        owner_type = "corporation"
    else:
        owner_type = "character"
    return {
        "icn": icon,
        "qty": blueprint.quantity,
        "pk": blueprint.pk,
        "nme": blueprint.eve_type.name,
        "loc": blueprint.location.name_plus,
        "me": blueprint.material_efficiency,
        "te": blueprint.time_efficiency,
        "og": original,
        "iog": filter_is_original,
        "rns": runs,
        "on": blueprint.owner.name,
        "ot": owner_type,
    }


@login_required
@permissions_required("blueprints.basic_access")
def list_blueprints(request):

    corporation_ids = set(
        request.user.character_ownerships.select_related("character").values_list(
            "character__corporation_id", flat=True
        )
    )
    corporations = list(
        EveCorporationInfo.objects.filter(corporation_id__in=corporation_ids)
    )
    if request.user.has_perm("blueprints.view_alliance_blueprints"):
        alliances = {
            corporation.alliance for corporation in corporations if corporation.alliance
        }
        for alliance in alliances:
            corporations += alliance.evecorporationinfo_set.all()

        corporations = list(set(corporations))

    personal_owner_ids = list()
    for owner in Owner.objects.filter(corporation=None):
        if owner.character.character.corporation_id in corporation_ids:
            personal_owner_ids.append(owner.pk)

    blueprints_query = Blueprint.objects.filter(
        Q(owner__corporation__in=corporations) | Q(owner__pk__in=personal_owner_ids)
    ).select_related(
        "eve_type",
        "location",
        "owner",
        "owner__corporation",
        "owner__character",
        "location",
        "location__eve_solar_system",
        "location__eve_type",
    )
    blueprint_rows = [convert_blueprint(blueprint) for blueprint in blueprints_query]

    return JsonResponse(blueprint_rows, safe=False)


@login_required
@permissions_required("blueprints.request_blueprints")
def create_request_modal(request):
    blueprint = Blueprint.objects.get(pk=request.GET.get("blueprint_id"))
    context = {"blueprint": convert_blueprint(blueprint)}
    return render(request, "blueprints/modals/create_request_content.html", context)


@login_required
@permissions_required(("blueprints.request_blueprints", "blueprints.manage_requests"))
def view_request_modal(request):
    user_request = Request.objects.get(pk=request.GET.get("request_id"))
    context = {"request": convert_request(user_request)}
    return render(request, "blueprints/modals/view_request_content.html", context)


@login_required
@permissions_required("blueprints.request_blueprints")
def create_request(request):
    if request.method == "POST":
        requested = Blueprint.objects.get(pk=request.POST.get("pk"))
        runs = request.POST.get("rns")
        if runs == "":
            runs = None
        user = request.user
        Request.objects.create(
            blueprint=requested,
            requesting_user=user,
            status=Request.STATUS_OPEN,
            runs=runs,
        )
        messages_plus.info(
            request,
            format_html(
                gettext_lazy("A copy of %(blueprint)s has been requested.")
                % {"blueprint": requested.eve_type.name}
            ),
        )
    return redirect("blueprints:index")


def convert_request(request: Request) -> dict:
    icon = format_html(
        '<img src="{}" width="{}" height="{}">',
        request.blueprint.eve_type.icon_url(size=64, is_blueprint=True),
        BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
        BLUEPRINTS_LIST_ICON_OUTPUT_SIZE,
    )

    if request.blueprint.owner.corporation:
        owner_type = "corporation"
    else:
        owner_type = "character"
    return {
        "request_id": request.pk,
        "type_icon": icon,
        "type_name": request.blueprint.eve_type.name,
        "owner_name": request.blueprint.owner.name,
        "owner_type": owner_type,
        "requestor": request.requesting_user.profile.main_character.character_name,
        "location": request.blueprint.location.name_plus,
        "material_efficiency": request.blueprint.material_efficiency,
        "time_efficiency": request.blueprint.time_efficiency,
        "runs": request.runs if request.runs else "",
        "status": request.status,
        "status_display": request.get_status_display(),
    }


@login_required
@permissions_required("blueprints.request_blueprints")
def list_user_requests(request):

    request_rows = list()

    request_query = Request.objects.select_related_default().filter(
        requesting_user=request.user, closed_at=None
    )
    for request in request_query:
        request_rows.append(convert_request(request))

    return JsonResponse(request_rows, safe=False)


@login_required
@permissions_required("blueprints.manage_requests")
def list_open_requests(request):

    request_rows = list()

    requests = Request.objects.select_related_default().requests_fulfillable_by_user(
        request.user
    ) | Request.objects.select_related_default().requests_being_fulfilled_by_user(
        request.user
    )

    for request in requests:
        request_rows.append(convert_request(request))

    return JsonResponse(request_rows, safe=False)


def mark_request(
    request, request_id, status, fulfilling_user, closed, *, can_requestor_edit=False
):
    completed = False
    user_request = Request.objects.get(pk=request_id)

    corporation_ids = {
        character.character.corporation_id
        for character in request.user.character_ownerships.all()
    }
    character_ownership_ids = {
        character.pk for character in request.user.character_ownerships.all()
    }
    if (
        (
            user_request.blueprint.owner.corporation
            and user_request.blueprint.owner.corporation.corporation_id
            in corporation_ids
        )
        or (
            not user_request.blueprint.owner.corporation
            and user_request.blueprint.owner.pk in character_ownership_ids
        )
        or (can_requestor_edit and user_request.requesting_user == request.user)
    ):
        if closed:
            user_request.closed_at = datetime.utcnow()
        else:
            user_request.closed_at = None
        user_request.fulfulling_user = fulfilling_user
        user_request.status = status
        user_request.save()
        completed = True
    return user_request, completed


@login_required
@permissions_required("blueprints.manage_requests")
@require_POST
def mark_request_fulfilled(request, request_id):
    user_request, completed = mark_request(
        request, request_id, Request.STATUS_FULFILLED, request.user, True
    )
    if completed:
        messages_plus.info(
            request,
            format_html(
                gettext_lazy(
                    "The request for %(blueprint)s has been closed as fulfilled."
                )
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    else:
        messages_plus.error(
            request,
            format_html(
                gettext_lazy("Fulfilling the request for %(blueprint)s has failed.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    return redirect("blueprints:index")


@login_required
@permissions_required("blueprints.manage_requests")
@require_POST
def mark_request_in_progress(request, request_id):
    user_request, completed = mark_request(
        request, request_id, Request.STATUS_IN_PROGRESS, request.user, False
    )
    if completed:
        messages_plus.info(
            request,
            format_html(
                gettext_lazy(
                    "The request for %(blueprint)s has been marked as in progress."
                )
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    else:
        messages_plus.error(
            request,
            format_html(
                gettext_lazy(
                    "Marking the request for %(blueprint)s as in progress has failed."
                )
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    return redirect("blueprints:index")


@login_required
@permissions_required("blueprints.manage_requests")
@require_POST
def mark_request_open(request, request_id):
    user_request, completed = mark_request(
        request, request_id, Request.STATUS_OPEN, None, False
    )
    if completed:
        messages_plus.info(
            request,
            format_html(
                gettext_lazy("The request for %(blueprint)s has been re-opened.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    else:
        messages_plus.error(
            request,
            format_html(
                gettext_lazy("Re-opening the request for %(blueprint)s has failed.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    return redirect("blueprints:index")


@login_required
@permissions_required(["blueprints.basic_access", "blueprints.manage_requests"])
@require_POST
def mark_request_cancelled(request, request_id):
    user_request, completed = mark_request(
        request,
        request_id,
        Request.STATUS_CANCELLED,
        None,
        True,
        can_requestor_edit=True,
    )
    if completed:
        messages_plus.info(
            request,
            format_html(
                gettext_lazy(
                    "The request for %(blueprint)s has been closed as cancelled."
                )
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    else:
        messages_plus.error(
            request,
            format_html(
                gettext_lazy("Cancelling the request for %(blueprint)s has failed.")
                % {"blueprint": user_request.blueprint.eve_type.name}
            ),
        )
    return redirect("blueprints:index")

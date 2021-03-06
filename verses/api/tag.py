from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from verses.schema import TranslationTagSchema, PurportSectionTagSchema
from common import api_exceptions
from common.helpers import get_filters, api_token_required
import json
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from verses.models import Verse, TranslationTag, PurportSectionTag, Tag
from common.helpers import make_response, GET_SUCCESS_CODE, POST_SUCCESS_CODE, PUT_SUCCESS_CODE, DELETE_SUCCESS_CODE
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.utils import IntegrityError
from marshmallow import ValidationError as MarshmallowValidationError
from django.views.decorators.http import require_http_methods

class TagTranslationHandler(View):
    schema = TranslationTagSchema

    @method_decorator(api_exceptions.api_exception_handler)
    @method_decorator(api_token_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(TagTranslationHandler, self).dispatch(*args, **kwargs)

    def get(self, request):
        verse_filter_params = {"verse__canto_num":"canto_num", "verse__chapter_num":"chapter_num"}
        tag_filter_params = {"verse__verse_id":"verse_id"}
        verse_filters = get_filters(request, verse_filter_params)
        tag_filters = get_filters(request, tag_filter_params)

        tag_objects = TranslationTag.objects.filter(**tag_filters).select_related("verse")
        tag_objects = tag_objects.filter(**verse_filters)
        schema = (self.schema)()
        data = schema.dump(tag_objects, many=True)
        resp_data = make_response(data, message="Successfully fetched translation tags", code=GET_SUCCESS_CODE)
        return JsonResponse(resp_data)

    def post(self, request):
        req_data = json.loads(request.body)
        schema = (self.schema)()
        resp_data = []
        verse_id = req_data["verse_id"]
        for req in req_data["translationtags"]:
            try:
                req['verse_id'] = verse_id
                new_translation_tag = schema.load(req)
            except MarshmallowValidationError as e:
                raise api_exceptions.BadRequestData(errors=e.messages)
            new_translation_tag["verse"] = Verse.objects.get(verse_id=new_translation_tag["verse_id"])
            new_translation_tag["tag_name"] = Tag.objects.get(name=new_translation_tag["tag"])
            new_translation_tag["tagger"] = request.user
            new_translation_tag.pop("tag")
            try:
                translation_tags = self.schema.model.objects.create(**new_translation_tag)
            except DjangoValidationError as e:
                raise api_exceptions.ValidationError(errors=e.message_dict)
            except IntegrityError as e:
                if new_translation_tag.get("tagger_remark"):
                    t_tag = self.schema.model.objects.filter(verse_id=new_translation_tag["verse_id"], tag_name=new_translation_tag["tag_name"])
                    t_tag.update(tagger_remark=new_translation_tag["tagger_remark"])
                    t_tag[0].save()
                    resp_data.append(schema.dump(t_tag[0]))
                    continue
                else:
                    raise api_exceptions.ValidationError(errors="DB Integrity error")
            resp_data.append(schema.dump(translation_tags))
        return JsonResponse(make_response(resp_data, "Successfully added translation tags", POST_SUCCESS_CODE))

    def delete(self, request, id, format=None):
        tag = self.schema.model.objects.filter(id=id)
        if not tag:
            raise api_exceptions.ValidationError(errors="Not a valid tag_id")
        tag[0].delete()
        return JsonResponse(make_response({}, "Successfully deleted translation tag", DELETE_SUCCESS_CODE))

    def put(self, request, id, format=None):
        tag = self.schema.model.objects.filter(id=id)
        if request.user.user_type!=3:
            raise api_exceptions.PermissionDenied(errors="Only reviewers are allowed to update")
        if not tag:
            raise api_exceptions.ValidationError(errors="Not a valid tag_id")
        tag[0].reviewer = request.user
        tag[0].save()
        return JsonResponse(make_response({}, "Successfully reviewed translation tag", PUT_SUCCESS_CODE))

class TagPurportSectionHandler(View):
    schema = PurportSectionTagSchema

    @method_decorator(api_exceptions.api_exception_handler)
    @method_decorator(api_token_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super(TagPurportSectionHandler, self).dispatch(*args, **kwargs)

    def get(self, request):
        verse_filter_params = {"verse__canto_num":"canto_num", "verse__chapter_num":"chapter_num"}
        tag_filter_params = {"verse__verse_id":"verse_id"}
        verse_filters = get_filters(request, verse_filter_params)
        tag_filters = get_filters(request, tag_filter_params)

        tag_objects = PurportSectionTag.objects.filter(**tag_filters).select_related("verse")
        tag_objects = tag_objects.filter(**verse_filters).order_by("start_idx")
        schema = (self.schema)()
        data = schema.dump(tag_objects, many=True)
        resp_data = make_response(data, message="Successfully fetched purport tags", code=GET_SUCCESS_CODE)
        return JsonResponse(resp_data)

    def post(self, request):
        req_data = json.loads(request.body)
        schema = (self.schema)()
        resp_data = []
        verse_id = req_data['verse_id']
        for req in req_data['purporttags']:
            try:
                req['verse_id'] = verse_id
                new_purport_section_tag = schema.load(req)
            except MarshmallowValidationError as e:
                raise api_exceptions.BadRequestData(errors=e.messages)
            try:
                new_purport_section_tag["tag_name"] = Tag.objects.get(name=new_purport_section_tag["tag"])
                new_purport_section_tag["tagger"] = request.user
                new_purport_section_tag.pop("tag")
                purport_section_tags = self.schema.model.objects.create(**new_purport_section_tag)
            except DjangoValidationError as e:
                raise api_exceptions.ValidationError(errors=e.message_dict)
            except IntegrityError as e:
                if new_purport_section_tag.get("tagger_remark"):
                    p_tag = self.schema.model.objects.filter(verse_id=new_purport_section_tag["verse_id"], start_idx=new_purport_section_tag["start_idx"], end_idx=new_purport_section_tag["end_idx"], tag=new_purport_section_tag["tag_name"])
                    p_tag.update(tagger_remark=new_purport_section_tag["tagger_remark"])
                    p_tag[0].save()
                    resp_data.append(schema.dump(p_tag[0]))
                    continue
                else:
                    raise api_exceptions.ValidationError(errors="DB Integrity error")
            resp_data.append(schema.dump(purport_section_tags))
        return JsonResponse(make_response(resp_data, "Successfully added purport tags", POST_SUCCESS_CODE))

    def delete(self, request, id, format=None):
        tag = self.schema.model.objects.filter(id=id)
        if not tag:
            raise api_exceptions.ValidationError(errors="Not a valid tag_id")
        tag[0].delete()
        return JsonResponse(make_response({}, "Successfully deleted purport tag", DELETE_SUCCESS_CODE))

    def put(self, request, id, format=None):
        tag = self.schema.model.objects.filter(id=id)
        if request.user.user_type!=3:
            raise api_exceptions.PermissionDenied(errors="Only reviewers are allowed to update")
        if not tag:
            raise api_exceptions.ValidationError(errors="Not a valid tag_id")
        tag[0].reviewer = request.user
        tag[0].save()
        return JsonResponse(make_response({}, "Successfully reviewed purport tag", PUT_SUCCESS_CODE))

def get_sub_tags(tag):
    if tag.is_leaf:
        return {}
    else:
        return {child.name:get_sub_tags(child) for child in Tag.objects.filter(parent__id=tag.id)}

@require_http_methods(["GET"])
@api_exceptions.api_exception_handler
@api_token_required
@method_decorator(csrf_exempt)
def get_tags(request):
    top_tags = Tag.objects.filter(level=1)
    all_tags = [{l1_tag.name:get_sub_tags(l1_tag) for l1_tag in top_tags}]
    return JsonResponse(make_response(all_tags, "Successfully fetched all tags", GET_SUCCESS_CODE))


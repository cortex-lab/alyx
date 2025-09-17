from pathlib import Path
import json
from django.http import JsonResponse

from rest_framework.negotiation import BaseContentNegotiation
from drf_spectacular.views import SpectacularRedocView

import alyx


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    def select_parser(self, request, parsers):
        """
        Select the first parser in the `.parser_classes` list.
        """
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):
        """
        Select the first renderer in the `.renderer_classes` list.
        """
        return (renderers[0], renderers[0].media_type)


class SpectacularRedocViewCoreAPIDeprecation(SpectacularRedocView):
    """
    This view is used to intercept the coreAPI content type and return a JSON response instead of HTML.
    In the newest docs, this /docs is only used for http webpage content and the the API schemes
    are now served via the api/schema
    """
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request, *args, **kwargs):
        if request.headers['Accept'].startswith('application/coreapi+json'):
            with open(Path(alyx.__file__).parents[2].joinpath('data', 'coreapi.json'), 'r') as f:
                response = JsonResponse(json.load(f))
            return response
        else:
            return super().get(request, *args, **kwargs)
